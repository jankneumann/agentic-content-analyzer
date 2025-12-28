# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

An agentic AI solution for aggregating and summarizing AI newsletters into daily and weekly digests.

**Purpose**: Help technical leaders and developers at Comcast stay informed on AI/Data trends
**Voice**: Strategic leadership spanning CTO-level strategy to individual practitioner best practices
**Sources**: Gmail and Substack RSS feeds
**Output**: Structured digests analyzing themes across newsletters, with knowledge graph-powered historical context

## Technology Stack

- **Language**: Python 3.11+
- **Package Management**: uv
- **Databases**:
  - PostgreSQL + SQLAlchemy (structured data: newsletters, summaries, digests)
  - Graphiti + Neo4j (knowledge graph: concepts, themes, temporal relationships)
- **Agent Frameworks**: Multi-framework approach for comparison
  - Claude SDK (Anthropic) - Primary
  - OpenAI SDK (Agents/Assistants API)
  - Google ADK (Agent Development Kit)
  - Microsoft Agent Framework (Semantic Kernel or AutoGen)
- **Ingestion**: Gmail API, feedparser (RSS)
- **Task Queue**: Celery + Redis
- **Web**: FastAPI (APIs, web UI)
- **Testing**: pytest

## Architecture

```
src/
  agents/           # Agent framework implementations
    base.py         # Abstract base classes
    claude/         # Claude SDK agents (primary)
    openai/         # OpenAI SDK agents
    google/         # Google ADK agents
    microsoft/      # MS Agent Framework agents
  ingestion/        # Newsletter fetching
    gmail.py        # Gmail API integration
    substack.py     # RSS feed parser
  models/           # Data models (Pydantic + SQLAlchemy)
    newsletter.py
    summary.py
    digest.py
  storage/          # Data persistence
    database.py     # PostgreSQL
    graphiti_client.py  # Graphiti MCP integration
  processors/       # Core processing
    summarizer.py
    theme_analyzer.py
    digest_creator.py
  delivery/         # Output channels
    email.py
    web.py
  tasks/            # Celery tasks
  api/              # FastAPI app
```

## Key Workflows

### Newsletter Processing Pipeline
1. **Ingestion**: Fetch from Gmail/Substack → Parse content → Store raw
2. **Summarization**: Individual newsletter → Structured summary → Extract entities
3. **Knowledge Graph**: Store entities/relationships in Graphiti (concepts, temporal evolution)
4. **Theme Analysis**: Query Graphiti for common themes, trending topics, historical context
5. **Digest Generation**: Multi-audience formatting (CTO strategy + developer tactics)
6. **Delivery**: Email/web with daily/weekly schedules

### Knowledge Graph (Graphiti) Usage
- **Entity Extraction**: Technical concepts, companies, products, people, methodologies
- **Relationship Tracking**: How topics relate, co-occurrence patterns
- **Temporal Analysis**: Track concept evolution over time, identify emerging trends
- **Historical Context**: "We first discussed X when...", "This relates to previous theme Y..."
- **Queries**: "What topics are related to RAG?", "How has AI regulation discussion evolved?"

### Agent Framework Pattern
Each framework implementation provides:
- Newsletter summarization agent
- Theme analysis agent
- Digest generation agent
- Consistent interfaces for comparison

## Development Setup

### Local Development (Recommended)
```bash
# Initialize project
uv init
uv venv
source .venv/bin/activate  # or .venv/Scripts/activate on Windows

# Start local dependencies
docker compose up -d  # PostgreSQL, Redis, Neo4j

# Install dependencies
uv pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with API keys

# Run database migrations
alembic upgrade head

# Start Graphiti MCP server
# See: https://github.com/getzep/graphiti/blob/main/mcp_server/README.md
```

### Cloud Production (When Ready)
- Deploy to Railway/Render/Fly.io
- Use managed PostgreSQL, Redis
- Host Neo4j (Neo4j Aura or self-hosted)
- Environment-aware configuration (same codebase, different env vars)

