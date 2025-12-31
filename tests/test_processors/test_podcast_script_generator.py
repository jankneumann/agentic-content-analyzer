"""Tests for podcast script generation."""

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.podcast import (
    DialogueTurn,
    PodcastGenerationMetadata,
    PodcastLength,
    PodcastRequest,
    PodcastScript,
    PodcastSection,
    VoicePersona,
    VoiceProvider,
)
from src.processors.podcast_script_generator import (
    PODCAST_SCRIPT_LENGTH_PROMPTS,
    PODCAST_SCRIPT_SYSTEM_PROMPT,
    PODCAST_TOOLS,
    WORD_COUNT_TARGETS,
    PodcastScriptGenerator,
)


@pytest.fixture
def sample_digest_data() -> dict:
    """Create sample digest data for testing."""
    return {
        "id": 1,
        "digest_type": "daily",
        "period_start": "2025-01-01T00:00:00",
        "period_end": "2025-01-05T23:59:59",
        "title": "AI/Tech Digest - January 1-5, 2025",
        "executive_overview": (
            "This week saw significant advancements in large language models and "
            "infrastructure for AI applications. Key strategic decisions needed around "
            "vector database adoption and LLM deployment strategies."
        ),
        "strategic_insights": [
            {
                "title": "LLM Capabilities Expanding Rapidly",
                "summary": "Context windows and multimodal capabilities reaching new heights [1].",
                "details": [
                    "Context windows now exceed 1M tokens in production systems [1]",
                    "Cost per token decreasing 40% year-over-year [2]",
                ],
                "themes": ["Large Language Models"],
            }
        ],
        "technical_developments": [
            {
                "title": "Hybrid Vector Search",
                "summary": "Combining vector and keyword search for better accuracy [2].",
                "details": [
                    "Reranking models improving relevance by 30% [2]",
                ],
                "themes": ["Vector Databases", "RAG"],
            }
        ],
        "emerging_trends": [
            {
                "title": "Multi-Agent Orchestration",
                "summary": "New frameworks for coordinating multiple AI agents [1][2].",
                "details": [
                    "LangGraph and similar frameworks gaining adoption [1]",
                ],
                "themes": ["AI Agents"],
            }
        ],
        "actionable_recommendations": {
            "for_leadership": ["Evaluate long-context LLM use cases"],
            "for_teams": ["Prototype hybrid search for RAG systems"],
            "for_individuals": ["Learn about embedding models"],
        },
    }


@pytest.fixture
def sample_newsletter_metadata() -> list[dict]:
    """Create sample newsletter metadata for testing."""
    return [
        {
            "id": 1,
            "title": "AI Weekly - Latest in LLMs",
            "publication": "AI Weekly",
            "date": "2025-01-01T00:00:00",
            "url": "https://example.com/article1",
        },
        {
            "id": 2,
            "title": "Tech Trends Report",
            "publication": "TechCrunch",
            "date": "2025-01-02T00:00:00",
            "url": "https://example.com/article2",
        },
    ]


@pytest.fixture
def sample_summaries() -> list:
    """Create sample newsletter summaries for testing."""

    class MockSummary:
        def __init__(self, newsletter_id):
            self.newsletter_id = newsletter_id
            self.executive_summary = f"Summary for newsletter {newsletter_id}"
            self.key_themes = ["AI", "Machine Learning"]
            self.strategic_insights = ["Strategic insight 1", "Strategic insight 2"]
            self.technical_details = ["Technical detail 1", "Technical detail 2"]
            self.relevant_links = []

    return [MockSummary(1), MockSummary(2)]


