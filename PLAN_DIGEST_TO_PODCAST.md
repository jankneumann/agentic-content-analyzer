# Implementation Plan: Digest-to-Podcast Audio Feature

## Executive Summary

Transform daily and weekly digests into engaging podcast-style audio content featuring two expert personas discussing AI, Data, and Software development news with perspectives relevant to Comcast and the industry.

**Personas:**
1. **Alex Chen** - VP of Engineering / Senior Technical Leader: Strategic perspective, organizational impact, competitive landscape, investment decisions
2. **Dr. Sam Rodriguez** - Distinguished Engineer: Technical deep-dives, implementation details, architectural implications, developer experience

**Voice Options:** Each persona available in male and female voice variants:
- Alex (Male) / Alex (Female)
- Sam (Male) / Sam (Female)

**Output Formats:**
- **5-minute Brief**: Executive highlights only
- **15-minute Standard**: Key insights + select technical deep-dives
- **30-minute Extended**: Full coverage with detailed analysis

---

## Phase 1: Data Models & Configuration

### 1.1 New Models (`src/models/podcast.py`)

```python
from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from src.storage.database import Base

class PodcastLength(str, Enum):
    BRIEF = "brief"          # 5 minutes (~750-1000 words)
    STANDARD = "standard"    # 15 minutes (~2250-3000 words)
    EXTENDED = "extended"    # 30 minutes (~4500-6000 words)

class PodcastStatus(str, Enum):
    PENDING = "pending"
    SCRIPT_GENERATING = "script_generating"
    SCRIPT_PENDING_REVIEW = "script_pending_review"  # Script ready for human review
    SCRIPT_REVISION_REQUESTED = "script_revision_requested"  # Reviewer requested changes
    SCRIPT_APPROVED = "script_approved"  # Script approved, ready for audio
    AUDIO_GENERATING = "audio_generating"
    COMPLETED = "completed"
    FAILED = "failed"

class VoiceProvider(str, Enum):
    ELEVENLABS = "elevenlabs"
    GOOGLE_TTS = "google_tts"
    AWS_POLLY = "aws_polly"
    OPENAI_TTS = "openai_tts"

class VoicePersona(str, Enum):
    """Voice persona options - each persona available in male/female variants."""
    ALEX_MALE = "alex_male"      # VP Engineering - Male voice
    ALEX_FEMALE = "alex_female"  # VP Engineering - Female voice
    SAM_MALE = "sam_male"        # Distinguished Engineer - Male voice
    SAM_FEMALE = "sam_female"    # Distinguished Engineer - Female voice

# --- Pydantic Models ---

class DialogueTurn(BaseModel):
    """Single turn in the podcast dialogue."""
    speaker: str  # "alex" or "sam"
    text: str
    emphasis: Optional[str] = None  # "excited", "thoughtful", "concerned"
    pause_after: float = 0.5  # seconds

class PodcastSection(BaseModel):
    """Section of the podcast with dialogue turns."""
    section_type: str  # "intro", "strategic", "technical", "trend", "outro"
    title: str
    dialogue: list[DialogueTurn]
    sources_cited: list[int] = []  # Newsletter IDs referenced

class PodcastScript(BaseModel):
    """Complete podcast script ready for TTS."""
    title: str
    length: PodcastLength
    estimated_duration_seconds: int
    word_count: int
    sections: list[PodcastSection]
    intro: PodcastSection
    outro: PodcastSection
    sources_summary: list[dict]  # [{id, title, publication, url}]

class PodcastRequest(BaseModel):
    """Request to generate a podcast from a digest."""
    digest_id: int
    length: PodcastLength = PodcastLength.STANDARD
    enable_web_search: bool = True  # Allow model to use web search tool
    voice_provider: VoiceProvider = VoiceProvider.ELEVENLABS
    alex_voice: VoicePersona = VoicePersona.ALEX_MALE  # Voice for Alex persona
    sam_voice: VoicePersona = VoicePersona.SAM_FEMALE  # Voice for Sam persona
    custom_focus_topics: list[str] = []  # Optional topic emphasis
    # Note: Original newsletter text is fetched on-demand via tool, not pre-loaded

# --- Database Models ---

class PodcastScriptRecord(Base):
    """Cached podcast script - can be reused for multiple audio generations."""
    __tablename__ = "podcast_scripts"

    id = Column(Integer, primary_key=True)
    digest_id = Column(Integer, ForeignKey("digests.id"), nullable=False)
    length = Column(SQLEnum(PodcastLength), nullable=False)

    # Script content
    title = Column(String(500))
    script_json = Column(JSON)  # PodcastScript Pydantic model serialized
    word_count = Column(Integer)
    estimated_duration_seconds = Column(Integer)

    # Review workflow
    status = Column(SQLEnum(PodcastStatus), default=PodcastStatus.SCRIPT_PENDING_REVIEW)
    reviewed_by = Column(String(100))
    reviewed_at = Column(DateTime)
    review_notes = Column(Text)
    revision_count = Column(Integer, default=0)
    revision_history = Column(JSON)  # List of {section, original, revised, feedback, timestamp}

    # Context & Tool Usage Tracking
    newsletter_ids_available = Column(JSON)  # All newsletter IDs in digest period
    newsletter_ids_fetched = Column(JSON)  # IDs fetched via get_newsletter_content tool
    theme_ids = Column(JSON)  # Themes incorporated
    web_search_queries = Column(JSON)  # Web searches performed via tool
    tool_call_count = Column(Integer)  # Total tool invocations

    # Generation metadata
    model_used = Column(String(100))
    model_version = Column(String(50))
    token_usage = Column(JSON)
    processing_time_seconds = Column(Integer)
    error_message = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime)

    # Relationships
    digest = relationship("Digest", backref="podcast_scripts")
    podcasts = relationship("Podcast", back_populates="script")


class Podcast(Base):
    """Podcast audio generated from an approved script."""
    __tablename__ = "podcasts"

    id = Column(Integer, primary_key=True)
    script_id = Column(Integer, ForeignKey("podcast_scripts.id"), nullable=False)

    # Audio output
    audio_url = Column(String(1000))  # Local path (S3/SharePoint future)
    audio_format = Column(String(20), default="mp3")
    duration_seconds = Column(Integer)
    file_size_bytes = Column(Integer)

    # Voice configuration
    voice_provider = Column(SQLEnum(VoiceProvider))
    alex_voice = Column(SQLEnum(VoicePersona))
    sam_voice = Column(SQLEnum(VoicePersona))
    voice_config = Column(JSON)  # Provider-specific voice IDs used

    # Status
    status = Column(String(50), default="generating")  # generating, completed, failed
    error_message = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # Relationships
    script = relationship("PodcastScriptRecord", back_populates="podcasts")
```

### 1.2 Configuration Updates

**Add to `src/config/settings.py`:**

