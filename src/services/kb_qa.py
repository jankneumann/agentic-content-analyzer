"""Knowledge base question-answering service.

Provides a lightweight Q&A loop over compiled topic articles (D5):
1. Keyword-match topics against the question.
2. Cap to top-N by relevance score.
3. Read compiled articles for the selected topics.
4. Render a prompt and synthesize an answer via the configured LLM.
5. Optionally file the answer as a TopicNote on each referenced topic.

The service raises on LLM failure — callers (API, CLI) translate that
into their preferred error response.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.config.models import ModelConfig, ModelStep, get_model_config
from src.config.settings import get_settings
from src.models.topic import Topic, TopicStatus
from src.services.knowledge_base import KnowledgeBaseService
from src.services.llm_router import LLMRouter
from src.services.prompt_service import PromptService

logger = logging.getLogger(__name__)


class KBQAService:
    """Answer questions using compiled KB topic articles.

    Args:
        db: SQLAlchemy session.
        model_config: Optional ModelConfig (defaults to global).
        prompt_service: Optional PromptService (auto-instantiated if None).
        llm_router: Optional LLMRouter (auto-instantiated if None).
        kb_service: Optional KnowledgeBaseService used for file-back mode.
    """

    def __init__(
        self,
        db: Session,
        *,
        model_config: ModelConfig | None = None,
        prompt_service: PromptService | None = None,
        llm_router: LLMRouter | None = None,
        kb_service: KnowledgeBaseService | None = None,
    ) -> None:
        self.db = db
        self.model_config = model_config or get_model_config()
        self.prompt_service = prompt_service or PromptService(db)
        self.llm_router = llm_router or LLMRouter(self.model_config)
        self.kb_service = kb_service or KnowledgeBaseService(
            db,
            model_config=self.model_config,
            prompt_service=self.prompt_service,
            llm_router=self.llm_router,
        )
        self.settings = get_settings()

    async def query(
        self,
        question: str,
        *,
        file_back: bool = False,
    ) -> dict[str, Any]:
        """Answer a question against the KB.

        Args:
            question: The user question (free-form text).
            file_back: If True, file the answer as an insight TopicNote on
                each referenced topic.

        Returns:
            A dict with keys: ``answer`` (markdown), ``topics`` (list of
            slugs referenced), ``truncated`` (bool), and optionally
            ``message`` when no topics matched.
        """
        question = (question or "").strip()
        if not question:
            return {
                "answer": "",
                "topics": [],
                "truncated": False,
                "message": "Question is empty.",
            }

        matched = self._search_topics(question)
        max_topics = int(self.settings.kb_qa_max_topics or 10)
        truncated = len(matched) > max_topics
        selected = matched[:max_topics]

        if not selected:
            return {
                "answer": "",
                "topics": [],
                "truncated": False,
                "message": (
                    "No relevant KB content found for this question. "
                    "Try searching raw content instead."
                ),
            }

        topics_block = self._build_topics_block(selected)
        user_prompt = self.prompt_service.render(
            "pipeline.kb_qa.user_template",
            question=question,
            topics_block=topics_block,
        )
        system_prompt = self.prompt_service.get_pipeline_prompt("kb_qa", "system")
        if not system_prompt:
            system_prompt = (
                "You are a knowledge base assistant answering questions "
                "using compiled topic articles."
            )

        model = self.model_config.get_model_for_step(ModelStep.KB_INDEX)
        qa_timeout = 120  # seconds — reasonable for a single Q&A synthesis
        t0 = time.monotonic()
        try:
            response = await asyncio.wait_for(
                self.llm_router.generate(
                    model=model,
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=1200,
                    temperature=0.3,
                ),
                timeout=qa_timeout,
            )
        except TimeoutError as exc:
            raise RuntimeError(f"KB Q&A LLM call timed out after {qa_timeout}s") from exc
        elapsed = time.monotonic() - t0

        logger.info(
            "kb_qa.query topics_matched=%d topics_selected=%d truncated=%s elapsed_seconds=%.2f",
            len(matched),
            len(selected),
            truncated,
            elapsed,
        )

        answer_text = (response.text or "").strip()
        if truncated:
            answer_text = (
                f"{answer_text}\n\n"
                f"_Note: {len(matched) - max_topics} additional topics were "
                "omitted. Refine your question to see them._"
            )

        topic_slugs = [t.slug for t in selected]

        if file_back and answer_text:
            self._file_back(topic_slugs, question, answer_text)

        return {
            "answer": answer_text,
            "topics": topic_slugs,
            "truncated": truncated,
        }

    def _search_topics(self, question: str) -> list[Topic]:
        """Return topics whose name or summary match the question.

        Uses a simple ILIKE over tokens in the question, then orders the
        result by relevance_score descending. Archived topics are excluded.
        """
        tokens = [t for t in _split_tokens(question) if len(t) >= 3]
        if not tokens:
            # Fall back to whole-question match
            tokens = [question]

        conditions = []
        for token in tokens[:8]:  # cap token expansion
            like = f"%{token}%"
            conditions.append(Topic.name.ilike(like))
            conditions.append(Topic.summary.ilike(like))
            conditions.append(Topic.article_md.ilike(like))

        query = self.db.query(Topic).filter(
            Topic.status.notin_([TopicStatus.ARCHIVED, TopicStatus.MERGED]),
            or_(*conditions),
        )
        return query.order_by(Topic.relevance_score.desc()).limit(50).all()

    def _build_topics_block(self, topics: list[Topic]) -> str:
        """Render the topics block injected into the Q&A prompt.

        Each article is truncated to ~300 words to keep the total prompt
        within LLM context budget (~10 topics * 300 words = ~4000 tokens).
        """
        max_words_per_article = 300
        parts: list[str] = []
        for topic in topics:
            article = (topic.article_md or topic.summary or "").strip()
            words = article.split()
            if len(words) > max_words_per_article:
                article = " ".join(words[:max_words_per_article]) + " [...]"
            parts.append(
                f"### {topic.name} (slug: {topic.slug})\n"
                f"Category: {topic.category}\n"
                f"Trend: {topic.trend or 'unknown'}\n\n"
                f"{article}"
            )
        return "\n\n---\n\n".join(parts)

    def _file_back(
        self,
        slugs: list[str],
        question: str,
        answer: str,
    ) -> None:
        """Create an insight TopicNote on each referenced topic."""
        note_content = f"**Q:** {question}\n\n**A:** {answer}"
        for slug in slugs:
            try:
                self.kb_service.add_note(
                    topic_slug=slug,
                    content=note_content,
                    note_type="insight",
                    author="system",
                )
            except Exception as exc:
                logger.warning("KB Q&A file-back failed for topic %s: %s", slug, exc)


def _split_tokens(value: str) -> list[str]:
    """Tokenize a query string for keyword search."""
    import re

    return [t for t in re.split(r"\W+", value.lower()) if t]
