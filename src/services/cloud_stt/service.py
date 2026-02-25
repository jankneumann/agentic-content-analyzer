"""Cloud STT service with provider factory.

Resolves the appropriate cloud STT provider based on the model family
of the configured CLOUD_STT pipeline step model.
"""

from src.config.models import ModelFamily, ModelStep, get_model_config
from src.services.cloud_stt.provider import CloudSTTProvider
from src.utils.logging import get_logger

logger = get_logger(__name__)


class CloudSTTService:
    """Service for creating cloud STT providers from pipeline configuration.

    The provider is resolved from the CLOUD_STT pipeline step model family:
    - gemini model → GeminiSTTProvider (cleaned=True)
    - whisper model → WhisperSTTProvider (cleaned=False)
    - deepgram model → DeepgramSTTProvider (cleaned=False)
    """

    def create_provider(self, api_key: str | None = None) -> CloudSTTProvider:
        """Create a cloud STT provider based on the current model configuration.

        Args:
            api_key: Optional API key override. If not provided, the provider
                     will use its default API key resolution.

        Returns:
            A CloudSTTProvider instance for the configured model family

        Raises:
            ValueError: If the model family is not supported for STT
        """
        config = get_model_config()
        model_id = config.get_model_for_step(ModelStep.CLOUD_STT)
        model_info = config.get_model_info(model_id)
        family = model_info.family

        return self._create_provider_for_family(family, model_id, api_key)

    @staticmethod
    def _create_provider_for_family(
        family: ModelFamily,
        model_id: str,
        api_key: str | None = None,
    ) -> CloudSTTProvider:
        """Create a provider adapter for the given model family.

        Args:
            family: The model family to resolve
            model_id: The specific model ID
            api_key: Optional API key

        Returns:
            The appropriate CloudSTTProvider

        Raises:
            ValueError: If the family is not supported for cloud STT
        """
        if family == ModelFamily.GEMINI:
            from src.services.cloud_stt.gemini_provider import GeminiSTTProvider

            return GeminiSTTProvider(model_id=model_id, api_key=api_key)

        if family == ModelFamily.WHISPER:
            from src.services.cloud_stt.whisper_provider import WhisperSTTProvider

            return WhisperSTTProvider(model_id=model_id, api_key=api_key)

        if family == ModelFamily.DEEPGRAM:
            from src.services.cloud_stt.deepgram_provider import DeepgramSTTProvider

            return DeepgramSTTProvider(model_id=model_id, api_key=api_key)

        raise ValueError(
            f"Model family '{family}' does not support cloud STT. "
            f"Supported families: gemini, whisper, deepgram"
        )