```python
# Podcast / TTS Configuration
PODCAST_VOICE_PROVIDER: VoiceProvider = VoiceProvider.ELEVENLABS
PODCAST_OUTPUT_FORMAT: str = "mp3"
PODCAST_SAMPLE_RATE: int = 44100

# Voice Persona Mappings (provider-specific voice IDs)
# Each persona has male and female variants
VOICE_PERSONA_CONFIG: dict = {
    VoiceProvider.ELEVENLABS: {
        VoicePersona.ALEX_MALE: "voice-id-alex-male",      # Configure with actual IDs
        VoicePersona.ALEX_FEMALE: "voice-id-alex-female",
        VoicePersona.SAM_MALE: "voice-id-sam-male",
        VoicePersona.SAM_FEMALE: "voice-id-sam-female",
    },
    VoiceProvider.OPENAI_TTS: {
        VoicePersona.ALEX_MALE: "onyx",
        VoicePersona.ALEX_FEMALE: "nova",
        VoicePersona.SAM_MALE: "fable",
        VoicePersona.SAM_FEMALE: "shimmer",
    },
    VoiceProvider.GOOGLE_TTS: {
        VoicePersona.ALEX_MALE: "en-US-Studio-M",
        VoicePersona.ALEX_FEMALE: "en-US-Studio-O",
        VoicePersona.SAM_MALE: "en-US-Studio-Q",
        VoicePersona.SAM_FEMALE: "en-US-Studio-N",
    },
    VoiceProvider.AWS_POLLY: {
        VoicePersona.ALEX_MALE: "Matthew",
        VoicePersona.ALEX_FEMALE: "Joanna",
        VoicePersona.SAM_MALE: "Stephen",
        VoicePersona.SAM_FEMALE: "Salli",
    },
}

# Provider API Keys
ELEVENLABS_API_KEY: str = ""
GOOGLE_TTS_CREDENTIALS: str = ""
AWS_POLLY_REGION: str = "us-east-1"

# Podcast Content Settings
PODCAST_WORDS_PER_MINUTE: int = 150  # Average speaking rate
PODCAST_STORAGE_PATH: str = "data/podcasts"  # Local storage

# Future Extensions (not implemented)
# PODCAST_INCLUDE_MUSIC: bool = False  # Intro/outro music
# PODCAST_S3_BUCKET: str = ""  # S3 storage
# PODCAST_SHAREPOINT_PATH: str = ""  # SharePoint/OneDrive storage
```

**Add to `src/config/models.py` - New ModelStep:**

```python
class ModelStep(str, Enum):
    # ... existing steps ...
    PODCAST_SCRIPT = "podcast_script"  # Script generation from digest
```

**Add to `.env.example`:**

```bash
# Podcast / TTS Configuration
PODCAST_VOICE_PROVIDER=elevenlabs
ELEVENLABS_API_KEY=your-elevenlabs-api-key
ELEVENLABS_VOICE_ALEX=voice-id-for-alex
ELEVENLABS_VOICE_SAM=voice-id-for-sam

# Model for podcast script generation
MODEL_PODCAST_SCRIPT=claude-sonnet-4-5
```

---

## Phase 2: Script Generation Processor

### 2.1 New Processor (`src/processors/podcast_script_generator.py`)

**Key Responsibilities:**
1. Load digest with all context (summaries, themes, original text)
2. Optionally perform web search for grounding
3. Generate conversational script between two personas
4. Structure output for TTS processing

**Length-Based Content Strategy:**

| Length | Duration | Word Count | Content Scope |
|--------|----------|------------|---------------|
| Brief | 5 min | ~750-1000 | Executive overview + 2-3 top insights |
| Standard | 15 min | ~2250-3000 | Overview + strategic + technical highlights + 1 trend |
| Extended | 30 min | ~4500-6000 | Full digest + original newsletter excerpts + web context |

**Content Sources by Length:**

| Source | Brief | Standard | Extended |
|--------|-------|----------|----------|
| Digest executive_overview | ✓ | ✓ | ✓ |
| Digest strategic_insights | Top 2 | Top 4 | All |
| Digest technical_developments | - | Top 3 | All |
| Digest emerging_trends | - | Top 1 | All |
| Digest actionable_recommendations | - | Key 3 | All |
| Newsletter summaries (metadata) | ✓ | ✓ | ✓ |
| Newsletter full text (via tool) | On-demand | On-demand | On-demand |
| Graphiti themes | Top 3 | Top 5 | All |
| Historical context | - | Key 2 | All |
| Web search grounding | - | Optional | ✓ |
| Relevant links | - | Top 5 | All |

**Tool-Based Newsletter Access:**

Original newsletter content is NOT included in the initial context. Instead, the model is provided with:
1. A list of available newsletters (ID, title, publication, date, summary preview)
2. A `get_newsletter_content` tool to fetch full text on-demand

This approach:
- Reduces initial context size significantly
- Lets the model decide which newsletters are worth quoting directly
- Enables smarter token budget management
- Works consistently across all lengths (model decides depth)

### 2.2 Script Generation Prompt Design