## Development Guidelines

### Git Workflow
**CRITICAL**: Commit after every major feature implementation:
- Makes recovery from errors easy (e.g., reverting problematic sed changes)
- Provides clear checkpoints for progress tracking
- Use descriptive commit messages that explain the "why"
- Commit frequency: After completing each major task/feature

Example workflow:
```bash
# After completing feature/fix
git add .
git commit -m "Add integration tests for theme analysis workflow"
```

### Tool Usage Best Practices

#### AVOID sed for Global Changes
**CRITICAL**: `sed` can cause unintended side effects and is difficult to control precisely.

**Bad Example**:
```bash
# DON'T: This might remove commas from unintended places
sed -i 's/$/,/g' file.py  # Removed commas from JSON, function params, etc.
```

**Rules**:
- **NEVER use sed for global changes** unless very narrowly scoped
- **ALWAYS prefer the Edit tool** for code changes - it's safer and more precise
- Only use sed for extremely specific, well-tested patterns
- If in doubt, use Edit tool instead

**Good Alternative**:
```python
# DO: Use Edit tool with exact string matching
Edit(
    file_path="...",
    old_string="exact string to replace",
    new_string="exact replacement"
)
```

## Development Commands

```bash
# Ingestion
python -m src.ingestion.gmail      # Fetch from Gmail
python -m src.ingestion.substack   # Fetch from RSS

# Processing
python -m src.processors.summarizer --newsletter-id <id>
python -m src.processors.digest_creator --type daily

# Celery (for scheduled tasks)
celery -A src.tasks worker --loglevel=info
celery -A src.tasks beat --loglevel=info

# API server
uvicorn src.api.app:app --reload

# Tests
pytest
pytest tests/agents/claude/  # Test specific framework
pytest -k "test_summarization"  # Run specific tests

# Linting & Type Checking
ruff check src/
mypy src/
```

## Environment Configuration

Required in `.env`:
```bash
# Databases
DATABASE_URL=postgresql://localhost/newsletters
REDIS_URL=redis://localhost:6379
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password

# Agent Framework APIs
ANTHROPIC_API_KEY=sk-ant-...  # Required for Claude SDK
OPENAI_API_KEY=sk-...         # Optional for framework comparison
GOOGLE_API_KEY=...            # Optional for framework comparison

# Gmail
GMAIL_CREDENTIALS_FILE=credentials.json
GMAIL_TOKEN_FILE=token.json

# Email Delivery (for production)
SENDGRID_API_KEY=...

# Environment
ENVIRONMENT=development  # or production
```

## Model Selection & Configuration

The system uses a flexible, YAML-based model configuration system that supports multiple LLM providers with automatic failover and per-provider pricing.

### Architecture Overview

The model configuration system consists of three layers:

1. **Model Registry** (`src/config/model_registry.yaml`): Defines all available models, their providers, and pricing
2. **ModelConfig Class** (`src/config/models.py`): Python interface for model selection and provider management
3. **Processor Integration**: Each processor (summarizer, theme analyzer, digest creator) uses ModelConfig

### Pipeline Steps

The newsletter processing pipeline has four distinct LLM steps, each configurable independently:

| Step | Purpose | Default Model | Optimization Strategy |
|------|---------|---------------|----------------------|
| **SUMMARIZATION** | Extract key points from individual newsletters | Claude Haiku | Fast, cost-effective for straightforward extraction |
| **THEME_ANALYSIS** | Identify patterns across multiple summaries | Claude Sonnet | Quality-critical; benefits from stronger reasoning |
| **DIGEST_CREATION** | Generate multi-audience formatted output | Claude Sonnet | Quality-critical; customer-facing content |
| **HISTORICAL_CONTEXT** | Query knowledge graph for related themes | Claude Haiku | Simple queries; speed matters |

### Model ID System