@pytest.fixture
def mock_llm_script_response() -> dict:
    """Create mock LLM response for script generation."""
    return {
        "title": "AI Insights Weekly - January 2025",
        "sections": [
            {
                "section_type": "intro",
                "title": "Welcome to AI Insights",
                "dialogue": [
                    {
                        "speaker": "alex",
                        "text": "Welcome to AI Insights Weekly! I'm Alex Chen, and today we're diving into the biggest AI developments.",
                        "emphasis": "excited",
                        "pause_after": 0.5,
                    },
                    {
                        "speaker": "sam",
                        "text": "Thanks Alex! And I'm Sam Rodriguez. We've got some fascinating technical developments to discuss.",
                        "emphasis": "thoughtful",
                        "pause_after": 0.5,
                    },
                ],
                "sources_cited": [1, 2],
            },
            {
                "section_type": "strategic",
                "title": "LLM Evolution",
                "dialogue": [
                    {
                        "speaker": "alex",
                        "text": "The big story this week is context windows exceeding 1 million tokens. What does this mean for enterprise applications?",
                        "emphasis": "thoughtful",
                        "pause_after": 0.8,
                    },
                    {
                        "speaker": "sam",
                        "text": "It's huge, Alex. We can now process entire codebases in a single prompt. Think about the implications for code review.",
                        "emphasis": "excited",
                        "pause_after": 0.5,
                    },
                ],
                "sources_cited": [1],
            },
            {
                "section_type": "outro",
                "title": "Wrap Up",
                "dialogue": [
                    {
                        "speaker": "alex",
                        "text": "That's all for this week! Thanks for listening.",
                        "emphasis": None,
                        "pause_after": 0.5,
                    },
                    {
                        "speaker": "sam",
                        "text": "See you next time!",
                        "emphasis": "amused",
                        "pause_after": 0.3,
                    },
                ],
                "sources_cited": [],
            },
        ],
        "sources_summary": [
            {"id": 1, "title": "AI Weekly - Latest in LLMs", "publication": "AI Weekly"},
            {"id": 2, "title": "Tech Trends Report", "publication": "TechCrunch"},
        ],
    }


@pytest.fixture
def podcast_request() -> PodcastRequest:
    """Create a standard podcast request for testing."""
    return PodcastRequest(
        digest_id=1,
        length=PodcastLength.STANDARD,
        enable_web_search=True,
        voice_provider=VoiceProvider.OPENAI_TTS,
        alex_voice=VoicePersona.ALEX_MALE,
        sam_voice=VoicePersona.SAM_FEMALE,
    )


class TestPodcastScriptGenerator:
    """Tests for PodcastScriptGenerator class."""

    def test_initialization(self):
        """Test generator initialization."""
        generator = PodcastScriptGenerator()

        assert generator.model is not None
        assert generator.provider_used is None
        assert generator.input_tokens == 0
        assert generator.output_tokens == 0
        assert generator.newsletter_ids_fetched == []
        assert generator.web_search_queries == []
        assert generator.tool_call_count == 0

    def test_word_count_targets(self):
        """Test word count targets are properly defined."""
        assert PodcastLength.BRIEF in WORD_COUNT_TARGETS
        assert PodcastLength.STANDARD in WORD_COUNT_TARGETS
        assert PodcastLength.EXTENDED in WORD_COUNT_TARGETS

        # Verify brief is shortest
        assert WORD_COUNT_TARGETS[PodcastLength.BRIEF]["max"] < WORD_COUNT_TARGETS[PodcastLength.STANDARD]["min"]

        # Verify standard is in middle
        assert WORD_COUNT_TARGETS[PodcastLength.STANDARD]["max"] < WORD_COUNT_TARGETS[PodcastLength.EXTENDED]["min"]

    def test_length_prompts_defined(self):
        """Test length-specific prompts are defined."""
        for length in PodcastLength:
            assert length in PODCAST_SCRIPT_LENGTH_PROMPTS
            assert len(PODCAST_SCRIPT_LENGTH_PROMPTS[length]) > 100

    def test_system_prompt_contains_personas(self):
        """Test system prompt includes both personas."""
        assert "Alex Chen" in PODCAST_SCRIPT_SYSTEM_PROMPT
        assert "Dr. Sam Rodriguez" in PODCAST_SCRIPT_SYSTEM_PROMPT
        assert "VP of Engineering" in PODCAST_SCRIPT_SYSTEM_PROMPT
        assert "Distinguished Engineer" in PODCAST_SCRIPT_SYSTEM_PROMPT

    def test_tools_definition(self):
        """Test tools are properly defined."""
        assert len(PODCAST_TOOLS) == 2

        tool_names = [t["name"] for t in PODCAST_TOOLS]
        assert "get_newsletter_content" in tool_names
        assert "web_search" in tool_names

        for tool in PODCAST_TOOLS:
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"


