# Agentic Newsletter Aggregator - Project Plan

## Project Overview

An AI-powered newsletter aggregation and summarization system that:
- Ingests newsletters from Gmail and Substack RSS feeds
- Summarizes individual newsletters into structured, condensed formats
- Analyzes newsletter sets for major themes and trends using knowledge graphs
- References previous digests for continuity and trend tracking
- (Future) Generates podcast-style audio summaries

**Target Audience**: Technical leaders and developers at Comcast
**Voice**: Strategic AI/Data leadership spanning CTO-level strategy to individual practitioner best practices
**Primary Language**: Python (with option to explore TypeScript)
**Learning Focus**: Compare agent frameworks (Google ADK, Microsoft Agent Framework, Claude SDK, OpenAI SDK, etc.)
**Development**: Local-first with cloud deployment for production

## Phase 1: Foundation & Single-Newsletter Processing

**Goal**: Establish core infrastructure and prove out single newsletter summarization

### 1.1 Project Setup ✅
- [x] Initialize Python project with `uv`
  ```bash
  uv init
  uv venv
  source .venv/bin/activate  # or .venv/Scripts/activate on Windows
  uv pip install <dependencies>
  ```
- [x] Create project structure (see Architecture section)
- [x] Set up Docker Compose for local development
  - PostgreSQL container
  - Redis container
  - Neo4j/Graphiti container
- [x] Configure environment management (.env for API keys)
- [x] Configure logging and error handling
- [x] Set up Git workflow and pre-commit hooks
- [x] Create basic project documentation

### 1.2 Newsletter Ingestion ✅
- [x] Gmail Integration
  - Gmail API setup and authentication (OAuth2)
  - Filter/query newsletters by sender or label
  - Extract email content (HTML/text parsing with BeautifulSoup)
  - Handle attachments and embedded images
  - Store raw email metadata and content
- [x] Substack RSS Integration
  - RSS feed parser implementation (feedparser)
  - Handle multiple Substack sources (config file with feed URLs)
  - Extract full article content
  - Handle pagination and feed updates
- [x] Create unified newsletter data model
  - Source metadata (sender, publication, date, URL)
  - Content (title, body, links, images)
  - Raw content preservation (for reprocessing)
  - Ingestion timestamp and status

### 1.3 Initial Summarization (Single Framework) ✅
- [x] Set up Claude SDK (Anthropic) as initial framework
  - API key configuration
  - Client initialization
  - Error handling and rate limiting
- [x] Design summarization prompt structure
  - Extract key insights and technical topics
  - Identify trends and emerging themes
  - Capture actionable items and recommendations
  - Pull notable quotes or data points
  - Structure output as JSON for downstream processing
- [x] Implement single newsletter summarization
- [x] Define structured output schema (Pydantic models)
  ```python
  class NewsletterSummary:
      executive_summary: str  # 2-3 sentences
      key_themes: List[str]   # Bulleted list
      strategic_insights: List[str]  # CTO-level
      technical_details: List[str]   # Developer-level
      actionable_items: List[str]
      notable_quotes: List[str]
      relevance_scores: Dict[str, float]  # by audience
      source_links: List[str]
  ```

### 1.4 Storage Layer ✅
- [x] PostgreSQL schema design
  ```sql
  -- Raw newsletters table
  -- Summaries table
  -- Digest history table
  -- Processing status/audit log
  ```
- [x] SQLAlchemy models and migrations (Alembic)
- [x] Implement data access layer (repository pattern)
- [x] Create database initialization scripts

### 1.5 Knowledge Graph Integration (Graphiti) ✅
- [x] Set up Graphiti MCP server locally
  - Follow https://github.com/getzep/graphiti/blob/main/mcp_server/README.md
  - Configure Neo4j backend
  - Test MCP server connection
- [x] Design entity extraction strategy
  - Technical concepts (RAG, LLMs, transformers, etc.)
  - Companies and products (OpenAI, Claude, GPT-4, etc.)
  - People and organizations (researchers, companies)
  - Techniques and methodologies
- [x] Implement Graphiti integration
  - Extract entities from newsletter summaries
  - Store relationships between concepts
  - Add temporal metadata (when topics were discussed)
- [x] Create query utilities
  - Find related topics
  - Track topic evolution over time
  - Identify emerging vs established themes

**Deliverable**: Working system that ingests newsletters from Gmail/Substack, produces structured summaries, and populates knowledge graph