The project uses **family-based model IDs** for user-facing configuration, while internally managing provider-specific identifiers for API calls.

**Family-Based IDs** (what you use in code and config):
- Format: `claude-sonnet-4-5` (no version dates)
- Stable across provider and version updates
- Used in: Environment variables, ModelConfig, database `model_used` field
- Example: `config = ModelConfig(summarization="claude-haiku-4-5")`

**Provider-Specific IDs** (managed internally):
- Format varies by provider:
  - Anthropic: `claude-sonnet-4-5-20250929` (includes release date)
  - AWS Bedrock: `anthropic.claude-sonnet-4-5-20250929-v1:0` (namespace prefix)
  - Google Vertex AI: `claude-sonnet-4-5@20250929` (@ separator)
- Stored in `model_registry.yaml` under `provider_model_id`
- Automatically selected for API calls based on provider
- Version tracked separately in database `model_version` field

**Benefits**:
- **Multi-version support**: Different providers can use different release versions
- **Cleaner code**: No version dates in application code
- **Easier updates**: Change provider-specific IDs without code changes
- **Better tracking**: Separate general ID and version in database

**Example**:
```python
# You use family-based ID
config = ModelConfig(summarization="claude-sonnet-4-5")

# System automatically uses correct provider ID for API:
# - Anthropic: "claude-sonnet-4-5-20250929"
# - AWS Bedrock: "anthropic.claude-sonnet-4-5-20250929-v1:0"
# - Vertex AI: "claude-sonnet-4-5@20250929"
```

### Configuration Methods

#### 1. Environment-Based (Recommended for Production)

Set model IDs via environment variables (defined in `.env`):

```bash
# Use Haiku for cost optimization (family-based IDs)
MODEL_SUMMARIZATION=claude-haiku-4-5
MODEL_THEME_ANALYSIS=claude-haiku-4-5
MODEL_DIGEST_CREATION=claude-haiku-4-5
MODEL_HISTORICAL_CONTEXT=claude-haiku-4-5

# Provider API keys
ANTHROPIC_API_KEY=sk-ant-...
```

#### 2. Code-Based Configuration

For custom workflows or testing:

```python
from src.config.models import ModelConfig, ModelStep, Provider, ProviderConfig

# Configure specific models per step (using family-based IDs)
config = ModelConfig(
    summarization="claude-haiku-4-5",      # Fast extraction
    theme_analysis="claude-sonnet-4-5",    # Better reasoning
    digest_creation="claude-sonnet-4-5",   # Quality output
    historical_context="claude-haiku-4-5", # Simple queries
    providers=[
        ProviderConfig(provider=Provider.ANTHROPIC, api_key="sk-ant-...")
    ]
)

# Use in processors
from src.processors.summarizer import NewsletterSummarizer
summarizer = NewsletterSummarizer(model_config=config)
```

#### 3. Model Override at Runtime

Override model for specific operations:

```python
# Override model for a single operation
from src.agents.claude import ClaudeAgent

agent = ClaudeAgent(
    model_config=config,
    model="claude-opus-4-5"  # Override to highest quality (family-based ID)
)
```

### Provider Configuration & Failover

#### Multi-Provider Setup

Configure multiple providers for the same model (automatic failover):

```python
config = ModelConfig(
    providers=[
        # Primary: Direct Anthropic API
        ProviderConfig(
            provider=Provider.ANTHROPIC,
            api_key="sk-ant-primary-...",
        ),
        # Backup: AWS Bedrock (different pricing)
        ProviderConfig(
            provider=Provider.AWS_BEDROCK,
            api_key="bedrock-key-...",
            region="us-east-1"
        ),
        # Tertiary: Vertex AI
        ProviderConfig(
            provider=Provider.VERTEX_AI,
            api_key="vertex-key-...",
            project_id="my-project"
        )
    ]
)
```