class TestContextAssembly:
    """Tests for lightweight context assembly."""

    @pytest.mark.asyncio
    async def test_assemble_lightweight_context_no_digest(self):
        """Test context assembly when digest not found."""
        generator = PodcastScriptGenerator()
        request = PodcastRequest(digest_id=999)

        with patch("src.processors.podcast_script_generator.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value.__enter__.return_value = mock_db

            context = await generator._assemble_lightweight_context(request)

        assert context["digest"] is None

    @pytest.mark.asyncio
    async def test_assemble_lightweight_context_success(
        self, sample_digest_data, sample_newsletter_metadata
    ):
        """Test successful context assembly."""
        generator = PodcastScriptGenerator()
        request = PodcastRequest(
            digest_id=1,
            custom_focus_topics=["AI Agents", "RAG"],
        )

        # Create mock digest
        mock_digest = MagicMock()
        mock_digest.id = 1
        mock_digest.digest_type.value = "daily"
        mock_digest.period_start = datetime(2025, 1, 1)
        mock_digest.period_end = datetime(2025, 1, 5)
        mock_digest.title = sample_digest_data["title"]
        mock_digest.executive_overview = sample_digest_data["executive_overview"]
        mock_digest.strategic_insights = sample_digest_data["strategic_insights"]
        mock_digest.technical_developments = sample_digest_data["technical_developments"]
        mock_digest.emerging_trends = sample_digest_data["emerging_trends"]
        mock_digest.actionable_recommendations = sample_digest_data["actionable_recommendations"]

        # Create mock newsletters
        mock_newsletters = []
        for nl in sample_newsletter_metadata:
            mock_nl = MagicMock()
            mock_nl.id = nl["id"]
            mock_nl.title = nl["title"]
            mock_nl.publication = nl["publication"]
            mock_nl.published_date = datetime.fromisoformat(nl["date"])
            mock_nl.url = nl["url"]
            mock_newsletters.append(mock_nl)

        with patch("src.processors.podcast_script_generator.get_db") as mock_get_db:
            mock_db = MagicMock()

            # Setup chain for digest query
            mock_db.query.return_value.filter.return_value.first.return_value = mock_digest

            # Setup chain for newsletters query
            nl_query = mock_db.query.return_value.filter.return_value
            nl_query.order_by.return_value.all.return_value = mock_newsletters

            # Setup chain for summaries query
            summaries_query = mock_db.query.return_value.filter.return_value
            summaries_query.all.return_value = []

            mock_get_db.return_value.__enter__.return_value = mock_db

            context = await generator._assemble_lightweight_context(request)

        assert context["digest"] is not None
        assert context["digest"]["id"] == 1
        assert context["length"] == PodcastLength.STANDARD
        assert context["custom_focus_topics"] == ["AI Agents", "RAG"]


class TestFormatting:
    """Tests for prompt formatting methods."""

    def test_format_newsletter_list_empty(self):
        """Test formatting empty newsletter list."""
        generator = PodcastScriptGenerator()
        result = generator._format_newsletter_list([])
        assert "No newsletters available" in result

    def test_format_newsletter_list(self, sample_newsletter_metadata):
        """Test formatting newsletter list."""
        generator = PodcastScriptGenerator()
        result = generator._format_newsletter_list(sample_newsletter_metadata)

        assert "[1]" in result
        assert "[2]" in result
        assert "AI Weekly" in result
        assert "TechCrunch" in result
        assert "2025-01-01" in result

    def test_format_summaries_empty(self):
        """Test formatting empty summaries."""
        generator = PodcastScriptGenerator()
        result = generator._format_summaries([])
        assert "No summaries available" in result

    def test_format_summaries(self, sample_summaries):
        """Test formatting summaries."""
        generator = PodcastScriptGenerator()
        result = generator._format_summaries(sample_summaries)

        assert "[1]" in result
        assert "[2]" in result
        assert "Summary for newsletter 1" in result
        assert "AI" in result
        assert "Machine Learning" in result


class TestToolHandlers:
    """Tests for tool handler methods."""

    @pytest.mark.asyncio
    async def test_handle_get_newsletter_content_not_found(self):
        """Test newsletter content retrieval when not found."""
        generator = PodcastScriptGenerator()

        with patch("src.processors.podcast_script_generator.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_get_db.return_value.__enter__.return_value = mock_db

            result = await generator._handle_get_newsletter_content(999)

        assert "not found" in result
        assert 999 in generator.newsletter_ids_fetched

    @pytest.mark.asyncio
    async def test_handle_get_newsletter_content_success(self):
        """Test successful newsletter content retrieval."""
        generator = PodcastScriptGenerator()

        mock_newsletter = MagicMock()
        mock_newsletter.id = 1
        mock_newsletter.title = "Test Newsletter"
        mock_newsletter.publication = "Test Publication"
        mock_newsletter.published_date = datetime(2025, 1, 1)
        mock_newsletter.raw_text = "This is the newsletter content with important AI news."

        with patch("src.processors.podcast_script_generator.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_newsletter
            mock_get_db.return_value.__enter__.return_value = mock_db

            result = await generator._handle_get_newsletter_content(1)

        assert "Test Newsletter" in result
        assert "Test Publication" in result
        assert "important AI news" in result
        assert 1 in generator.newsletter_ids_fetched

    @pytest.mark.asyncio
    async def test_handle_get_newsletter_content_truncation(self):
        """Test newsletter content is truncated for long content."""
        generator = PodcastScriptGenerator()

        # Create content longer than 15k chars
        long_content = "A" * 20000

        mock_newsletter = MagicMock()
        mock_newsletter.id = 1
        mock_newsletter.title = "Long Newsletter"
        mock_newsletter.publication = "Test"
        mock_newsletter.published_date = datetime(2025, 1, 1)
        mock_newsletter.raw_text = long_content

        with patch("src.processors.podcast_script_generator.get_db") as mock_get_db:
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = mock_newsletter
            mock_get_db.return_value.__enter__.return_value = mock_db

            result = await generator._handle_get_newsletter_content(1)

        assert "[Content truncated...]" in result

    @pytest.mark.asyncio
    async def test_handle_web_search(self):
        """Test web search handler (stub implementation)."""
        generator = PodcastScriptGenerator()

        result = await generator._handle_web_search("latest AI news 2025")

        assert "latest AI news 2025" in result
        assert "pending implementation" in result.lower()
        assert "latest AI news 2025" in generator.web_search_queries


class TestScriptParsing:
    """Tests for script response parsing."""

    def test_parse_script_response_success(self, mock_llm_script_response):
        """Test successful script parsing."""
        generator = PodcastScriptGenerator()

        # Create mock response
        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = json.dumps(mock_llm_script_response)
        mock_response.content = [mock_text_block]

        script = generator._parse_script_response(mock_response, PodcastLength.STANDARD)

        assert isinstance(script, PodcastScript)
        assert script.title == "AI Insights Weekly - January 2025"
        assert script.length == PodcastLength.STANDARD
        assert len(script.sections) == 3
        assert script.intro is not None
        assert script.intro.section_type == "intro"
        assert script.outro is not None
        assert script.outro.section_type == "outro"
        assert len(script.sources_summary) == 2

    def test_parse_script_response_with_markdown(self, mock_llm_script_response):
        """Test parsing script with markdown code blocks."""
        generator = PodcastScriptGenerator()

        # Wrap JSON in markdown code block
        json_with_markdown = f"```json\n{json.dumps(mock_llm_script_response)}\n```"

        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = json_with_markdown
        mock_response.content = [mock_text_block]

        script = generator._parse_script_response(mock_response, PodcastLength.BRIEF)

        assert isinstance(script, PodcastScript)
        assert script.title == "AI Insights Weekly - January 2025"

    def test_parse_script_response_invalid_json(self):
        """Test parsing when JSON is invalid."""
        generator = PodcastScriptGenerator()

        mock_response = MagicMock()
        mock_text_block = MagicMock()
        mock_text_block.text = "This is not valid JSON { broken"
        mock_response.content = [mock_text_block]

        script = generator._parse_script_response(mock_response, PodcastLength.STANDARD)

        # Should return fallback script
        assert isinstance(script, PodcastScript)
        assert "Digest Podcast" in script.title
        assert len(script.sections) == 1  # Only intro section

    def test_parse_script_response_no_content(self):
        """Test parsing when response has no text content."""
        generator = PodcastScriptGenerator()

        mock_response = MagicMock()
        mock_response.content = []

        script = generator._parse_script_response(mock_response, PodcastLength.EXTENDED)

        # Should return fallback script
        assert isinstance(script, PodcastScript)
        assert "issue generating" in script.sections[0].dialogue[1].text.lower()


class TestFallbackScript:
    """Tests for fallback script creation."""

    def test_create_fallback_script_brief(self):
        """Test fallback script for brief length."""
        generator = PodcastScriptGenerator()
        script = generator._create_fallback_script(PodcastLength.BRIEF)

        assert script.length == PodcastLength.BRIEF
        assert len(script.sections) == 1
        assert script.sections[0].section_type == "intro"
        assert len(script.sections[0].dialogue) == 2
        assert script.sections[0].dialogue[0].speaker == "alex"
        assert script.sections[0].dialogue[1].speaker == "sam"

    def test_create_fallback_script_extended(self):
        """Test fallback script for extended length."""
        generator = PodcastScriptGenerator()
        script = generator._create_fallback_script(PodcastLength.EXTENDED)

        assert script.length == PodcastLength.EXTENDED


class TestUserPromptBuilding:
    """Tests for user prompt construction."""

    def test_build_user_prompt(self, sample_digest_data, sample_newsletter_metadata, sample_summaries):
        """Test user prompt building."""
        generator = PodcastScriptGenerator()

        context = {
            "digest": sample_digest_data,
            "newsletter_metadata": sample_newsletter_metadata,
            "summaries": sample_summaries,
            "length": PodcastLength.STANDARD,
            "custom_focus_topics": ["AI Agents"],
        }

        prompt = generator._build_user_prompt(context, PodcastLength.STANDARD)

        # Check digest content included
        assert "AI/Tech Digest" in prompt
        assert "significant advancements" in prompt

        # Check length instructions
        assert "15-minute" in prompt or "15 minutes" in prompt

        # Check word count targets
        assert "2250" in prompt
        assert "3000" in prompt

        # Check custom focus topics
        assert "AI Agents" in prompt

        # Check output format instructions
        assert "JSON" in prompt
        assert "section_type" in prompt
        assert "dialogue" in prompt

    def test_build_user_prompt_no_custom_topics(self, sample_digest_data, sample_newsletter_metadata, sample_summaries):
        """Test user prompt without custom focus topics."""
        generator = PodcastScriptGenerator()

        context = {
            "digest": sample_digest_data,
            "newsletter_metadata": sample_newsletter_metadata,
            "summaries": sample_summaries,
            "length": PodcastLength.BRIEF,
            "custom_focus_topics": [],
        }

        prompt = generator._build_user_prompt(context, PodcastLength.BRIEF)

        # Custom focus section should not appear
        assert "Custom Focus Topics" not in prompt


class TestDialogueTurn:
    """Tests for DialogueTurn model."""

    def test_dialogue_turn_defaults(self):
        """Test DialogueTurn default values."""
        turn = DialogueTurn(speaker="alex", text="Hello!")

        assert turn.speaker == "alex"
        assert turn.text == "Hello!"
        assert turn.emphasis is None
        assert turn.pause_after == 0.5

    def test_dialogue_turn_with_emphasis(self):
        """Test DialogueTurn with emphasis."""
        turn = DialogueTurn(
            speaker="sam",
            text="That's fascinating!",
            emphasis="excited",
            pause_after=0.8,
        )

        assert turn.speaker == "sam"
        assert turn.emphasis == "excited"
        assert turn.pause_after == 0.8


class TestPodcastSection:
    """Tests for PodcastSection model."""

    def test_podcast_section_creation(self):
        """Test PodcastSection creation."""
        dialogue = [
            DialogueTurn(speaker="alex", text="Welcome!"),
            DialogueTurn(speaker="sam", text="Thanks!"),
        ]

        section = PodcastSection(
            section_type="intro",
            title="Introduction",
            dialogue=dialogue,
            sources_cited=[1, 2, 3],
        )

        assert section.section_type == "intro"
        assert section.title == "Introduction"
        assert len(section.dialogue) == 2
        assert section.sources_cited == [1, 2, 3]


class TestPodcastScript:
    """Tests for PodcastScript model."""

    def test_podcast_script_creation(self):
        """Test PodcastScript creation."""
        intro = PodcastSection(
            section_type="intro",
            title="Intro",
            dialogue=[DialogueTurn(speaker="alex", text="Hello!")],
        )

        script = PodcastScript(
            title="Test Podcast",
            length=PodcastLength.STANDARD,
            estimated_duration_seconds=900,
            word_count=2500,
            sections=[intro],
            intro=intro,
            outro=None,
            sources_summary=[{"id": 1, "title": "Source"}],
        )

        assert script.title == "Test Podcast"
        assert script.length == PodcastLength.STANDARD
        assert script.estimated_duration_seconds == 900
        assert script.word_count == 2500


class TestPodcastRequest:
    """Tests for PodcastRequest model."""

    def test_podcast_request_defaults(self):
        """Test PodcastRequest default values."""
        request = PodcastRequest(digest_id=1)

        assert request.digest_id == 1
        assert request.length == PodcastLength.STANDARD
        assert request.enable_web_search is True
        assert request.voice_provider == VoiceProvider.OPENAI_TTS
        assert request.alex_voice == VoicePersona.ALEX_MALE
        assert request.sam_voice == VoicePersona.SAM_FEMALE
        assert request.custom_focus_topics == []

    def test_podcast_request_custom_values(self):
        """Test PodcastRequest with custom values."""
        request = PodcastRequest(
            digest_id=5,
            length=PodcastLength.EXTENDED,
            enable_web_search=False,
            voice_provider=VoiceProvider.ELEVENLABS,
            alex_voice=VoicePersona.ALEX_FEMALE,
            sam_voice=VoicePersona.SAM_MALE,
            custom_focus_topics=["GenAI", "RAG"],
        )

        assert request.digest_id == 5
        assert request.length == PodcastLength.EXTENDED
        assert request.enable_web_search is False
        assert request.voice_provider == VoiceProvider.ELEVENLABS
        assert request.alex_voice == VoicePersona.ALEX_FEMALE
        assert request.sam_voice == VoicePersona.SAM_MALE
        assert request.custom_focus_topics == ["GenAI", "RAG"]


class TestGenerationMetadata:
    """Tests for PodcastGenerationMetadata model."""

    def test_generation_metadata_defaults(self):
        """Test PodcastGenerationMetadata default values."""
        metadata = PodcastGenerationMetadata()

        assert metadata.newsletter_ids_fetched == []
        assert metadata.web_searches == []
        assert metadata.tool_call_count == 0
        assert metadata.total_tokens_used == 0

    def test_generation_metadata_with_data(self):
        """Test PodcastGenerationMetadata with data."""
        metadata = PodcastGenerationMetadata(
            newsletter_ids_fetched=[1, 2, 3],
            web_searches=["AI news", "machine learning trends"],
            tool_call_count=5,
            total_tokens_used=15000,
        )

        assert metadata.newsletter_ids_fetched == [1, 2, 3]
        assert len(metadata.web_searches) == 2
        assert metadata.tool_call_count == 5
        assert metadata.total_tokens_used == 15000