## Phase 2: Multi-Newsletter Analysis & Digest Generation

**Goal**: Analyze multiple newsletters together and generate cohesive digests

### 2.1 Theme Analysis Agent ✅
- [x] Design cross-newsletter analysis system
  - Query Graphiti for common themes across date range
  - Identify trending topics (frequency, recency, growth)
  - Detect emerging vs established themes
  - Find unexpected connections between topics
- [x] Implement theme clustering/categorization
  - ML/AI topics (LLMs, agents, RAG, fine-tuning)
  - DevOps/Infrastructure (cloud, containers, orchestration)
  - Data Engineering (pipelines, lakes, processing)
  - Business/Strategy (adoption, ROI, governance)
  - Tools/Products (new releases, updates)
  - Research/Academia (papers, breakthroughs)
  - Security (added)
- [x] Build relevance scoring
  - Importance to Comcast technical audience
  - Strategic vs tactical relevance
  - Novelty vs confirmation of known trends
  - Cross-functional impact
- [x] Performance monitoring and model flexibility
  - Processing time tracking (~4.2s per newsletter)
  - Support for large context models (Gemini Flash placeholder)
  - Concurrent Graphiti query optimization

### 2.2 Historical Context Integration ✅
- [x] Query Graphiti for historical topic mentions
  - "When did we first discuss this?"
  - "How has the discussion evolved?"
  - "What related topics were discussed together?"
- [x] Implement context retrieval
  - Fetch previous digest snippets mentioning topic
  - Track sentiment/stance changes over time
  - Identify recurring themes vs one-off mentions
- [x] Build continuity features
  - "Previously we discussed..."
  - "This builds on last week's theme about..."
  - "This is a new development in an ongoing trend..."
- [x] LLM-powered evolution analysis
  - Analyzes how themes have changed over time
  - Generates evolution summaries and continuity text
  - Tracks mention frequency and stance changes

### 2.3 Digest Generation ✅
- [x] Design digest structure (multi-level)
  ```markdown
  # AI Newsletter Digest - [Date]

  ## Executive Overview (2-3 paragraphs)
  For senior leadership - what matters and why

  ## Strategic Insights
  CTO-level implications and decisions
  - Theme 1: [Strategic context]
  - Theme 2: [Business impact]

  ## Technical Developments
  Developer-focused details and implementations
  - Topic 1: [Technical deep-dive]
  - Topic 2: [How-to and best practices]

  ## Emerging Trends
  New and noteworthy (with historical context)

  ## Actionable Recommendations
  - For leadership: [Strategic actions]
  - For teams: [Tactical implementations]
  - For individuals: [Skill development]

  ## Sources
  Links to original newsletters
  ```
- [x] Implement multi-audience formatting
  - Layered information (summary → details)
  - Role-specific insights (color-coded sections)
  - Three output formats: Markdown, HTML (email-ready), Plain text
- [x] Create daily digest generator
  - CLI script with flexible date selection
  - Integrates theme analysis and historical context
  - Outputs to console, file, or database
- [x] Create weekly digest generator
  - Meta-analysis of week's themes
  - Longer-term trend tracking
  - Support for custom date ranges
- [x] Unit tests for digest creation and formatting
  - DigestCreator tests with mocking (9 tests)
  - DigestFormatter tests for all formats (10 tests)
  - 99% coverage on formatter, 94% on creator
  - More comprehensive historical context

### 2.4 Scheduling & Automation
- [ ] Implement Celery tasks
  - Scheduled newsletter ingestion (hourly/daily)
  - Daily digest generation (e.g., 6am)
  - Weekly digest generation (e.g., Monday 7am)
- [ ] Configure Celery Beat for scheduling
- [ ] Error handling and retry logic
  - Exponential backoff for API failures
  - Alert on repeated failures
  - Dead letter queue for manual review
- [ ] Monitoring and observability
  - Structured logging with context
  - Health check endpoints
  - Processing metrics (newsletters ingested, digests generated)

**Deliverable**: Automated system producing daily/weekly digests with knowledge graph-powered historical context

## Phase 3: Agent Framework Comparison

**Goal**: Implement parallel versions using different frameworks for learning and comparison

### 3.1 Framework Implementation Matrix

Implement the summarization and analysis components using each framework:

#### 3.1.1 Claude SDK (Anthropic) ✅ Primary
- [ ] Newsletter summarization agent
- [ ] Theme analysis agent
- [ ] Digest generation agent
- [ ] Tool use for Graphiti queries
- [ ] Document: API patterns, prompt engineering, extended thinking

#### 3.1.2 OpenAI SDK (Agents/Assistants API)
- [ ] Newsletter summarization agent
- [ ] Theme analysis agent
- [ ] Digest generation agent
- [ ] Function calling for Graphiti integration
- [ ] Document: Assistants API, structured outputs, file search

#### 3.1.3 Google ADK (Agent Development Kit)
- [ ] Newsletter summarization agent
- [ ] Theme analysis agent
- [ ] Digest generation agent
- [ ] Gemini integration and tool use
- [ ] Document: ADK patterns, multi-turn conversations

#### 3.1.4 Microsoft Agent Framework (Semantic Kernel or AutoGen)
- [ ] Newsletter summarization agent
- [ ] Theme analysis agent
- [ ] Digest generation agent
- [ ] Multi-agent orchestration
- [ ] Document: Agent collaboration, planning patterns

### 3.2 Framework Comparison Analysis
- [ ] Create comparison matrix
  - **Developer Experience**: API clarity, documentation, debugging
  - **API Design**: Ergonomics, flexibility, abstractions
  - **Cost**: Token usage, API pricing, optimization options
  - **Performance**: Speed, quality of outputs, consistency
  - **Tool/Function Calling**: Ease of use, reliability, features
  - **Multi-Agent**: Orchestration, state management, collaboration
  - **State Management**: Conversation history, context windows
  - **Error Handling**: Retry logic, rate limiting, graceful degradation
- [ ] Document learnings and recommendations
  - Best use cases for each framework
  - Strengths and weaknesses
  - Migration considerations
- [ ] Performance benchmarking
  - Time to generate summary
  - Token usage per newsletter/digest
  - Quality assessment (human eval)
- [ ] Cost analysis
  - Per newsletter cost
  - Per digest cost
  - Monthly operational costs

**Deliverable**: Working implementations in 4 frameworks with detailed comparison documentation

## Phase 4: Audio Digest Generation (Future)

**Goal**: Convert written digests to podcast-style audio summaries

### 4.1 Script Generation
- [ ] Design audio-optimized digest structure
  - Conversational tone (vs written)
  - Natural transitions and flow
  - Time-boxed segments (5min, 15min, 30min versions)
- [ ] Implement script generation agent
  - Convert written digest to audio script
  - Add intro/outro segments
  - Insert natural pauses and emphasis
  - Remove visual-only elements (tables, code blocks)

### 4.2 Text-to-Speech Integration
- [ ] Evaluate TTS options
  - OpenAI TTS API (Nova voices)
  - ElevenLabs (most natural, more expensive)
  - Google Cloud TTS (Wavenet/Neural2)
  - AWS Polly (Neural voices)
- [ ] Choose voice(s) for different sections
  - Single professional voice, or
  - Multiple voices for variety (intro vs content)
- [ ] Implement TTS generation
  - API integration
  - Audio file generation and storage
  - Quality settings (sample rate, format)

### 4.3 Audio Production
- [ ] Audio assembly
  - Combine intro + content + outro
  - Add music/transitions (optional)
  - Normalize audio levels
- [ ] Generate multiple formats
  - 5-minute executive summary (key themes only)
  - 15-minute detailed version (strategic + technical)
  - 30-minute deep-dive (full digest with examples)
- [ ] Post-processing
  - MP3 encoding
  - ID3 tags (title, date, description)
  - Thumbnail/cover art

### 4.4 Distribution
- [ ] Audio hosting
  - S3 or similar cloud storage
  - CDN for fast delivery
- [ ] RSS feed for podcast apps
  - Standard podcast RSS format
  - Episode metadata
  - Update feed with new episodes
- [ ] Web player
  - Embed audio player in digest emails
  - Web interface for browsing episodes
- [ ] Sharing capabilities
  - Shareable links
  - Transcripts alongside audio

**Deliverable**: Automated audio digest generation and distribution

## Phase 5: Delivery & User Interface

**Goal**: Make digests accessible and useful

### 5.1 Output Channels
- [ ] Email delivery system
  - HTML email templates (responsive design)
  - Plain text fallback
  - Personalization options (by role/interest)
  - Integration with SendGrid/Mailgun/AWS SES
