# Agentic Newsletter Aggregator - Documentation

**An agentic AI solution for aggregating and summarizing AI newsletters into daily and weekly digests.**

## Quick Links

- **[Setup Guide](SETUP.md)** - Get started with local development
- **[Architecture](ARCHITECTURE.md)** - Tech stack, system design, and key workflows
- **[Model Configuration](MODEL_CONFIGURATION.md)** - LLM model selection, providers, and cost optimization
- **[Development Guide](DEVELOPMENT.md)** - Commands, patterns, and best practices
- **[Content Guidelines](CONTENT_GUIDELINES.md)** - Digest structure, tone, and formatting standards
- **[Gotchas](GOTCHAS.md)** - Critical pitfalls organized by area (database, testing, deployment, etc.)

## Project Overview

**Purpose**: Help technical leaders and developers at Comcast stay informed on AI/Data trends

**Voice**: Strategic leadership spanning CTO-level strategy to individual practitioner best practices

**Sources**: Gmail and Substack RSS feeds

**Output**: Structured digests analyzing themes across newsletters, with knowledge graph-powered historical context

## Key Features

- **Multi-Framework Agent Comparison**: Claude SDK (primary), OpenAI, Google ADK, Microsoft frameworks
- **Knowledge Graph Integration**: Graphiti + Neo4j for temporal theme tracking and historical context
- **Multi-Audience Formatting**: Strategic insights for CTOs, tactical details for developers
- **Cost Optimization**: Configurable model selection per pipeline step
- **Provider Failover**: Automatic fallback across Anthropic, AWS Bedrock, Google Vertex AI

## Getting Started

1. **[Setup your development environment](SETUP.md#local-development)**
2. **[Configure your models and providers](MODEL_CONFIGURATION.md#configuration-methods)**
3. **[Run your first newsletter processing](DEVELOPMENT.md#development-commands)**
4. **[Review the content guidelines](CONTENT_GUIDELINES.md)** for digest quality standards

## Project Structure

```
src/
  agents/           # Agent framework implementations (Claude, OpenAI, Google, Microsoft)
  ingestion/        # Newsletter fetching (Gmail API, RSS)
  models/           # Data models (Pydantic + SQLAlchemy)
  storage/          # Data persistence (PostgreSQL, Graphiti)
  processors/       # Core processing (summarization, theme analysis, digest creation)
  delivery/         # Output channels (email, web)
  tasks/            # Celery background tasks
  api/              # FastAPI app
```

## Learning Goals

This project serves as a **comparison framework for agent development kits**:
- Document developer experience for each framework
- Compare API design, tool use, orchestration patterns
- Benchmark performance (speed, quality, token usage)
- Analyze cost implications
- Identify strengths/weaknesses for different use cases

See [Development Guide](DEVELOPMENT.md#learning-goals) for detailed findings.

## Contributing

This project follows:
- **Professional, objective tone** - Technical accuracy over validation
- **Behavior-based testing** - Tests validate behavior, not specific values
- **Cost-conscious defaults** - Haiku for extraction, Sonnet for reasoning
- **Multi-audience content** - CTOs get strategy, developers get tactics

See [Development Guide](DEVELOPMENT.md#development-guidelines) for full guidelines.