```python
PODCAST_SCRIPT_SYSTEM_PROMPT = """
You are a podcast script writer creating an engaging dialogue between two technology experts
discussing AI, Data, and Software development news relevant to a large media/tech company.

PERSONAS:

**Alex Chen** (VP of Engineering):
- 20+ years in technology leadership at Fortune 500 companies
- Focuses on: strategic implications, organizational impact, competitive dynamics
- Speaking style: Confident, strategic, occasionally uses business metaphors
- Often asks: "What does this mean for our technology roadmap?"
- Provides perspective on: investment priorities, team structure, vendor relationships

**Dr. Sam Rodriguez** (Distinguished Engineer):
- PhD in Computer Science, 15+ years building large-scale systems
- Focuses on: implementation details, architectural patterns, developer experience
- Speaking style: Thoughtful, precise, enthusiastic about elegant solutions
- Often asks: "How would we actually implement this?"
- Provides perspective on: technical feasibility, engineering trade-offs, adoption challenges

CONVERSATION DYNAMICS:
- Natural back-and-forth with interruptions, agreements, and friendly debates
- Alex often opens topics with business context, Sam adds technical depth
- They reference each other's points ("Building on what Sam said...")
- Include moments of genuine curiosity and discovery
- Occasional humor and real-world analogies
- Reference Comcast and industry competitors where relevant

OUTPUT FORMAT:
Generate a structured JSON podcast script with dialogue turns.
Each turn should include:
- speaker: "alex" or "sam"
- text: The spoken content (natural, conversational)
- emphasis: Optional emotional tone ("excited", "thoughtful", "concerned", "amused")
- pause_after: Seconds of pause (0.3-2.0)

CONTENT REQUIREMENTS:
- Always cite sources using newsletter titles or publications
- Include specific details, numbers, and examples from the source material
- Connect news to practical implications for engineering organizations
- Highlight connections between topics when they exist
- End with clear takeaways or actions

AVAILABLE TOOLS:
You have access to the following tools to enrich your script:

1. **get_newsletter_content(newsletter_id: int) -> str**
   Retrieves the full original text of a newsletter by ID.
   Use this when you want to:
   - Quote directly from a source for impact
   - Get more context on a specific story
   - Verify details before making claims
   - Find compelling examples or data points

2. **web_search(query: str) -> list[SearchResult]**
   Searches the web for recent information.
   Use this when you want to:
   - Get the latest updates on breaking stories
   - Find competitor reactions or announcements
   - Verify claims with external sources
   - Add context about companies or technologies mentioned

Use tools judiciously based on podcast length:
- Brief (5 min): Use sparingly, only for key quotes
- Standard (15 min): Use for 2-3 deep-dive moments
- Extended (30 min): Use freely to enrich content
"""

PODCAST_SCRIPT_LENGTH_PROMPTS = {
    PodcastLength.BRIEF: """
Generate a 5-minute podcast script (~750-1000 words).

Structure:
1. INTRO (30 seconds): Hook with the most important news
2. TOP STORIES (3.5 minutes): 2-3 key insights with brief discussion
3. OUTRO (1 minute): Quick takeaways and sign-off

Focus on: Executive-level insights, "what matters most this {period}"
Skip: Deep technical details, extensive background
""",

    PodcastLength.STANDARD: """
Generate a 15-minute podcast script (~2250-3000 words).

Structure:
1. INTRO (1 minute): Welcome, overview of key themes
2. STRATEGIC SECTION (4 minutes): 3-4 strategic insights with discussion
3. TECHNICAL SECTION (5 minutes): 2-3 technical developments with depth
4. EMERGING TRENDS (3 minutes): 1-2 new developments
5. TAKEAWAYS (1.5 minutes): Action items for leaders and practitioners
6. OUTRO (0.5 minutes): Sign-off

Balance: Equal strategic and technical depth
Include: Relevant links and further reading mentions
""",

    PodcastLength.EXTENDED: """
Generate a 30-minute podcast script (~4500-6000 words).

Structure:
1. INTRO (2 minutes): Comprehensive overview of the {period}
2. DEEP DIVE 1 (6 minutes): Most significant development with full context
3. STRATEGIC ROUNDUP (6 minutes): All strategic insights
4. TECHNICAL ROUNDUP (8 minutes): All technical developments with implementation discussion
5. EMERGING TRENDS (4 minutes): New developments with historical context
6. ACTIONABLE INSIGHTS (3 minutes): Role-specific recommendations
7. OUTRO (1 minute): Summary and sign-off

Include:
- Excerpts from original newsletters where compelling
- Web search context for recent developments
- Full historical theme evolution
- All relevant links with context
- Competitor and industry analysis
"""
}
```

### 2.3 Context Assembly (Tool-Based Approach)

The script generator uses an agentic approach where the LLM has access to tools for fetching additional content on-demand, rather than pre-loading all newsletter content.

```python
class PodcastScriptGenerator:
    """Generate podcast scripts from digests using tool-based content retrieval."""

    def __init__(self):
        self.model_config = ModelConfig()
        self.model = self.model_config.get_model_for_step(ModelStep.PODCAST_SCRIPT)
        self.graphiti = GraphitiClient()

    async def generate_script(
        self,
        request: PodcastRequest
    ) -> PodcastScript:
        """Generate a podcast script from a digest."""

        # 1. Load digest and lightweight context (NO full newsletter text)
        context = await self._assemble_lightweight_context(request)

        # 2. Define tools for the LLM to call on-demand
        tools = self._create_tools(context)

        # 3. Generate script via agentic LLM loop (with tool use)
        script = await self._generate_script_with_tools(context, tools, request.length)

        # 4. Validate and enhance script
        script = self._validate_and_enhance(script)

        return script

    async def _assemble_lightweight_context(self, request: PodcastRequest) -> PodcastContext:
        """Assemble lightweight context - metadata only, no full newsletter text."""

        with get_db() as db:
            # Load digest (structured data)
            digest = db.query(Digest).filter(Digest.id == request.digest_id).first()

            # Load newsletter METADATA only (not full text)
            newsletters = db.query(Newsletter).filter(
                Newsletter.published_date >= digest.period_start,
                Newsletter.published_date <= digest.period_end,
                Newsletter.status == ProcessingStatus.COMPLETED
            ).all()

            # Create lightweight newsletter list for the prompt
            newsletter_metadata = [
                {
                    "id": n.id,
                    "title": n.title,
                    "publication": n.publication,
                    "date": n.published_date.isoformat(),
                    "url": n.url
                }
                for n in newsletters
            ]

            # Load summaries (these ARE included - they're already condensed)
            newsletter_ids = [n.id for n in newsletters]
            summaries = db.query(NewsletterSummary).filter(
                NewsletterSummary.newsletter_id.in_(newsletter_ids)
            ).all()

            # Load theme analysis
            theme_analysis = db.query(ThemeAnalysis).filter(
                ThemeAnalysis.start_date >= digest.period_start,
                ThemeAnalysis.end_date <= digest.period_end
            ).order_by(ThemeAnalysis.created_at.desc()).first()

        # Query Graphiti for theme context
        graphiti_themes = await self.graphiti.extract_themes_from_range(
            start_date=digest.period_start,
            end_date=digest.period_end
        )

        return PodcastContext(
            digest=digest,
            newsletter_metadata=newsletter_metadata,  # Lightweight!
            summaries=summaries,
            theme_analysis=theme_analysis,
            graphiti_themes=graphiti_themes,
            length=request.length
        )

    def _create_tools(self, context: PodcastContext) -> list[Tool]:
        """Create tools for on-demand content retrieval."""

        return [
            Tool(
                name="get_newsletter_content",
                description="Retrieve the full original text of a newsletter by ID. "
                           "Use when you need direct quotes, more context, or specific details.",
                parameters={
                    "type": "object",
                    "properties": {
                        "newsletter_id": {
                            "type": "integer",
                            "description": "The ID of the newsletter to retrieve"
                        }
                    },
                    "required": ["newsletter_id"]
                },
                handler=self._handle_get_newsletter_content
            ),
            Tool(
                name="web_search",
                description="Search the web for recent information about a topic. "
                           "Use for latest updates, competitor info, or external context.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query"
                        }
                    },
                    "required": ["query"]
                },
                handler=self._handle_web_search
            )
        ]

    async def _handle_get_newsletter_content(self, newsletter_id: int) -> str:
        """Tool handler: Fetch full newsletter content from database."""
        with get_db() as db:
            newsletter = db.query(Newsletter).filter(
                Newsletter.id == newsletter_id
            ).first()

            if not newsletter:
                return f"Newsletter with ID {newsletter_id} not found."

            # Return cleaned text content
            return f"""
Newsletter: {newsletter.title}
Publication: {newsletter.publication}
Date: {newsletter.published_date}

Content:
{newsletter.raw_text[:15000]}  # Limit to avoid context overflow
"""

    async def _handle_web_search(self, query: str) -> str:
        """Tool handler: Perform web search."""
        results = await self.web_search_service.search(query, num_results=3)
        return "\n\n".join([
            f"**{r.title}**\n{r.snippet}\nSource: {r.url}"
            for r in results
        ])

    async def _generate_script_with_tools(
        self,
        context: PodcastContext,
        tools: list[Tool],
        length: PodcastLength
    ) -> PodcastScript:
        """Run agentic loop with tool use to generate script."""

        # Build initial prompt with lightweight context
        system_prompt = PODCAST_SCRIPT_SYSTEM_PROMPT
        user_prompt = self._build_user_prompt(context, length)

        # Agentic loop - model can call tools as needed
        messages = [{"role": "user", "content": user_prompt}]

        while True:
            response = await self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=messages,
                tools=[t.to_dict() for t in tools],
                max_tokens=12000
            )

            # Check if model wants to use tools
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await self._execute_tool(block, tools)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                # Model finished - extract script from response
                return self._parse_script_response(response)

    def _build_user_prompt(self, context: PodcastContext, length: PodcastLength) -> str:
        """Build the user prompt with lightweight context."""

        return f"""
Create a {length.value} podcast script for the {context.digest.digest_type.value} digest.

## Digest Overview
**Title:** {context.digest.title}
**Period:** {context.digest.period_start} to {context.digest.period_end}

**Executive Overview:**
{context.digest.executive_overview}

**Strategic Insights:**
{json.dumps(context.digest.strategic_insights, indent=2)}

**Technical Developments:**
{json.dumps(context.digest.technical_developments, indent=2)}

**Emerging Trends:**
{json.dumps(context.digest.emerging_trends, indent=2)}

## Available Newsletters
You can use the `get_newsletter_content` tool to retrieve full text for any of these:

{self._format_newsletter_list(context.newsletter_metadata)}

## Newsletter Summaries
{self._format_summaries(context.summaries)}

## Themes from Knowledge Graph
{self._format_themes(context.graphiti_themes)}

## Instructions
{PODCAST_SCRIPT_LENGTH_PROMPTS[length]}

Generate the podcast script. Use the tools to fetch newsletter content or web search
when you need more detail for compelling quotes or to verify/enrich specific points.
"""
```

