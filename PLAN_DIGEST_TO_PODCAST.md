# Implementation Plan: Digest-to-Podcast Audio Feature

## Executive Summary

Transform daily and weekly digests into engaging podcast-style audio content featuring two expert personas discussing AI, Data, and Software development news with perspectives relevant to Comcast and the industry.

**Personas:**
1. **Alex Chen** - VP of Engineering / Senior Technical Leader: Strategic perspective, organizational impact, competitive landscape, investment decisions
2. **Dr. Sam Rodriguez** - Distinguished Engineer: Technical deep-dives, implementation details, architectural implications, developer experience

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
    SCRIPT_COMPLETED = "script_completed"
    AUDIO_GENERATING = "audio_generating"
    COMPLETED = "completed"
    FAILED = "failed"

class VoiceProvider(str, Enum):
    ELEVENLABS = "elevenlabs"
    GOOGLE_TTS = "google_tts"
    AWS_POLLY = "aws_polly"
    OPENAI_TTS = "openai_tts"

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
    include_web_search: bool = True
    include_original_text: bool = False  # Only for extended
    voice_provider: VoiceProvider = VoiceProvider.ELEVENLABS
    custom_focus_topics: list[str] = []  # Optional topic emphasis

# --- Database Model ---

class Podcast(Base):
    """Podcast audio generated from a digest."""
    __tablename__ = "podcasts"

    id = Column(Integer, primary_key=True)
    digest_id = Column(Integer, ForeignKey("digests.id"), nullable=False)
    length = Column(SQLEnum(PodcastLength), nullable=False)
    status = Column(SQLEnum(PodcastStatus), default=PodcastStatus.PENDING)

    # Script content
    title = Column(String(500))
    script_json = Column(JSON)  # PodcastScript serialized
    word_count = Column(Integer)

    # Audio output
    audio_url = Column(String(1000))  # S3/GCS URL or local path
    audio_format = Column(String(20))  # mp3, wav
    duration_seconds = Column(Integer)
    file_size_bytes = Column(Integer)

    # Generation metadata
    voice_provider = Column(SQLEnum(VoiceProvider))
    voice_config = Column(JSON)  # Provider-specific voice IDs

    # Context used
    newsletter_ids = Column(JSON)  # List of newsletter IDs used
    theme_ids = Column(JSON)  # Themes incorporated
    web_search_queries = Column(JSON)  # Web searches performed

    # Tracking
    model_used = Column(String(100))
    token_usage = Column(JSON)
    processing_time_seconds = Column(Integer)
    error_message = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    script_completed_at = Column(DateTime)
    audio_completed_at = Column(DateTime)

    # Relationships
    digest = relationship("Digest", backref="podcasts")
```

### 1.2 Configuration Updates

**Add to `src/config/settings.py`:**

```python
# Podcast / TTS Configuration
PODCAST_VOICE_PROVIDER: VoiceProvider = VoiceProvider.ELEVENLABS
PODCAST_OUTPUT_FORMAT: str = "mp3"
PODCAST_SAMPLE_RATE: int = 44100

# ElevenLabs Configuration
ELEVENLABS_API_KEY: str = ""
ELEVENLABS_VOICE_ALEX: str = ""  # Voice ID for VP persona
ELEVENLABS_VOICE_SAM: str = ""   # Voice ID for DE persona

# Google TTS Configuration
GOOGLE_TTS_CREDENTIALS: str = ""
GOOGLE_TTS_VOICE_ALEX: str = "en-US-Studio-M"
GOOGLE_TTS_VOICE_SAM: str = "en-US-Studio-Q"

# AWS Polly Configuration
AWS_POLLY_REGION: str = "us-east-1"
AWS_POLLY_VOICE_ALEX: str = "Matthew"
AWS_POLLY_VOICE_SAM: str = "Stephen"

# OpenAI TTS Configuration
OPENAI_TTS_VOICE_ALEX: str = "onyx"
OPENAI_TTS_VOICE_SAM: str = "fable"