**Failover Behavior**:
- Providers are tried in order of configuration
- If primary fails (API error, rate limit), automatically tries next provider
- All failures are logged; last error is raised if all providers fail
- Provider used is tracked in `provider_used` attribute for cost calculation

#### Provider-Specific Pricing

The same model costs differently on different providers:

```yaml
# In model_registry.yaml (family-based keys, provider-specific IDs)
anthropic.claude-sonnet-4-5:
  provider_model_id: "claude-sonnet-4-5-20250929"  # Provider-specific ID for API calls
  cost_per_mtok_input: 3.00   # $3/MTok
  cost_per_mtok_output: 15.00  # $15/MTok

aws_bedrock.claude-sonnet-4-5:
  provider_model_id: "anthropic.claude-sonnet-4-5-20250929-v1:0"  # Bedrock format
  cost_per_mtok_input: 3.00
  cost_per_mtok_output: 15.00

google_vertex.claude-sonnet-4-5:
  provider_model_id: "claude-sonnet-4-5@20250929"  # Vertex format
  cost_per_mtok_input: 3.00
  cost_per_mtok_output: 15.00
```

### Cost Optimization Strategies

#### Strategy 1: Mixed Model Configuration (Recommended)

Use cheaper models for simple tasks, premium models for quality-critical steps:

```python
# Cost-optimized configuration (family-based IDs)
config = ModelConfig(
    summarization="claude-haiku-4-5",      # $0.80/MTok input, $4/MTok output
    theme_analysis="claude-sonnet-4-5",    # $3/MTok input, $15/MTok output
    digest_creation="claude-sonnet-4-5",   # $3/MTok input, $15/MTok output
    historical_context="claude-haiku-4-5", # $0.80/MTok input, $4/MTok output
)

# Cost savings example (processing 100 newsletters):
# - Summarization: 100 newsletters × ~2K tokens = ~$0.80 (Haiku) vs ~$3.00 (Sonnet)
# - Theme analysis: 5 analyses × ~5K tokens = ~$0.38 (Sonnet)
# - Digest creation: 7 digests × ~8K tokens = ~$1.20 (Sonnet)
# Total: ~$2.38 vs ~$4.58 (all Sonnet) = 48% cost reduction
```

#### Strategy 2: Quality-First Configuration

Use premium models for all steps when quality is paramount:

```python
# Maximum quality configuration (family-based IDs)
config = ModelConfig(
    summarization="claude-sonnet-4-5",
    theme_analysis="claude-opus-4-5",      # Highest reasoning capability
    digest_creation="claude-opus-4-5",
    historical_context="claude-sonnet-4-5",
)
```

#### Strategy 3: Budget-Constrained Configuration

Use fastest, cheapest models for all steps:

```python
# Maximum cost savings (family-based IDs)
config = ModelConfig(
    summarization="claude-haiku-4-5",
    theme_analysis="claude-haiku-4-5",
    digest_creation="claude-haiku-4-5",
    historical_context="claude-haiku-4-5",
)
```

#### Cost Tracking

All processors track token usage and calculate costs:

```python
from src.processors.theme_analyzer import ThemeAnalyzer

analyzer = ThemeAnalyzer(model_config=config)
result = await analyzer.analyze_themes(request)

# Access cost data
print(f"Tokens: {result.token_usage} ({result.input_tokens} in, {result.output_tokens} out)")
print(f"Cost: ${result.cost:.4f}")
print(f"Model used: {result.model_used}")
print(f"Provider: {analyzer.provider_used.value}")
```

### Adding New Models

#### 1. Add Model to Registry

Edit `src/config/model_registry.yaml`:

```yaml
models:
  # Add new model definition (family-based ID)
  claude-opus-4-5:
    family: claude
    name: "Claude 4.5 Opus"
    supports_vision: true
    supports_video: false
    default_version: "20251024"

provider_model_configs:
  # Add provider-specific configuration
  anthropic.claude-opus-4-5:
    provider_model_id: "claude-opus-4-5-20251024"  # Actual API identifier
    cost_per_mtok_input: 15.00
    cost_per_mtok_output: 75.00
    context_window: 200000
    max_output_tokens: 8192
```