### 2.4 Tool Usage Tracking

Track which tools were called during generation for transparency and debugging:

```python
class PodcastGenerationMetadata(BaseModel):
    """Metadata about podcast script generation."""
    newsletter_fetches: list[int]  # Newsletter IDs fetched via tool
    web_searches: list[str]  # Search queries executed
    tool_call_count: int
    total_tokens_used: int
```

---

## Phase 3: Audio Generation

### 3.1 TTS Service Abstraction (`src/delivery/tts_service.py`)

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
import aiohttp

class TTSProvider(ABC):
    """Abstract base for TTS providers."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        **kwargs
    ) -> bytes:
        """Synthesize text to audio bytes."""
        pass

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        voice_id: str,
        **kwargs
    ) -> AsyncIterator[bytes]:
        """Stream audio synthesis for long content."""
        pass


class ElevenLabsTTS(TTSProvider):
    """ElevenLabs TTS implementation."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.elevenlabs.io/v1"

    async def synthesize(self, text: str, voice_id: str, **kwargs) -> bytes:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/text-to-speech/{voice_id}",
                headers={"xi-api-key": self.api_key},
                json={
                    "text": text,
                    "model_id": kwargs.get("model_id", "eleven_turbo_v2"),
                    "voice_settings": {
                        "stability": kwargs.get("stability", 0.5),
                        "similarity_boost": kwargs.get("similarity_boost", 0.75)
                    }
                }
            ) as response:
                return await response.read()


class OpenAITTS(TTSProvider):
    """OpenAI TTS implementation."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def synthesize(self, text: str, voice_id: str, **kwargs) -> bytes:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key)

        response = await client.audio.speech.create(
            model="tts-1-hd",
            voice=voice_id,
            input=text
        )
        return response.content


class GoogleTTS(TTSProvider):
    """Google Cloud TTS implementation."""
    # Implementation using google-cloud-texttospeech
    pass


class AWSPollyTTS(TTSProvider):
    """AWS Polly TTS implementation."""
    # Implementation using boto3
    pass
```

### 3.2 Audio Generator (`src/delivery/audio_generator.py`)

```python
import io
from pathlib import Path
from pydub import AudioSegment

class PodcastAudioGenerator:
    """Generate podcast audio from scripts."""

    def __init__(self, provider: VoiceProvider):
        self.tts = self._get_tts_provider(provider)
        self.settings = get_settings()

    def _get_tts_provider(self, provider: VoiceProvider) -> TTSProvider:
        if provider == VoiceProvider.ELEVENLABS:
            return ElevenLabsTTS(self.settings.ELEVENLABS_API_KEY)
        elif provider == VoiceProvider.OPENAI_TTS:
            return OpenAITTS(self.settings.OPENAI_API_KEY)
        # ... other providers

    async def generate_audio(
        self,
        script: PodcastScript,
        output_path: Path
    ) -> AudioMetadata:
        """Generate full podcast audio from script."""

        audio_segments = []

        for section in script.sections:
            for turn in section.dialogue:
                # Get voice ID for speaker
                voice_id = self._get_voice_for_speaker(turn.speaker)

                # Synthesize speech
                audio_bytes = await self.tts.synthesize(
                    text=turn.text,
                    voice_id=voice_id
                )

                # Convert to AudioSegment
                segment = AudioSegment.from_mp3(io.BytesIO(audio_bytes))
                audio_segments.append(segment)

                # Add pause
                pause_ms = int(turn.pause_after * 1000)
                audio_segments.append(AudioSegment.silent(duration=pause_ms))

        # Combine all segments
        final_audio = sum(audio_segments)

        # Export
        final_audio.export(output_path, format="mp3")

        return AudioMetadata(
            duration_seconds=len(final_audio) // 1000,
            file_size_bytes=output_path.stat().st_size,
            format="mp3"
        )

    def _get_voice_for_speaker(self, speaker: str, alex_voice: VoicePersona, sam_voice: VoicePersona) -> str:
        """Get provider-specific voice ID for a speaker."""
        persona = alex_voice if speaker == "alex" else sam_voice
        return self.settings.VOICE_PERSONA_CONFIG[self.provider][persona]
```

---

## Phase 4: Script Review Workflow

The script review workflow allows human review and section-based refinement before audio generation.

### 4.1 Script Review Models (`src/models/podcast.py` additions)

```python
class ScriptRevisionRequest(BaseModel):
    """Request to revise a specific section of a script."""
    script_id: int
    section_index: int  # Index into sections list
    feedback: str  # User feedback for this section
    # If provided, replace section entirely; if not, AI will refine based on feedback
    replacement_dialogue: Optional[list[DialogueTurn]] = None

class ScriptReviewAction(str, Enum):
    APPROVE = "approve"
    REQUEST_REVISION = "request_revision"
    REJECT = "reject"

class ScriptReviewRequest(BaseModel):
    """Request to review a complete script."""
    script_id: int
    action: ScriptReviewAction
    reviewer: str
    # Section-specific feedback (key = section index)
    section_feedback: dict[int, str] = {}
    general_notes: Optional[str] = None
```

### 4.2 Script Reviser Processor (`src/processors/script_reviser.py`)

```python
class PodcastScriptReviser:
    """Revise specific sections of a podcast script based on feedback."""

    def __init__(self):
        self.model_config = ModelConfig()
        self.model = self.model_config.get_model_for_step(ModelStep.PODCAST_SCRIPT)

    async def revise_section(
        self,
        script_record: PodcastScriptRecord,
        section_index: int,
        feedback: str
    ) -> PodcastSection:
        """Revise a single section based on feedback, leaving others unchanged."""

        script = PodcastScript.model_validate(script_record.script_json)
        section = script.sections[section_index]

        # Build revision prompt
        prompt = f"""