# Podcast Content Settings
PODCAST_WORDS_PER_MINUTE: int = 150  # Average speaking rate
PODCAST_INCLUDE_MUSIC: bool = False  # Future: intro/outro music
PODCAST_STORAGE_PATH: str = "data/podcasts"  # Local storage
PODCAST_S3_BUCKET: str = ""  # Optional S3 storage
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
| Newsletter summaries | - | Key points | Full |
| Original newsletter text | - | - | Excerpts |
| Graphiti themes | Top 3 | Top 5 | All |
| Historical context | - | Key 2 | All |
| Web search grounding | - | Optional | ✓ |
| Relevant links | - | Top 5 | All |

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

### 2.3 Context Assembly

```python
class PodcastScriptGenerator:
    """Generate podcast scripts from digests."""

    def __init__(self):
        self.model_config = ModelConfig()
        self.model = self.model_config.get_model_for_step(ModelStep.PODCAST_SCRIPT)
        self.graphiti = GraphitiClient()

    async def generate_script(
        self,
        request: PodcastRequest
    ) -> PodcastScript:
        """Generate a podcast script from a digest."""

        # 1. Load digest and related data
        context = await self._assemble_context(request)

        # 2. Optionally perform web search for grounding
        if request.include_web_search:
            context.web_results = await self._perform_web_search(context)

        # 3. Generate script via LLM
        script = await self._generate_script_llm(context, request.length)

        # 4. Validate and enhance script
        script = self._validate_and_enhance(script)

        return script

    async def _assemble_context(self, request: PodcastRequest) -> PodcastContext:
        """Assemble all context needed for script generation."""

        with get_db() as db:
            # Load digest
            digest = db.query(Digest).filter(Digest.id == request.digest_id).first()

            # Load newsletters from the digest period
            newsletters = db.query(Newsletter).filter(
                Newsletter.published_date >= digest.period_start,
                Newsletter.published_date <= digest.period_end,
                Newsletter.status == ProcessingStatus.COMPLETED
            ).all()

            # Load summaries
            newsletter_ids = [n.id for n in newsletters]
            summaries = db.query(NewsletterSummary).filter(
                NewsletterSummary.newsletter_id.in_(newsletter_ids)
            ).all()

            # Load theme analysis
            theme_analysis = db.query(ThemeAnalysis).filter(
                ThemeAnalysis.start_date >= digest.period_start,
                ThemeAnalysis.end_date <= digest.period_end
            ).order_by(ThemeAnalysis.created_at.desc()).first()

        # Query Graphiti for additional theme context
        graphiti_themes = await self.graphiti.extract_themes_from_range(
            start_date=digest.period_start,
            end_date=digest.period_end
        )

        return PodcastContext(
            digest=digest,
            newsletters=newsletters,
            summaries=summaries,
            theme_analysis=theme_analysis,
            graphiti_themes=graphiti_themes,
            length=request.length,
            include_original_text=request.include_original_text
        )

    async def _perform_web_search(self, context: PodcastContext) -> list[WebSearchResult]:
        """Perform web searches for grounding and recent context."""

        # Extract key topics from digest for search
        search_queries = self._extract_search_queries(context)

        results = []
        for query in search_queries[:5]:  # Limit to 5 searches
            # Use web search tool/API
            search_result = await self._web_search(query)
            results.extend(search_result)

        return results
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

    def _get_voice_for_speaker(self, speaker: str) -> str:
        if speaker == "alex":
            return self.settings.ELEVENLABS_VOICE_ALEX
        else:
            return self.settings.ELEVENLABS_VOICE_SAM
```

---

## Phase 4: Pipeline Integration

### 4.1 Podcast Processor (`src/processors/podcast_creator.py`)