- [ ] Web interface (FastAPI + simple frontend)
  - Browse digest history (calendar view)
  - Search past digests (full-text search)
  - Topic/theme filtering (using Graphiti)
  - Individual newsletter view
  - Export options (PDF, Markdown)
- [ ] API for programmatic access
  - REST API endpoints
  - Authentication (API keys)
  - Rate limiting
- [ ] Slack/Teams integration (optional)
  - Daily digest posted to channel
  - Bot commands for queries
  - Topic subscriptions

### 5.2 User Feedback & Iteration
- [ ] Feedback collection
  - "Was this digest helpful?" (thumbs up/down)
  - Topic relevance ratings
  - Suggested topics to add
- [ ] Usage analytics
  - Email open/click rates
  - Web interface usage patterns
  - Popular topics/themes
- [ ] Iterate based on feedback
  - Adjust digest structure
  - Refine summarization prompts
  - Tune relevance scoring
- [ ] A/B testing (optional)
  - Different digest formats
  - Subject line optimization
  - Content ordering

**Deliverable**: Production-ready delivery system with user feedback loop

## Technical Architecture

### Development Stack

```yaml
Language: Python 3.11+
Package Manager: uv
Web Framework: FastAPI (APIs, webhooks, web UI)
Task Queue: Celery + Redis (scheduling, async processing)
Databases:
  - PostgreSQL: Structured data (newsletters, summaries, digests)
  - Graphiti + Neo4j: Knowledge graph (concepts, themes, relationships)
Email:
  - Ingestion: Gmail API
  - Delivery: SendGrid/Mailgun/AWS SES
RSS: feedparser
Testing: pytest + pytest-asyncio
Linting: ruff
Type Checking: mypy
```

### Agent Frameworks (Multi-Framework Comparison)
```yaml
- Claude SDK (Anthropic) - Primary
- OpenAI SDK (Agents/Assistants API)
- Google ADK (Agent Development Kit)
- Microsoft Agent Framework (Semantic Kernel or AutoGen)
```

### Project Structure

```
agentic-newsletter-aggregator/
├── pyproject.toml           # uv project config
├── .env.example             # Environment template
├── docker-compose.yml       # Local development dependencies
├── README.md
├── PROJECT_PLAN.md
├── CLAUDE.md
│
├── src/
│   ├── agents/              # Agent framework implementations
│   │   ├── base.py          # Abstract base classes
│   │   ├── claude/          # Claude SDK implementation
│   │   │   ├── summarizer.py
│   │   │   ├── analyzer.py
│   │   │   └── digest_generator.py
│   │   ├── openai/          # OpenAI SDK implementation
│   │   ├── google/          # Google ADK implementation
│   │   └── microsoft/       # MS Agent Framework implementation
│   │
│   ├── ingestion/           # Newsletter fetching
│   │   ├── gmail.py         # Gmail API integration
│   │   ├── substack.py      # RSS feed parser
│   │   └── models.py        # Ingestion data models
│   │
│   ├── models/              # Core data models (Pydantic + SQLAlchemy)
│   │   ├── newsletter.py    # Newsletter model
│   │   ├── summary.py       # Summary model
│   │   └── digest.py        # Digest model
│   │
│   ├── storage/             # Data persistence
│   │   ├── database.py      # PostgreSQL + SQLAlchemy
│   │   ├── graphiti_client.py  # Graphiti MCP integration
│   │   └── migrations/      # Alembic migrations
│   │
│   ├── processors/          # Core processing logic
│   │   ├── summarizer.py    # Newsletter summarization
│   │   ├── theme_analyzer.py  # Cross-newsletter theme analysis
│   │   └── digest_creator.py  # Digest generation
│   │
│   ├── delivery/            # Output channels
│   │   ├── email.py         # Email delivery
│   │   └── web.py           # Web interface
│   │
│   ├── tasks/               # Celery tasks
│   │   ├── ingest.py        # Scheduled ingestion
│   │   └── generate.py      # Digest generation
│   │
│   ├── api/                 # FastAPI application
│   │   ├── app.py           # Main FastAPI app
│   │   └── routes/          # API endpoints
│   │
│   ├── config.py            # Configuration management
│   └── utils/               # Utilities
│       ├── logging.py
│       └── html_parser.py
│
├── tests/                   # Test suite
│   ├── test_ingestion/
│   ├── test_agents/
│   └── test_processors/
│
└── scripts/                 # Utility scripts
    ├── setup_gmail.py       # Gmail API setup wizard
    └── backfill.py          # Backfill historical newsletters
```

