# Architecture

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

## System Architecture

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
    theme.py
  storage/          # Data persistence
    database.py     # PostgreSQL
    graphiti_client.py  # Graphiti MCP integration
  processors/       # Core processing
    summarizer.py
    theme_analyzer.py
    digest_creator.py
    historical_context.py
  delivery/         # Output channels
    email.py
    web.py
  tasks/            # Celery tasks
  api/              # FastAPI app
  config/           # Configuration
    models.py       # Model registry and configuration
    settings.py     # Application settings
    model_registry.yaml  # Model definitions and provider configs
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

This enables **direct performance comparisons** across frameworks:
- API design differences
- Tool use patterns
- Orchestration approaches
- Performance (speed, quality, token usage)
- Cost implications

## Data Models

### Newsletter
- Source metadata (Gmail, RSS)
- Raw content (HTML, text)
- Processing status
- Publication information

### NewsletterSummary
- Structured extraction from newsletter
- Key themes, insights, technical details
- Relevance scores (CTO, teams, individuals)
- Model and cost tracking

### ThemeAnalysis
- Cross-newsletter theme detection
- Trend classification (emerging, growing, established)
- Historical context integration
- Relevance scoring

### Digest
- Multi-audience formatted output
- Strategic insights (CTO-level)
- Technical developments (practitioner-level)
- Emerging trends with historical context
- Actionable recommendations per role

## Processing Stages

### Stage 1: Ingestion
**Input**: Gmail messages, RSS feed items
**Output**: Raw newsletters in database
**Technology**: Gmail API, feedparser, SQLAlchemy

### Stage 2: Summarization
**Input**: Raw newsletter content
**Output**: Structured summary with metadata
**Technology**: Claude Haiku (default), Pydantic validation
**Cost**: ~$0.01-0.02 per newsletter

### Stage 3: Knowledge Graph Population
**Input**: Newsletter summaries
**Output**: Entities and relationships in Graphiti
**Technology**: Graphiti MCP, Neo4j
**Purpose**: Enable temporal analysis and historical context

### Stage 4: Theme Analysis
**Input**: Multiple summaries + Graphiti context
**Output**: Cross-cutting themes with trends and relevance
**Technology**: Claude Sonnet (default), Graphiti queries
**Cost**: ~$0.05-0.10 per analysis (5-10 newsletters)

### Stage 5: Digest Creation
**Input**: Theme analysis + historical context
**Output**: Multi-audience formatted digest
**Technology**: Claude Sonnet (default)
**Cost**: ~$0.10-0.15 per digest

### Stage 6: Delivery
**Input**: Completed digest
**Output**: Email, web view
**Technology**: SendGrid (email), FastAPI (web)

## Scalability Considerations

- **Database**: PostgreSQL with indexes on frequently queried fields (status, dates)
- **Async Processing**: Celery for background tasks, Redis for task queue
- **Knowledge Graph**: Neo4j optimized for temporal queries
- **Caching**: Redis for frequently accessed data
- **Provider Failover**: Automatic fallback across multiple LLM providers
- **Cost Control**: Configurable model selection per pipeline step
