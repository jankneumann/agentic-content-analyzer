"""Complexity-based prompt router for dynamic model selection.

Routes prompts to strong or weak models based on estimated complexity.
Uses an embedding + classifier approach: prompts are embedded, then a
lightweight classifier (logistic regression) predicts complexity score.

Cold start: Falls back to fixed mode when no trained classifier exists.
Embedding failure: Falls back to fixed mode and logs warning.
"""

import hashlib
import logging
import pickle  # noqa: S403
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Directory for persisted classifier models
_MODELS_DIR = Path(__file__).parent.parent.parent / "data" / "classifiers"


@dataclass
class RoutingDecisionInfo:
    """Information about a routing decision for logging."""

    step: str
    complexity_score: float
    threshold: float
    model_selected: str
    strong_model: str
    weak_model: str
    prompt_hash: str


class ComplexityRouter:
    """Route prompts by complexity using embedding + classifier.

    The classifier is trained on evaluation data (see ThresholdCalibrator).
    Before training, all calls fall back to fixed mode.

    Args:
        embed_fn: Callable that embeds a text string into a float vector.
                  Should wrap the configured embedding provider.
    """

    def __init__(self, embed_fn: Callable[[str], list[float]] | None = None):
        """Initialize the complexity router.

        Args:
            embed_fn: Embedding function. If None, classify() always falls back.
        """
        self.embed_fn = embed_fn
        self._classifiers: dict[str, object] = {}  # step -> trained classifier
        self._classifier_versions: dict[str, str] = {}  # step -> version

    def classify(
        self,
        prompt: str,
        step: str,
        strong_model: str,
        weak_model: str,
        threshold: float,
    ) -> RoutingDecisionInfo:
        """Classify a prompt and decide which model to use.

        Args:
            prompt: The user prompt to classify
            step: Pipeline step name
            strong_model: Model ID for complex prompts
            weak_model: Model ID for simple prompts
            threshold: Complexity score threshold (>= means use strong)

        Returns:
            RoutingDecisionInfo with selected model and scores

        Falls back to strong_model if:
        - No trained classifier exists for this step
        - Embedding function is not configured
        - Embedding or classification fails
        """
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16]

        # Cold start fallback (spec 7)
        if step not in self._classifiers:
            logger.warning(
                "No trained classifier for step '%s', falling back to fixed mode (strong model)",
                step,
            )
            return RoutingDecisionInfo(
                step=step,
                complexity_score=1.0,  # Assume complex
                threshold=threshold,
                model_selected=strong_model,
                strong_model=strong_model,
                weak_model=weak_model,
                prompt_hash=prompt_hash,
            )

        # Embedding failure fallback (spec 15a)
        if self.embed_fn is None:
            logger.warning(
                "No embedding function configured for step '%s', falling back to strong model",
                step,
            )
            return RoutingDecisionInfo(
                step=step,
                complexity_score=1.0,
                threshold=threshold,
                model_selected=strong_model,
                strong_model=strong_model,
                weak_model=weak_model,
                prompt_hash=prompt_hash,
            )

        try:
            embedding = self.embed_fn(prompt)
        except Exception as e:
            logger.warning(
                "Embedding failed for step '%s', falling back to strong model: %s",
                step,
                e,
            )
            return RoutingDecisionInfo(
                step=step,
                complexity_score=1.0,
                threshold=threshold,
                model_selected=strong_model,
                strong_model=strong_model,
                weak_model=weak_model,
                prompt_hash=prompt_hash,
            )

        # Classify
        try:
            classifier = self._classifiers[step]
            # predict_proba returns [[p_simple, p_complex]]
            proba = classifier.predict_proba([embedding])[0]
            complexity_score = float(proba[1])  # Probability of "complex" class
        except Exception as e:
            logger.warning(
                "Classifier inference failed for step '%s': %s. Falling back to strong model.",
                step,
                e,
            )
            return RoutingDecisionInfo(
                step=step,
                complexity_score=1.0,
                threshold=threshold,
                model_selected=strong_model,
                strong_model=strong_model,
                weak_model=weak_model,
                prompt_hash=prompt_hash,
            )

        # Route decision
        model_selected = strong_model if complexity_score >= threshold else weak_model

        return RoutingDecisionInfo(
            step=step,
            complexity_score=complexity_score,
            threshold=threshold,
            model_selected=model_selected,
            strong_model=strong_model,
            weak_model=weak_model,
            prompt_hash=prompt_hash,
        )

    def train(
        self,
        step: str,
        embeddings: list[list[float]],
        labels: list[int],
        version: str | None = None,
    ) -> float:
        """Train the complexity classifier for a step.

        Args:
            step: Pipeline step name
            embeddings: List of prompt embeddings
            labels: List of labels (0=simple/weak-ok, 1=complex/needs-strong)
            version: Optional version identifier for the trained model

        Returns:
            Training accuracy score

        Raises:
            ImportError: If scikit-learn is not installed
            ValueError: If training data is insufficient
        """
        from sklearn.linear_model import LogisticRegression

        if len(embeddings) < 10:
            raise ValueError(f"Insufficient training data: {len(embeddings)} samples (minimum 10)")

        clf = LogisticRegression(max_iter=1000, random_state=42)
        clf.fit(embeddings, labels)
        accuracy = clf.score(embeddings, labels)

        self._classifiers[step] = clf
        self._classifier_versions[step] = version or "v1"

        logger.info(
            "Trained classifier for step '%s': accuracy=%.3f, samples=%d, version=%s",
            step,
            accuracy,
            len(embeddings),
            self._classifier_versions[step],
        )

        return accuracy

    def save_model(self, step: str, path: Path | None = None) -> Path:
        """Persist trained classifier to disk.

        Args:
            step: Pipeline step name
            path: Optional custom path. Defaults to data/classifiers/{step}.pkl

        Returns:
            Path where the model was saved
        """
        if step not in self._classifiers:
            raise ValueError(f"No trained classifier for step '{step}'")

        save_path = path or (_MODELS_DIR / f"{step}.pkl")
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with open(save_path, "wb") as f:
            pickle.dump(
                {
                    "classifier": self._classifiers[step],
                    "version": self._classifier_versions.get(step, "v1"),
                },
                f,
            )

        logger.info("Saved classifier for step '%s' to %s", step, save_path)
        return save_path

    def load_model(self, step: str, path: Path | None = None) -> bool:
        """Load a trained classifier from disk.

        Args:
            step: Pipeline step name
            path: Optional custom path. Defaults to data/classifiers/{step}.pkl

        Returns:
            True if loaded successfully, False if file not found
        """
        load_path = path or (_MODELS_DIR / f"{step}.pkl")
        if not load_path.exists():
            return False

        # Validate default path is within the allowed models directory
        if path is None:
            try:
                load_path.resolve().relative_to(_MODELS_DIR.resolve())
            except ValueError:
                logger.error("Refusing to load classifier from outside models dir: %s", load_path)
                return False

        with open(load_path, "rb") as f:
            data = pickle.load(f)  # noqa: S301

        self._classifiers[step] = data["classifier"]
        self._classifier_versions[step] = data.get("version", "unknown")

        logger.info(
            "Loaded classifier for step '%s' from %s (version: %s)",
            step,
            load_path,
            self._classifier_versions[step],
        )
        return True