#### 2. Use New Model

Set in environment or code:

```bash
# Environment (use family-based ID)
MODEL_THEME_ANALYSIS=claude-opus-4-5
```

```python
# Code (use family-based ID)
config = ModelConfig(
    theme_analysis="claude-opus-4-5"
)
```

### Adding New Providers

#### 1. Add Provider Enum

Edit `src/config/models.py`:

```python
class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    AWS_BEDROCK = "aws_bedrock"
    VERTEX_AI = "vertex_ai"
    AZURE_OPENAI = "azure_openai"
    MY_NEW_PROVIDER = "my_new_provider"  # Add here
```

#### 2. Add Provider Configuration to YAML

```yaml
provider_model_configs:
  my_new_provider.claude-sonnet-4-5:
    provider_model_id: "provider-specific-identifier"  # Your provider's API identifier
    cost_per_mtok_input: 3.00
    cost_per_mtok_output: 15.00
    context_window: 200000
    max_output_tokens: 8192
```

#### 3. Implement Provider Client (if needed)

For providers with different APIs, add implementation in processors:

```python
# In src/processors/theme_analyzer.py
def _call_llm_with_provider(self, provider_config: ProviderConfig, prompt: str):
    if provider_config.provider == Provider.MY_NEW_PROVIDER:
        # Custom implementation for new provider
        client = MyNewProviderClient(api_key=provider_config.api_key)
        response = client.generate(prompt=prompt, model=self.model)
        return response
    elif provider_config.provider == Provider.ANTHROPIC:
        # Existing implementation
        ...
```

### Testing Different Model Combinations

The test suite includes comprehensive tests for different model configurations:

```bash
# Run model combination tests
pytest tests/integration/test_e2e_model_combinations.py -v

# Tests include:
# - Haiku-only configuration (fast/cheap)
# - Sonnet-only configuration (quality)
# - Mixed configuration (optimized)
# - Cost calculation verification
# - Provider failover
# - Model override at agent level
```

### Configuration Best Practices

1. **Start with Mixed Configuration**: Use Haiku for summarization/historical context, Sonnet for theme analysis/digest creation
2. **Monitor Costs**: Track token usage and costs per pipeline run to optimize
3. **Test Before Production**: Use test configurations to verify behavior before changing production settings
4. **Provider Redundancy**: Configure at least 2 providers for production to handle API issues
5. **Environment Variables**: Use env vars for production; code-based config for testing
6. **Model Families**: Stick to same family (Claude) for consistency unless comparing frameworks

### Model Registry Reference

Current available models (see `model_registry.yaml` for full list):

**Note**: Model IDs are now family-based (no version dates). The system automatically uses the correct provider-specific identifier for API calls.

**Claude Family**:
- `claude-haiku-4-5`: Fastest, cheapest ($0.80/$4 per MTok)
- `claude-sonnet-4-5`: Balanced quality/cost ($3/$15 per MTok)
- `claude-opus-4-5`: Highest quality ($15/$75 per MTok)
- `claude-sonnet-4`: Legacy Claude Sonnet 4 ($3/$15 per MTok)

**Gemini Family** (for framework comparison):
- `gemini-2.0-flash`: Fast, affordable, 1M context
- `gemini-2.0-pro`: High quality, 2M context

**OpenAI Family**:
- `gpt-4o`: Standard GPT-4o
- `gpt-4o-mini`: Smaller, faster GPT-4o
- `o1-mini`: Reasoning-focused model
- `gemini-2.0-pro-001`: Premium quality

**GPT Family** (for framework comparison):
- `gpt-4.5-turbo-2025-02-27`: Latest GPT-4.5
- `gpt-4o-2024-11-20`: Multimodal GPT-4o

### Troubleshooting