```python
class PodcastCreator:
    """Orchestrate full podcast creation pipeline."""

    def __init__(self):
        self.script_generator = PodcastScriptGenerator()
        self.audio_generator = None  # Lazy init based on provider

    async def create_podcast(self, request: PodcastRequest) -> Podcast:
        """Create a complete podcast from a digest."""

        # 1. Create database record
        with get_db() as db:
            podcast = Podcast(
                digest_id=request.digest_id,
                length=request.length,
                status=PodcastStatus.SCRIPT_GENERATING,
                voice_provider=request.voice_provider
            )
            db.add(podcast)
            db.commit()
            db.refresh(podcast)
            podcast_id = podcast.id

        try:
            # 2. Generate script
            script = await self.script_generator.generate_script(request)

            with get_db() as db:
                podcast = db.query(Podcast).get(podcast_id)
                podcast.script_json = script.model_dump()
                podcast.word_count = script.word_count
                podcast.title = script.title
                podcast.status = PodcastStatus.AUDIO_GENERATING
                podcast.script_completed_at = datetime.utcnow()
                db.commit()

            # 3. Generate audio
            self.audio_generator = PodcastAudioGenerator(request.voice_provider)
            output_path = self._get_output_path(podcast_id)

            audio_meta = await self.audio_generator.generate_audio(
                script,
                output_path
            )

            # 4. Update final record
            with get_db() as db:
                podcast = db.query(Podcast).get(podcast_id)
                podcast.audio_url = str(output_path)
                podcast.audio_format = audio_meta.format
                podcast.duration_seconds = audio_meta.duration_seconds
                podcast.file_size_bytes = audio_meta.file_size_bytes
                podcast.status = PodcastStatus.COMPLETED
                podcast.audio_completed_at = datetime.utcnow()
                db.commit()
                db.refresh(podcast)

            return podcast

        except Exception as e:
            with get_db() as db:
                podcast = db.query(Podcast).get(podcast_id)
                podcast.status = PodcastStatus.FAILED
                podcast.error_message = str(e)
                db.commit()
            raise
```

### 4.2 Pipeline Integration (`scripts/run_pipeline.py`)

Add podcast generation as optional pipeline step:

```python
parser.add_argument(
    "--podcast",
    nargs="?",
    const="standard",
    choices=["brief", "standard", "extended", "all"],
    help="Generate podcast after digest (default: standard length)"
)

parser.add_argument(
    "--podcast-provider",
    default="elevenlabs",
    choices=["elevenlabs", "openai_tts", "google_tts", "aws_polly"],
    help="TTS provider for podcast audio"
)

# In pipeline execution:
if args.podcast and self.stats["digest_created"]:
    lengths = [PodcastLength.BRIEF, PodcastLength.STANDARD, PodcastLength.EXTENDED] \
              if args.podcast == "all" \
              else [PodcastLength(args.podcast)]

    for length in lengths:
        request = PodcastRequest(
            digest_id=self.stats["digest_id"],
            length=length,
            voice_provider=VoiceProvider(args.podcast_provider)
        )
        podcast = await self._create_podcast(request)
        self.stats["podcasts"].append(podcast.id)
```

---

## Phase 5: API & Delivery

### 5.1 API Endpoints (`src/api/podcast_routes.py`)

```python
from fastapi import APIRouter, BackgroundTasks

router = APIRouter(prefix="/podcasts", tags=["podcasts"])

@router.post("/")
async def create_podcast(
    request: PodcastRequest,
    background_tasks: BackgroundTasks
) -> dict:
    """Create a podcast from a digest."""
    # Queue for background processing
    background_tasks.add_task(create_podcast_task, request)
    return {"status": "queued", "message": "Podcast generation started"}

@router.get("/{podcast_id}")
async def get_podcast(podcast_id: int) -> Podcast:
    """Get podcast by ID."""
    pass

@router.get("/{podcast_id}/audio")
async def get_podcast_audio(podcast_id: int):
    """Stream podcast audio file."""
    pass

@router.get("/{podcast_id}/script")
async def get_podcast_script(podcast_id: int) -> PodcastScript:
    """Get podcast script (for accessibility/transcript)."""
    pass

@router.get("/digest/{digest_id}")
async def list_podcasts_for_digest(digest_id: int) -> list[Podcast]:
    """List all podcasts generated from a digest."""
    pass
```

---

## Phase 6: Testing Strategy

### 6.1 Unit Tests

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

### 6.2 Integration Tests