### Local Development Environment

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: newsletters
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  neo4j:
    image: neo4j:5
    environment:
      NEO4J_AUTH: neo4j/password
    ports:
      - "7474:7474"  # HTTP
      - "7687:7687"  # Bolt
    volumes:
      - neo4j_data:/data

volumes:
  postgres_data:
  neo4j_data:
```

### Cloud Deployment (Production)

**Recommended Platform**: Railway, Render, or Fly.io for simplicity

```yaml
Components:
  - Application: Python app with Celery workers
  - PostgreSQL: Managed database
  - Redis: Managed Redis instance
  - Neo4j: Managed Neo4j (Neo4j Aura) or self-hosted
  - Storage: S3-compatible for audio files

Environment:
  - All configs via environment variables
  - Secrets management (API keys)
  - Automated deployments from main branch

Scaling:
  - Web server: 1 instance (low traffic)
  - Celery workers: 1-2 instances
  - Databases: Managed auto-scaling
```

### Configuration Management

```python
# src/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://localhost/newsletters"
    redis_url: str = "redis://localhost:6379"
    neo4j_url: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # APIs
    anthropic_api_key: str
    openai_api_key: str | None = None
    google_api_key: str | None = None

    # Gmail
    gmail_credentials_file: str = "credentials.json"
    gmail_token_file: str = "token.json"

    # Email delivery
    sendgrid_api_key: str | None = None

    # Environment
    environment: str = "development"  # or "production"

    class Config:
        env_file = ".env"

settings = Settings()
```

## Success Metrics

- **Coverage**: % of newsletters successfully ingested and summarized (target: >95%)
- **Quality**: User satisfaction with digest relevance and accuracy (feedback scores)
- **Timeliness**: Digests delivered on schedule (daily 7am, weekly Monday morning)
- **Engagement**: Email open rates, time spent reading/listening, click-throughs
- **Knowledge Graph**: Entity/relationship extraction accuracy, useful historical context
- **Learning**: Comprehensive framework comparison documented with recommendations
- **Cost**: Per-digest cost tracking, monthly operational budget adherence

## Risk Mitigation

- **API Rate Limits**: Implement exponential backoff, respect rate limits, queue management
- **Cost Control**: Monitor token usage per digest, set budget alerts, optimize prompts
- **Content Quality**: Human review for first month, user feedback loops, quality metrics
- **Gmail Access**: Handle OAuth refresh, quota management, graceful degradation
- **RSS Reliability**: Retry logic, fallback mechanisms, alert on persistent failures
- **Knowledge Graph**: Validate entity extraction quality, handle graph query failures
- **Framework Dependencies**: Abstract interfaces allow framework swapping if needed

## Timeline Estimate

- **Phase 1**: 2-3 weeks (MVP with Claude SDK + Graphiti)
- **Phase 2**: 2-3 weeks (full digest automation with knowledge graph)
- **Phase 3**: 3-4 weeks (parallel framework implementations and comparison)
- **Phase 4**: 1-2 weeks (audio generation)
- **Phase 5**: 1-2 weeks (delivery polish and user feedback)

**Total: 9-14 weeks for complete system**

*Note: Phases can be developed iteratively with working increments delivered at each phase.*

## Immediate Next Steps

1. **Initialize project with uv**
   ```bash
   uv init
   uv venv
   source .venv/bin/activate
   ```

2. **Set up Docker Compose for local dependencies**
   - Create docker-compose.yml
   - Start PostgreSQL, Redis, Neo4j locally

3. **Configure Gmail API access**
   - Create Google Cloud project
   - Enable Gmail API
   - Download credentials
   - Run OAuth flow

4. **Set up Graphiti MCP server**
   - Clone and configure Graphiti
   - Connect to Neo4j
   - Test entity extraction

5. **Implement basic newsletter ingestion**
   - Gmail: Fetch single newsletter
   - Substack: Parse RSS feed
   - Store in PostgreSQL

6. **Build first summarization pipeline (Claude SDK)**
   - Single newsletter → structured summary
   - Extract entities → Graphiti
   - Verify end-to-end flow

7. **Test with 2-3 real newsletters**
   - Validate ingestion
   - Review summary quality
   - Check knowledge graph population