**Model not found**: Ensure model ID matches exactly in `model_registry.yaml`

```python
# Check available models
from src.config.models import MODEL_REGISTRY
print(MODEL_REGISTRY.keys())
```

**Provider API error**: Check API keys in `.env` and provider status

```bash
# Verify environment variables
echo $ANTHROPIC_API_KEY
```

**Unexpected costs**: Verify provider-specific pricing in YAML matches actual provider pricing

```python
# Check cost calculation (use family-based ID)
cost = config.calculate_cost(
    model_id="claude-sonnet-4-5",
    input_tokens=1000,
    output_tokens=500,
    provider=Provider.ANTHROPIC
)
print(f"Estimated cost: ${cost:.4f}")
```

## Content Guidelines

### Digest Structure
- **Executive Summary**: 2-3 sentences for leadership (what matters and why)
- **Strategic Insights**: CTO-level implications and decisions
- **Technical Deep-Dives**: Developer-focused details and implementations
- **Emerging Trends**: New topics (with historical context from Graphiti)
- **Actionable Recommendations**: Specific actions for different roles
- **Sources**: Links to original newsletters

### Tone
- Professional but accessible
- Strategic perspective with tactical grounding
- Data-driven insights
- Cross-functional relevance (technical + business)
- References to previous discussions/trends for continuity

## Learning Goals

This project serves as a comparison framework for agent development kits:
- Document developer experience for each framework
- Compare API design, tool use, orchestration patterns
- Benchmark performance (speed, quality, token usage)
- Analyze cost implications
- Identify strengths/weaknesses for different use cases
- Produce comprehensive comparison documentation

## Implementation Patterns & Lessons (Phase 1)

### Progress Tracking
**CRITICAL**: Always update PROJECT_PLAN.md as tasks are completed by marking checkboxes `[x]`.
- This helps recover from Claude Code freezes/interruptions
- Provides clear visibility into what's done vs. what's pending
- Use section-level checkmarks (e.g., "### 1.1 Project Setup ✅") when all sub-items complete
- Update immediately after completing each major task, not in batches

### Running Scripts
**Always activate virtual environment first**:
```bash
source .venv/bin/activate  # Required before running any Python scripts
python scripts/script_name.py
```

Do NOT use:
- `python3 scripts/...` without venv activation
- `PYTHONPATH=. python3 scripts/...` as a workaround

### Code Architecture Patterns

#### Client-Service Pattern
For data ingestion, use two-layer architecture:
1. **Client**: Fetches/parses data from external source (Gmail API, RSS feeds)
   - `GmailClient`, `SubstackRSSClient`
   - Returns `NewsletterData` (Pydantic model)
   - No database interaction

2. **Service**: Business logic + database persistence
   - `GmailIngestionService`, `SubstackIngestionService`
   - Uses Client to fetch data
   - Handles deduplication, database storage, error handling
   - Returns count of ingested items

Example:
```python
# Client - data fetching only
client = SubstackRSSClient()
newsletters = client.fetch_feed(url)

# Service - business logic + persistence
service = SubstackIngestionService()
count = service.ingest_newsletters(feed_urls)
```

#### Configuration Flexibility
Support multiple configuration methods for better UX:
- **Environment variables**: For simple cases, CI/CD
- **Config files**: For complex lists, better developer experience
- **Command-line arguments**: For one-off overrides

Example (RSS feeds):
```python
# Priority: CLI args > env var > config file
def get_rss_feed_urls(self) -> list[str]:
    feeds = []
    if self.rss_feeds:  # Env var (comma-separated)
        feeds.extend(self.rss_feeds.split(","))
    if os.path.exists(self.rss_feeds_file):  # Config file (one per line)
        feeds.extend(read_file_lines())
    return list(dict.fromkeys(feeds))  # Deduplicate
```

### Database Patterns