```python
# tests/integration/test_podcast_pipeline.py

async def test_full_podcast_pipeline():
    """Test complete digest → script → audio pipeline."""

    # Create test digest
    digest = create_test_digest()

    # Generate podcast
    request = PodcastRequest(
        digest_id=digest.id,
        length=PodcastLength.BRIEF,
        include_web_search=False  # Skip for faster tests
    )

    creator = PodcastCreator()
    podcast = await creator.create_podcast(request)

    assert podcast.status == PodcastStatus.COMPLETED
    assert podcast.duration_seconds > 0
    assert Path(podcast.audio_url).exists()
```

---

## Phase 7: Suggested Refactoring

### 7.1 Extract Content Assembly Pattern

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

### 7.2 Standardize Web Search Integration

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

### 7.3 Improve Model Step Configuration

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

### 7.4 Add Delivery Abstraction

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

### 7.5 Token Budget Improvements

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

### Sprint 1: Foundation (Week 1-2)
1. [ ] Create `src/models/podcast.py` with all models
2. [ ] Create database migration for `podcasts` table
3. [ ] Add configuration to `settings.py`
4. [ ] Add `PODCAST_SCRIPT` to ModelStep enum
5. [ ] Refactor: Create `ContentContextAssembler`

### Sprint 2: Script Generation (Week 2-3)
1. [ ] Create `src/processors/podcast_script_generator.py`
2. [ ] Implement context assembly for different lengths
3. [ ] Design and test script generation prompts
4. [ ] Add unit tests for script generation

### Sprint 3: Audio Generation (Week 3-4)
1. [ ] Create `src/delivery/tts_service.py` with provider abstraction
2. [ ] Implement ElevenLabs provider (primary)
3. [ ] Implement OpenAI TTS provider (fallback)
4. [ ] Create `src/delivery/audio_generator.py`
5. [ ] Add audio file storage (local + optional S3)

### Sprint 4: Integration (Week 4-5)
1. [ ] Create `src/processors/podcast_creator.py`
2. [ ] Integrate with `scripts/run_pipeline.py`
3. [ ] Add API endpoints
4. [ ] Create integration tests
5. [ ] End-to-end testing

### Sprint 5: Polish & Optimization (Week 5-6)
1. [ ] Implement web search service
2. [ ] Add caching for repeated generations
3. [ ] Optimize audio generation (streaming, parallel)
4. [ ] Add podcast RSS feed generation (future)
5. [ ] Documentation

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
│   └── podcast.py                    # NEW: Podcast data models
├── processors/
│   ├── context_assembler.py          # NEW: Shared context assembly
│   ├── podcast_script_generator.py   # NEW: Script generation
│   └── podcast_creator.py            # NEW: Orchestration
├── delivery/
│   ├── base.py                       # NEW: Delivery abstraction
│   ├── tts_service.py                # NEW: TTS provider abstraction
│   └── audio_generator.py            # NEW: Audio file generation
├── services/
│   └── web_search.py                 # NEW: Web search service
├── config/
│   └── settings.py                   # MODIFY: Add podcast config
└── api/
    └── podcast_routes.py             # NEW: API endpoints

scripts/
└── run_pipeline.py                   # MODIFY: Add --podcast flag

tests/
├── test_models/
│   └── test_podcast.py               # NEW
├── test_processors/
│   ├── test_podcast_script_generator.py  # NEW
│   └── test_podcast_creator.py       # NEW
├── test_delivery/
│   ├── test_tts_service.py           # NEW
│   └── test_audio_generator.py       # NEW
└── integration/
    └── test_podcast_pipeline.py      # NEW

alembic/versions/
└── xxx_add_podcasts_table.py         # NEW: Migration

docs/
└── PODCAST_GUIDE.md                  # NEW: Documentation
```

---

## Open Questions for Clarification

1. **Voice Selection**: Should users be able to preview/select voices, or use configured defaults?

2. **Storage**: Local file storage vs. cloud (S3/GCS)? RSS podcast feed for distribution?

3. **Transcript Accessibility**: Generate VTT/SRT subtitles for accessibility?

4. **Music/Sound Effects**: Add intro/outro music or transitions?

5. **Caching**: Cache generated scripts for regenerating audio with different voices?

6. **Scheduling**: Auto-generate podcasts with digests or on-demand only?

7. **Quality Review**: Human review step before audio generation like digests?