You are revising a section of a podcast script based on reviewer feedback.

CURRENT SECTION ({section.section_type}):
Title: {section.title}

Dialogue:
{self._format_dialogue(section.dialogue)}

REVIEWER FEEDBACK:
{feedback}

INSTRUCTIONS:
1. Revise ONLY this section to address the feedback
2. Maintain the same speakers (Alex and Sam)
3. Keep the conversational style and persona voices
4. Preserve any source citations
5. Return the revised section in the same JSON format

Respond with the revised section only.
"""

        response = await self.client.messages.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000
        )

        revised_section = self._parse_section_response(response)
        return revised_section

    async def apply_revision(
        self,
        script_id: int,
        section_index: int,
        feedback: str
    ) -> PodcastScriptRecord:
        """Apply a revision and update the script record."""

        with get_db() as db:
            script_record = db.query(PodcastScriptRecord).get(script_id)

            # Get current script
            script = PodcastScript.model_validate(script_record.script_json)
            original_section = script.sections[section_index]

            # Generate revision
            revised_section = await self.revise_section(script_record, section_index, feedback)

            # Update script with revised section
            script.sections[section_index] = revised_section

            # Track revision history
            revision_entry = {
                "section_index": section_index,
                "section_type": original_section.section_type,
                "original_title": original_section.title,
                "feedback": feedback,
                "timestamp": datetime.utcnow().isoformat(),
            }
            history = script_record.revision_history or []
            history.append(revision_entry)

            # Update record
            script_record.script_json = script.model_dump()
            script_record.revision_history = history
            script_record.revision_count = (script_record.revision_count or 0) + 1
            script_record.status = PodcastStatus.SCRIPT_PENDING_REVIEW

            db.commit()
            db.refresh(script_record)

            return script_record
```

### 4.3 Script Review Service (`src/services/script_review_service.py`)

```python
class ScriptReviewService:
    """Service for managing script review workflow."""

    def __init__(self):
        self.reviser = PodcastScriptReviser()

    async def submit_review(
        self,
        request: ScriptReviewRequest
    ) -> PodcastScriptRecord:
        """Submit a review for a script."""

        with get_db() as db:
            script_record = db.query(PodcastScriptRecord).get(request.script_id)

            if request.action == ScriptReviewAction.APPROVE:
                script_record.status = PodcastStatus.SCRIPT_APPROVED
                script_record.reviewed_by = request.reviewer
                script_record.reviewed_at = datetime.utcnow()
                script_record.review_notes = request.general_notes
                script_record.approved_at = datetime.utcnow()

            elif request.action == ScriptReviewAction.REQUEST_REVISION:
                script_record.status = PodcastStatus.SCRIPT_REVISION_REQUESTED
                script_record.reviewed_by = request.reviewer
                script_record.reviewed_at = datetime.utcnow()
                script_record.review_notes = request.general_notes

                # Store section feedback for revision
                script_record.pending_feedback = request.section_feedback

            elif request.action == ScriptReviewAction.REJECT:
                script_record.status = PodcastStatus.FAILED
                script_record.reviewed_by = request.reviewer
                script_record.review_notes = request.general_notes

            db.commit()
            db.refresh(script_record)

        # If revision requested, apply revisions for each section with feedback
        if request.action == ScriptReviewAction.REQUEST_REVISION:
            for section_idx, feedback in request.section_feedback.items():
                script_record = await self.reviser.apply_revision(
                    request.script_id,
                    int(section_idx),
                    feedback
                )

        return script_record

    def get_script_for_review(self, script_id: int) -> dict:
        """Get script with review-friendly formatting."""

        with get_db() as db:
            script_record = db.query(PodcastScriptRecord).get(script_id)
            script = PodcastScript.model_validate(script_record.script_json)

        # Format for review UI
        return {
            "id": script_record.id,
            "title": script.title,
            "length": script.length.value,
            "word_count": script.word_count,
            "estimated_duration": f"{script.estimated_duration_seconds // 60} min",
            "status": script_record.status.value,
            "revision_count": script_record.revision_count,
            "sections": [
                {
                    "index": i,
                    "type": s.section_type,
                    "title": s.title,
                    "dialogue": [
                        {
                            "speaker": t.speaker.upper(),
                            "text": t.text,
                            "emphasis": t.emphasis
                        }
                        for t in s.dialogue
                    ],
                    "sources_cited": s.sources_cited
                }
                for i, s in enumerate(script.sections)
            ],
            "revision_history": script_record.revision_history or []
        }
```

---

## Phase 5: Pipeline Integration

### 5.1 Two-Phase Podcast Creation

The podcast creation is now split into two separate operations:

```python
class PodcastCreator:
    """Orchestrate podcast creation with review workflow."""

    def __init__(self):
        self.script_generator = PodcastScriptGenerator()
        self.audio_generator = None
        self.review_service = ScriptReviewService()

    # PHASE 1: Generate script (stops at pending review)
    async def generate_script(self, request: PodcastRequest) -> PodcastScriptRecord:
        """Generate script and save for review. Does NOT generate audio."""

        script_record = PodcastScriptRecord(
            digest_id=request.digest_id,
            length=request.length,
            status=PodcastStatus.SCRIPT_GENERATING
        )

        with get_db() as db:
            db.add(script_record)
            db.commit()
            db.refresh(script_record)
            script_id = script_record.id

        try:
            # Generate script
            script = await self.script_generator.generate_script(request)

            with get_db() as db:
                script_record = db.query(PodcastScriptRecord).get(script_id)
                script_record.script_json = script.model_dump()
                script_record.title = script.title
                script_record.word_count = script.word_count
                script_record.estimated_duration_seconds = script.estimated_duration_seconds
                script_record.status = PodcastStatus.SCRIPT_PENDING_REVIEW
                db.commit()
                db.refresh(script_record)

            return script_record

        except Exception as e:
            with get_db() as db:
                script_record = db.query(PodcastScriptRecord).get(script_id)
                script_record.status = PodcastStatus.FAILED
                script_record.error_message = str(e)
                db.commit()
            raise

    # PHASE 2: Generate audio (only for approved scripts)
    async def generate_audio(
        self,
        script_id: int,
        voice_provider: VoiceProvider,
        alex_voice: VoicePersona,
        sam_voice: VoicePersona
    ) -> Podcast:
        """Generate audio from an approved script."""

        with get_db() as db:
            script_record = db.query(PodcastScriptRecord).get(script_id)

            if script_record.status != PodcastStatus.SCRIPT_APPROVED:
                raise ValueError(f"Script must be approved before audio generation. Current status: {script_record.status}")

            # Create podcast record
            podcast = Podcast(
                script_id=script_id,
                voice_provider=voice_provider,
                alex_voice=alex_voice,
                sam_voice=sam_voice,
                status="generating"
            )
            db.add(podcast)
            db.commit()
            db.refresh(podcast)
            podcast_id = podcast.id

        try:
            script = PodcastScript.model_validate(script_record.script_json)

            # Generate audio
            self.audio_generator = PodcastAudioGenerator(
                provider=voice_provider,
                alex_voice=alex_voice,
                sam_voice=sam_voice
            )
            output_path = self._get_output_path(podcast_id)

            audio_meta = await self.audio_generator.generate_audio(script, output_path)

            with get_db() as db:
                podcast = db.query(Podcast).get(podcast_id)
                podcast.audio_url = str(output_path)
                podcast.audio_format = audio_meta.format
                podcast.duration_seconds = audio_meta.duration_seconds
                podcast.file_size_bytes = audio_meta.file_size_bytes
                podcast.status = "completed"
                podcast.completed_at = datetime.utcnow()
                db.commit()
                db.refresh(podcast)

            return podcast

        except Exception as e:
            with get_db() as db:
                podcast = db.query(Podcast).get(podcast_id)
                podcast.status = "failed"
                podcast.error_message = str(e)
                db.commit()
            raise

    def _get_output_path(self, podcast_id: int) -> Path:
        """Get local storage path for podcast audio."""
        storage_dir = Path(self.settings.PODCAST_STORAGE_PATH)
        storage_dir.mkdir(parents=True, exist_ok=True)
        return storage_dir / f"podcast_{podcast_id}.mp3"
```

### 5.2 CLI Integration (`scripts/run_pipeline.py`)

Podcast generation is on-demand only (not auto-triggered with digest creation):

```python
# Script generation (Phase 1)
parser.add_argument(
    "--podcast-script",
    nargs="?",
    const="standard",
    choices=["brief", "standard", "extended", "all"],
    help="Generate podcast script for review (does NOT generate audio)"
)

# Audio generation (Phase 2 - requires approved script)
parser.add_argument(
    "--podcast-audio",
    type=int,
    metavar="SCRIPT_ID",
    help="Generate audio from an approved script ID"
)

parser.add_argument(
    "--podcast-provider",
    default="openai_tts",
    choices=["elevenlabs", "openai_tts", "google_tts", "aws_polly"],
    help="TTS provider for podcast audio"
)

parser.add_argument(
    "--alex-voice",
    default="alex_male",
    choices=["alex_male", "alex_female"],
    help="Voice for Alex persona"
)

parser.add_argument(
    "--sam-voice",
    default="sam_female",
    choices=["sam_male", "sam_female"],
    help="Voice for Sam persona"
)

# In pipeline execution:
if args.podcast_script and self.stats.get("digest_id"):
    lengths = [PodcastLength.BRIEF, PodcastLength.STANDARD, PodcastLength.EXTENDED] \
              if args.podcast_script == "all" \
              else [PodcastLength(args.podcast_script)]

    for length in lengths:
        request = PodcastRequest(
            digest_id=self.stats["digest_id"],
            length=length
        )
        script = await self.podcast_creator.generate_script(request)
        print(f"Script {script.id} generated. Status: {script.status}")
        print(f"Review at: /api/scripts/{script.id}/review")
        self.stats["podcast_scripts"].append(script.id)

if args.podcast_audio:
    podcast = await self.podcast_creator.generate_audio(
        script_id=args.podcast_audio,
        voice_provider=VoiceProvider(args.podcast_provider),
        alex_voice=VoicePersona(args.alex_voice),
        sam_voice=VoicePersona(args.sam_voice)
    )
    print(f"Podcast audio generated: {podcast.audio_url}")
```

---

## Phase 6: API & Delivery

### 6.1 Script API Endpoints (`src/api/script_routes.py`)

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException

router = APIRouter(prefix="/scripts", tags=["podcast-scripts"])

@router.post("/generate")
async def generate_script(
    request: PodcastRequest,
    background_tasks: BackgroundTasks
) -> dict:
    """Generate a podcast script from a digest (Phase 1)."""
    background_tasks.add_task(generate_script_task, request)
    return {"status": "queued", "message": "Script generation started"}

@router.get("/{script_id}")
async def get_script(script_id: int) -> dict:
    """Get script with full details for review."""
    return review_service.get_script_for_review(script_id)

@router.get("/{script_id}/sections")
async def get_script_sections(script_id: int) -> list[dict]:
    """Get script sections only (for section-by-section review)."""
    pass

@router.post("/{script_id}/review")
async def submit_review(
    script_id: int,
    request: ScriptReviewRequest
) -> dict:
    """Submit review with optional section-specific feedback."""
    script = await review_service.submit_review(request)
    return {
        "script_id": script.id,
        "status": script.status.value,
        "revision_count": script.revision_count
    }

@router.post("/{script_id}/sections/{section_index}/revise")
async def revise_section(
    script_id: int,
    section_index: int,
    feedback: str
) -> dict:
    """Revise a single section based on feedback."""
    script = await reviser.apply_revision(script_id, section_index, feedback)
    return {
        "script_id": script.id,
        "section_revised": section_index,
        "status": script.status.value
    }

@router.get("/pending-review")
async def list_pending_scripts() -> list[dict]:
    """List all scripts pending review."""
    pass

@router.get("/digest/{digest_id}")
async def list_scripts_for_digest(digest_id: int) -> list[dict]:
    """List all scripts generated from a digest."""
    pass
```

### 6.2 Audio API Endpoints (`src/api/podcast_routes.py`)

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/podcasts", tags=["podcasts"])

@router.post("/generate")
async def generate_audio(
    script_id: int,
    voice_provider: VoiceProvider = VoiceProvider.OPENAI_TTS,
    alex_voice: VoicePersona = VoicePersona.ALEX_MALE,
    sam_voice: VoicePersona = VoicePersona.SAM_FEMALE,
    background_tasks: BackgroundTasks = None
) -> dict:
    """Generate audio from an approved script (Phase 2)."""
    # Verify script is approved
    script = get_script(script_id)
    if script.status != PodcastStatus.SCRIPT_APPROVED:
        raise HTTPException(400, "Script must be approved before audio generation")

    background_tasks.add_task(
        generate_audio_task, script_id, voice_provider, alex_voice, sam_voice
    )
    return {"status": "queued", "message": "Audio generation started"}

@router.get("/{podcast_id}")
async def get_podcast(podcast_id: int) -> Podcast:
    """Get podcast metadata by ID."""
    pass

@router.get("/{podcast_id}/audio")
async def stream_audio(podcast_id: int) -> FileResponse:
    """Stream podcast audio file."""
    podcast = get_podcast(podcast_id)
    return FileResponse(
        podcast.audio_url,
        media_type="audio/mpeg",
        filename=f"podcast_{podcast_id}.mp3"
    )

@router.get("/{podcast_id}/transcript")
async def get_transcript(podcast_id: int) -> dict:
    """Get podcast transcript (from script)."""
    pass

@router.get("/script/{script_id}")
async def list_podcasts_for_script(script_id: int) -> list[Podcast]:
    """List all audio versions generated from a script."""
    pass
```

---

## Phase 7: Testing Strategy

### 7.1 Unit Tests

```
tests/
├── test_models/
│   └── test_podcast.py           # Podcast model tests
├── test_processors/
│   └── test_podcast_script_generator.py
├── test_delivery/
│   ├── test_tts_service.py       # Mock TTS provider tests
│   └── test_audio_generator.py
└── test_api/
    └── test_podcast_routes.py
```

### 7.2 Integration Tests

```python
# tests/integration/test_podcast_pipeline.py

async def test_script_generation_and_review():
    """Test script generation and review workflow."""
    digest = create_test_digest()

    # Phase 1: Generate script
    request = PodcastRequest(
        digest_id=digest.id,
        length=PodcastLength.BRIEF,
        enable_web_search=False
    )

    creator = PodcastCreator()
    script = await creator.generate_script(request)

    assert script.status == PodcastStatus.SCRIPT_PENDING_REVIEW
    assert script.word_count > 0

    # Review and approve
    review_request = ScriptReviewRequest(
        script_id=script.id,
        action=ScriptReviewAction.APPROVE,
        reviewer="test_user"
    )
    script = await review_service.submit_review(review_request)
    assert script.status == PodcastStatus.SCRIPT_APPROVED


async def test_section_revision():
    """Test section-based script revision."""
    script = create_test_script(status=PodcastStatus.SCRIPT_PENDING_REVIEW)

    # Request revision for section 1
    script = await reviser.apply_revision(
        script_id=script.id,
        section_index=1,
        feedback="Make this section more technical with specific examples"
    )

    assert script.revision_count == 1
    assert len(script.revision_history) == 1
    assert script.status == PodcastStatus.SCRIPT_PENDING_REVIEW


async def test_audio_generation():
    """Test audio generation from approved script."""
    script = create_test_script(status=PodcastStatus.SCRIPT_APPROVED)

    creator = PodcastCreator()
    podcast = await creator.generate_audio(
        script_id=script.id,
        voice_provider=VoiceProvider.OPENAI_TTS,
        alex_voice=VoicePersona.ALEX_MALE,
        sam_voice=VoicePersona.SAM_FEMALE
    )

    assert podcast.status == "completed"
    assert podcast.duration_seconds > 0
    assert Path(podcast.audio_url).exists()
```

---

## Phase 8: Suggested Refactoring

### 8.1 Extract Content Assembly Pattern

**Current Issue**: `DigestCreator` has complex context assembly logic that would be duplicated in `PodcastScriptGenerator`.

**Refactoring**: Create shared `ContentContextAssembler`:

```python
# src/processors/context_assembler.py

class ContentContextAssembler:
    """Shared context assembly for digest and podcast creation."""

    async def assemble_digest_context(
        self,
        period_start: datetime,
        period_end: datetime,
        include_themes: bool = True,
        include_summaries: bool = True,
        include_original_text: bool = False,
        include_historical_context: bool = True
    ) -> ContentContext:
        """Assemble all context for content generation."""
        pass
```

**Benefit**: Single source of truth for context assembly, easier testing, consistent behavior.

### 8.2 Standardize Web Search Integration

**Current Issue**: No web search capability exists.

**Addition**: Create `WebSearchService`:

```python
# src/services/web_search.py

class WebSearchService:
    """Web search for content grounding."""

    async def search(
        self,
        query: str,
        num_results: int = 5,
        recency_days: int = 7
    ) -> list[WebSearchResult]:
        """Search web for recent information."""
        # Could use: Tavily, Brave Search, SerpAPI, etc.
        pass
```

### 8.3 Improve Model Step Configuration

**Current Issue**: ModelStep enum needs expansion for new pipeline steps.

**Refactoring**: Add podcast steps:

```python
class ModelStep(str, Enum):
    # Existing
    SUMMARIZATION = "summarization"
    THEME_ANALYSIS = "theme_analysis"
    DIGEST_CREATION = "digest_creation"
    DIGEST_REVISION = "digest_revision"
    HISTORICAL_CONTEXT = "historical_context"
    # New
    PODCAST_SCRIPT = "podcast_script"
    PODCAST_WEB_SEARCH = "podcast_web_search"  # For search query generation
```

### 8.4 Add Delivery Abstraction

**Current Issue**: Delivery is only via email; needs abstraction for audio.

**Refactoring**: Create delivery abstraction:

```python
# src/delivery/base.py

class DeliveryChannel(ABC):
    """Abstract delivery channel."""

    @abstractmethod
    async def deliver(self, content: Any, recipients: list[str]) -> DeliveryResult:
        pass

class EmailDelivery(DeliveryChannel):
    """Email delivery (existing functionality)."""
    pass

class AudioDelivery(DeliveryChannel):
    """Audio file delivery (new)."""
    pass

class PodcastFeedDelivery(DeliveryChannel):
    """RSS podcast feed delivery (future)."""
    pass
```

### 8.5 Token Budget Improvements

**Current Issue**: Token counting is digest-specific.

**Refactoring**: Generalize for podcast script generation:

```python
# Extend TokenCounter

class TokenCounter:
    def estimate_podcast_script_tokens(
        self,
        context: ContentContext,
        length: PodcastLength
    ) -> TokenEstimate:
        """Estimate tokens for podcast script generation."""
        pass
```

---

## Implementation Order

### Sprint 1: Foundation
1. [ ] Create `src/models/podcast.py` with all models (PodcastScriptRecord, Podcast, VoicePersona, etc.)
2. [ ] Create database migration for `podcast_scripts` and `podcasts` tables
3. [ ] Add configuration to `settings.py` (voice persona mappings, TTS provider config)
4. [ ] Add `PODCAST_SCRIPT` to ModelStep enum

### Sprint 2: Script Generation
1. [ ] Create `src/processors/podcast_script_generator.py` with tool-based content retrieval
2. [ ] Implement `get_newsletter_content` and `web_search` tools
3. [ ] Implement lightweight context assembly
4. [ ] Design and test script generation prompts for all lengths
5. [ ] Add unit tests for script generation

### Sprint 3: Script Review Workflow
1. [ ] Create `src/processors/script_reviser.py` for section-based revisions
2. [ ] Create `src/services/script_review_service.py`
3. [ ] Add script review API endpoints
4. [ ] Implement section-by-section revision with feedback
5. [ ] Add review workflow tests

### Sprint 4: Audio Generation
1. [ ] Create `src/delivery/tts_service.py` with provider abstraction
2. [ ] Implement OpenAI TTS provider (primary - best cost/quality balance)
3. [ ] Implement ElevenLabs provider (premium option)
4. [ ] Create `src/delivery/audio_generator.py` with voice persona support
5. [ ] Add local audio file storage

### Sprint 5: Integration
1. [ ] Create `src/processors/podcast_creator.py` (two-phase orchestration)
2. [ ] Integrate with `scripts/run_pipeline.py` (--podcast-script, --podcast-audio)
3. [ ] Add podcast audio API endpoints
4. [ ] Create integration tests
5. [ ] End-to-end testing and documentation

---

## Cost Considerations

### LLM Costs (Script Generation)

| Length | Est. Input Tokens | Est. Output Tokens | Claude Sonnet Cost |
|--------|-------------------|--------------------|--------------------|
| Brief | ~3,000 | ~1,500 | ~$0.02 |
| Standard | ~8,000 | ~4,500 | ~$0.05 |
| Extended | ~20,000 | ~9,000 | ~$0.12 |

### TTS Costs

| Provider | Cost per 1M chars | 5 min (~1k words) | 15 min (~3k words) | 30 min (~6k words) |
|----------|-------------------|-------------------|--------------------|--------------------|
| ElevenLabs | $0.30/1k chars | ~$1.50 | ~$4.50 | ~$9.00 |
| OpenAI TTS | $15/1M chars | ~$0.08 | ~$0.25 | ~$0.50 |
| Google TTS | $4/1M chars | ~$0.02 | ~$0.06 | ~$0.12 |
| AWS Polly | $4/1M chars | ~$0.02 | ~$0.06 | ~$0.12 |

**Recommendation**: Start with OpenAI TTS for cost efficiency with good quality, add ElevenLabs as premium option for best voice quality.

---

## File Structure Summary

```
src/
├── models/
│   └── podcast.py                    # NEW: Podcast data models (PodcastScriptRecord, Podcast, VoicePersona)
├── processors/
│   ├── context_assembler.py          # NEW: Shared context assembly
│   ├── podcast_script_generator.py   # NEW: Script generation with tools
│   ├── script_reviser.py             # NEW: Section-based script revision
│   └── podcast_creator.py            # NEW: Two-phase orchestration
├── delivery/
│   ├── base.py                       # NEW: Delivery abstraction
│   ├── tts_service.py                # NEW: TTS provider abstraction
│   └── audio_generator.py            # NEW: Audio file generation
├── services/
│   ├── script_review_service.py      # NEW: Script review workflow
│   └── web_search.py                 # NEW: Web search service
├── config/
│   └── settings.py                   # MODIFY: Add podcast config, voice persona mappings
└── api/
    ├── script_routes.py              # NEW: Script review API endpoints
    └── podcast_routes.py             # NEW: Audio API endpoints

scripts/
└── run_pipeline.py                   # MODIFY: Add --podcast-script, --podcast-audio flags

tests/
├── test_models/
│   └── test_podcast.py               # NEW
├── test_processors/
│   ├── test_podcast_script_generator.py  # NEW
│   ├── test_script_reviser.py        # NEW
│   └── test_podcast_creator.py       # NEW
├── test_services/
│   └── test_script_review_service.py # NEW
├── test_delivery/
│   ├── test_tts_service.py           # NEW
│   └── test_audio_generator.py       # NEW
└── integration/
    └── test_podcast_pipeline.py      # NEW

alembic/versions/
├── xxx_add_podcast_scripts_table.py  # NEW: Migration
└── xxx_add_podcasts_table.py         # NEW: Migration

docs/
└── PODCAST_GUIDE.md                  # NEW: Documentation
```

---

## Decisions Made

| Question | Decision |
|----------|----------|
| **Voice Selection** | 4 voice personas available: Alex (male/female), Sam (male/female). User selects at generation time. |
| **Storage** | Local file storage initially. S3/SharePoint as future extension. |
| **Accessibility** | Not required for initial implementation. |
| **Music/Sound Effects** | Future extension - document but don't implement. |
| **Script Caching** | Yes - scripts cached as `PodcastScriptRecord` in database, reusable for multiple audio generations. |
| **Generation Trigger** | On-demand only via CLI/API. Scheduling is a future feature. |
| **Quality Review** | Yes - script review workflow with section-based feedback before audio generation. |

---

## Future Extensions (Not in Initial Scope)

The following features are documented for future implementation:

1. **Intro/Outro Music**
   - Add configurable intro/outro music tracks
   - Transition sounds between sections
   - Audio normalization and post-processing

2. **Cloud Storage**
   - S3 bucket upload for audio files
   - SharePoint/OneDrive integration for internal Comcast sharing
   - Signed URL generation for secure access

3. **RSS Podcast Feed**
   - Generate RSS feed for podcast distribution
   - Private feed with authentication
   - Integration with Apple Podcasts, Spotify, etc.

4. **Scheduled Generation**
   - Auto-generate podcast scripts with digest creation
   - Configurable schedule per digest type
   - Queue management for audio generation

5. **Accessibility**
   - VTT/SRT subtitle generation
   - Chapter markers for podcast players
   - Transcript download in multiple formats

6. **Additional TTS Providers**
   - Google Cloud TTS implementation
   - AWS Polly implementation
   - Voice cloning for custom personas

7. **Analytics**
   - Listen duration tracking
   - Download counts
   - Popular episodes reporting