#### Deduplication
Always check for existing records before inserting:
```python
existing = db.query(Newsletter).filter(
    Newsletter.source_id == newsletter_data.source_id
).first()

if existing:
    if force_reprocess:
        # Update and reset status
        existing.status = ProcessingStatus.PENDING
    else:
        continue  # Skip, already exists
```

#### Session Management
Use context managers for proper cleanup:
```python
with get_db() as db:
    # Database operations
    db.add(newsletter)
    # Auto-commits on success, rolls back on exception
```

#### Force Reprocess Flag
Provide `--force` flag in CLI scripts for reprocessing:
- Updates existing records with fresh data
- Resets status to PENDING for reprocessing
- Essential for testing and iteration

### Error Handling

#### Individual Item Failures
Don't crash entire batch if one item fails:
```python
for item in items:
    try:
        process(item)
        logger.info(f"Success: {item.title}")
    except Exception as e:
        logger.error(f"Failed {item.title}: {e}")
        db.rollback()
        continue  # Keep processing other items
```

#### Logging Strategy
- Use structured logging: `logger = get_logger(__name__)`
- Log at appropriate levels:
  - `DEBUG`: Detailed parsing/processing info
  - `INFO`: Major operations (ingested X newsletters)
  - `WARNING`: Unexpected but handled (missing fields, using defaults)
  - `ERROR`: Failures with context

### Content Extraction Patterns

#### RSS/HTML Parsing
Try multiple fields with fallbacks:
```python
# Try content field (full article)
if hasattr(entry, 'content') and entry.content:
    for content_item in entry.content:
        if content_item.get('type') == 'text/html':
            return content_item.get('value')

# Fallback to summary
if hasattr(entry, 'summary'):
    return entry.summary

# Last resort
logger.warning(f"No content found for: {entry.title}")
return ""
```

#### Date Parsing
Handle multiple date formats gracefully:
```python
# Try published_parsed
if hasattr(entry, 'published_parsed') and entry.published_parsed:
    try:
        return datetime(*entry.published_parsed[:6])
    except (ValueError, TypeError):
        pass

# Fallback with warning
logger.warning(f"Could not parse date, using current time")
return datetime.now()
```

### Logging Configuration

#### Suppress Verbose Libraries
AI/ML libraries can flood logs with embeddings and debug info:
```python
# In setup_logging()
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("graphiti_core").setLevel(logging.WARNING)
logging.getLogger("neo4j").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
```

### Testing Strategy

#### Prefer Unit Tests Over One-Off Scripts
When implementing new features, create proper unit tests instead of one-off bash scripts:
- **Reproducible**: Tests can be run repeatedly without side effects
- **Documented**: Tests serve as executable documentation
- **Regression prevention**: Catches breaking changes automatically
- **Coverage tracking**: Identify untested code paths

Example: Instead of running `python -c "from src.utils.digest_formatter import..."` to verify digest formatting, create `tests/test_utils/test_digest_formatter.py` with comprehensive test cases.

#### Unit Testing Patterns

##### Organizing Tests
Mirror the source code structure in tests:
```
src/
  utils/
    digest_formatter.py
  processors/
    digest_creator.py

tests/
  test_utils/
    __init__.py
    test_digest_formatter.py
  test_processors/
    __init__.py
    test_digest_creator.py
```

##### Fixture Usage
Use pytest fixtures for reusable test data:
```python
@pytest.fixture
def sample_digest_data() -> DigestData:
    """Create sample digest data for testing."""
    return DigestData(
        digest_type=DigestType.DAILY,
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 1, 23, 59, 59),
        title="AI/Tech Digest - January 1, 2025",
        executive_overview="Summary text...",
        strategic_insights=[...],
        # ... full sample data
    )

def test_to_markdown(sample_digest_data):
    """Test markdown formatting."""
    result = DigestFormatter.to_markdown(sample_digest_data)
    assert "# AI/Tech Digest" in result
    assert "## Executive Overview" in result
```

##### Testing Output Formatters
For text/HTML/markdown formatters, verify:
1. **Structure**: Headers, sections appear in correct order
2. **Content**: All data fields are rendered
3. **Edge cases**: Empty sections, missing optional fields
4. **Format-specific**: Links in HTML, escaping, styling

```python
def test_markdown_empty_sections():
    """Test markdown formatting with empty optional sections."""
    minimal_digest = DigestData(
        title="Minimal Digest",
        executive_overview="Summary only.",
        strategic_insights=[],  # Empty
        technical_developments=[],  # Empty
        # ...
    )
    result = DigestFormatter.to_markdown(minimal_digest)

    # Should have required sections
    assert "# Minimal Digest" in result
    assert "## Executive Overview" in result

    # Empty sections should not appear
    assert "## Strategic Insights" not in result
```

##### Testing Complex Classes (with Dependencies)
Use mocking for classes with external dependencies (databases, LLMs, APIs):

```python
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.mark.asyncio
async def test_create_digest_success(sample_themes, sample_newsletters):
    """Test successful digest creation."""
    request = DigestRequest(...)

    # Mock theme analyzer
    theme_result = ThemeAnalysisResult(...)
    with patch("src.processors.digest_creator.ThemeAnalyzer") as mock_analyzer_class:
        mock_analyzer = AsyncMock()
        mock_analyzer.analyze_themes.return_value = theme_result
        mock_analyzer_class.return_value = mock_analyzer

        # Mock database fetch
        with patch.object(DigestCreator, "_fetch_newsletters", return_value=sample_newsletters):
            # Mock LLM call
            with patch.object(DigestCreator, "_generate_digest_content", return_value=mock_llm_response):
                creator = DigestCreator()
                digest = await creator.create_digest(request)

    # Verify results
    assert isinstance(digest, DigestData)
    assert digest.newsletter_count == 2
```

##### Testing Private Methods
Test private helper methods directly when they contain complex logic:
```python
def test_build_themes_context(sample_themes):
    """Test themes context string building."""
    creator = DigestCreator()
    context = creator._build_themes_context(sample_themes)

    assert "Large Language Models" in context
    assert "Relevance:" in context
    assert "Context windows expanding" in context
```

##### Running Tests
```bash
# Activate venv first
source .venv/bin/activate

# Run all tests
pytest

# Run specific test file
pytest tests/test_utils/test_digest_formatter.py -v

# Run tests matching pattern
pytest -k "test_markdown"

# Run with coverage
pytest --cov=src tests/
```

##### Test Coverage Goals
- **Formatters/Utilities**: Aim for 95%+ coverage
- **Core Business Logic**: Aim for 90%+ coverage
- **Integration Points**: Focus on edge cases and error handling
- **Mock external dependencies**: Databases, APIs, LLM calls

Example from digest generation:
- `digest_formatter.py`: 99% coverage (10 tests)
- `digest_creator.py`: 94% coverage (9 tests)

#### Test with Real Data (Integration Testing)
After unit tests pass, verify with real sources:
```bash
# Test Gmail ingestion with actual Gmail account
python scripts/ingest_gmail.py --max 3

# Test RSS with real Substack feed
python scripts/ingest_substack.py --feeds https://example.substack.com/feed --max 3
```

#### Verify in Database
After ingestion, check database to verify data quality:
```bash
docker exec -it newsletter-postgres psql -U newsletter_user -d newsletters
SELECT id, title, publication, status FROM newsletters LIMIT 5;
```

### Common Pitfalls to Avoid

1. **Not activating venv**: Always `source .venv/bin/activate` first
2. **Forgetting to update PROJECT_PLAN.md**: Update after each major completion
3. **Hardcoding configuration**: Use settings from config.py
4. **Crashing on single failure**: Wrap individual items in try/except, continue batch
5. **Poor error messages**: Include context (item name/id) in error logs
6. **Not handling duplicates**: Always check source_id before inserting
7. **Verbose logging**: Configure library log levels to avoid clutter
