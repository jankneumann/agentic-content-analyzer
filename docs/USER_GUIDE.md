# User Guide

A complete guide to using the Agentic Newsletter Aggregator — from first install to daily operation.

This system helps technical leaders and developers stay informed on AI, data, and technology trends by aggregating content from newsletters, RSS feeds, YouTube, podcasts, social media, and web searches into structured daily and weekly digests.

**Deployment model**: Single-user, bring-your-own compute and storage. You own your data, run your own infrastructure, and choose your cloud providers.

---

## Table of Contents

- [Interfaces](#interfaces)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [First Run](#first-run)
- [Configuration](#configuration)
  - [API Keys](#api-keys)
  - [Profiles](#profiles)
  - [Content Sources](#content-sources)
  - [LLM Models](#llm-models)
- [The Pipeline](#the-pipeline)
- [Web Interface](#web-interface)
  - [Dashboard](#dashboard)
  - [Content Management](#content-management)
  - [Summaries](#summaries)
  - [Theme Analysis](#theme-analysis)
  - [Digests](#digests)
  - [Review Workflow](#review-workflow)
  - [Podcast Scripts](#podcast-scripts)
  - [Podcasts & Audio](#podcasts--audio)
  - [Audio Digests](#audio-digests)
  - [Task History](#task-history)
  - [Settings](#settings)
- [Command-Line Interface](#command-line-interface)
  - [Ingesting Content](#ingesting-content)
  - [Summarizing Content](#summarizing-content)
  - [Creating Digests](#creating-digests)
  - [Running the Full Pipeline](#running-the-full-pipeline)
  - [Reviewing Digests](#reviewing-digests)
  - [Analyzing Themes](#analyzing-themes)
  - [Generating Podcasts](#generating-podcasts)
  - [Managing Prompts](#managing-prompts)
  - [Managing Settings](#managing-settings)
  - [Job Queue Management](#job-queue-management)
- [Mobile App (Capacitor)](#mobile-app-capacitor)
- [Desktop App (Tauri)](#desktop-app-tauri)
- [Deployment](#deployment)
  - [Local Development](#local-development)
  - [Cloud Deployment (Railway)](#cloud-deployment-railway)
  - [Database Providers](#database-providers)
  - [Storage Providers](#storage-providers)
  - [Neo4j Providers](#neo4j-providers)
  - [Observability](#observability)
- [Common Recipes](#common-recipes)
- [Troubleshooting](#troubleshooting)

---

## Interfaces

The aggregator can be accessed through multiple interfaces, each suited to different use cases:

| Interface | Status | Best For |
|-----------|--------|----------|
| **Web UI** | Available | Daily operation, reviewing digests, listening to podcasts, managing settings |
| **CLI** (`aca`) | Available | Automation, scripting, pipeline orchestration, power users |
| **Mobile App** (Capacitor) | Planned | On-the-go reading, push notifications, commute listening |
| **Desktop App** (Tauri) | Planned | Native OS integration, system tray, offline access |

The web UI and CLI share the same backend API, so anything done in one is immediately reflected in the other. The mobile and desktop apps will also connect to the same API, providing a consistent experience across all platforms.

---

## Getting Started

### Prerequisites

| Requirement | Purpose |
|-------------|---------|
| **Python 3.12+** | Backend runtime |
| **Docker + Docker Compose** | PostgreSQL, Neo4j, and supporting services |
| **[uv](https://github.com/astral-sh/uv)** | Python package manager |
| **Node.js 20+ & pnpm** | Frontend build tools |
| **Anthropic API key** | Core LLM for summarization and digest creation |

Optional API keys unlock additional sources:

| Key | Unlocks |
|-----|---------|
| Google API key + OAuth | Gmail ingestion, YouTube playlists |
| Gemini API key | Native video content extraction from YouTube |
| OpenAI API key | Audio transcription (Whisper), TTS for podcasts |
| xAI (Grok) API key | X/Twitter search ingestion |
| Perplexity API key | Web search ingestion via Sonar API |
| ElevenLabs API key | High-quality voice synthesis for podcasts |

### Installation

1. **Install uv** (if not already installed):

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2. **Clone and set up the Python environment**:

```bash
cd agentic-newsletter-aggregator
uv venv
source .venv/bin/activate    # macOS/Linux
uv sync --all-extras         # Install all dependencies
```

3. **Configure your environment**:

```bash
cp .env.example .env
# Edit .env and add at minimum: ANTHROPIC_API_KEY
```

Or use profile-based configuration (recommended):

```bash
# Create your secrets file
cat > .secrets.yaml << 'EOF'
ANTHROPIC_API_KEY: sk-ant-your-key-here
# Add other keys as needed
EOF

export PROFILE=local
```

4. **Start infrastructure services**:

```bash
docker compose up -d         # PostgreSQL + Neo4j
alembic upgrade head         # Initialize the database schema
```

5. **Install the frontend**:

```bash
cd web
pnpm install
cd ..
```

6. **Verify everything is working**:

```bash
aca manage verify-setup      # Check service connectivity
```

You should see green checkmarks for Database, Neo4j, and LLM API.

### First Run

Start both backend and frontend:

```bash
make dev-bg                  # Starts API (port 8000) + frontend (port 5173)
```

Open **http://localhost:5173** in your browser. You'll see the dashboard — empty for now.

Run your first pipeline to populate it:

```bash
# Ingest from pre-configured RSS feeds
aca ingest rss --max 5

# Summarize the ingested content
aca summarize pending

# Create your first daily digest
aca create-digest daily
```

Go back to the web UI. Your dashboard now shows content, summaries, and a digest ready for review.

---

## Configuration

### API Keys

API keys can be stored in three places (highest to lowest priority):

1. **Environment variables** — always win
2. **Profile settings** — in `profiles/*.yaml` referencing secrets
3. **Secrets file** — `.secrets.yaml` (gitignored)
4. **`.env` file** — traditional fallback

Example `.secrets.yaml`:

```yaml
ANTHROPIC_API_KEY: sk-ant-...
OPENAI_API_KEY: sk-...
GOOGLE_API_KEY: AIza...
XAI_API_KEY: xai-...
PERPLEXITY_API_KEY: pplx-...
ADMIN_API_KEY: your-admin-key    # Protects settings endpoints
APP_SECRET_KEY: your-secret-key  # Login password + JWT signing
```

Generate secure keys with:

```bash
aca manage generate-secret   # Outputs a 64-char random key
```

### Profiles

Profiles bundle configuration into named YAML files, replacing scattered `.env` variables. They support inheritance, secrets interpolation, and validation.

```bash
# See available profiles
aca profile list

# Activate a profile
export PROFILE=local

# Validate configuration
aca profile validate local

# Inspect fully resolved settings
aca profile inspect
```

Available profiles:

| Profile | Use Case |
|---------|----------|
| `local` | Docker Compose development, no observability |
| `local-opik` | Local with Opik tracing stack |
| `local-supabase` | Local with Supabase instead of raw PostgreSQL |
| `staging` | Remote backends (cloud DB + Braintrust) |
| `railway` | Production deployment on Railway |

Migrate from an existing `.env`:

```bash
aca profile migrate --env-file .env --output my-profile --dry-run
```

### Content Sources

Sources are configured in YAML files under `sources.d/`:

```
sources.d/
  _defaults.yaml           # Global defaults (max_entries, days_back)
  rss.yaml                 # RSS feed URLs
  gmail.yaml               # Gmail search queries
  substack.yaml            # Substack paid subscriptions
  youtube_playlist.yaml    # YouTube playlists (OAuth + Gemini)
  youtube_rss.yaml         # YouTube RSS feeds (public, no OAuth)
  podcasts.yaml            # Podcast feeds with transcript settings
  websearch.yaml           # Web search (Perplexity + Grok)
```

**Adding an RSS feed** — edit `sources.d/rss.yaml`:

```yaml
sources:
  - name: My Favorite Newsletter
    url: https://example.com/feed.xml
    tags: [ai, research]
    enabled: true
```

**Adding a YouTube playlist** — edit `sources.d/youtube_playlist.yaml`:

```yaml
sources:
  - name: AI Explained
    id: PLxxxxxxxxxxxxxxx
    tags: [ai, explainers]
    visibility: public
    gemini_summary: true
    gemini_resolution: default
```

**Adding a web search** — edit `sources.d/websearch.yaml`:

```yaml
sources:
  - name: AI Research Updates
    provider: perplexity
    prompt: "Latest AI research breakthroughs and papers this week"
    tags: [ai, research]
    max_results: 15
    recency_filter: week
```

**Syncing Substack subscriptions** automatically:

```bash
aca ingest substack-sync
# Paid subscriptions → sources.d/substack.yaml
# Free subscriptions → sources.d/rss.yaml
```

The system ships with 150+ pre-configured AI/tech RSS feeds ready to use.

### LLM Models

Different pipeline stages can use different models to balance cost and quality:

```bash
# .env or profile settings
MODEL_SUMMARIZATION=claude-haiku-4-5          # Fast, cost-effective
MODEL_THEME_ANALYSIS=claude-sonnet-4-5        # Quality reasoning
MODEL_DIGEST_CREATION=claude-sonnet-4-5       # Customer-facing output
MODEL_YOUTUBE_PROCESSING=gemini-2.5-flash     # Video extraction
MODEL_CAPTION_PROOFREADING=gemini-2.5-flash-lite  # Caption cleanup
```

Models can also be changed at runtime via the web UI Settings page or CLI:

```bash
aca settings set model.summarization claude-sonnet-4-5
```

---

## The Pipeline

The core workflow follows a three-stage pipeline:

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│   INGEST    │ ──▸ │  SUMMARIZE   │ ──▸ │ CREATE DIGEST │
│             │     │              │     │               │
│ Gmail       │     │ AI extracts: │     │ Aggregates    │
│ RSS feeds   │     │ • Key themes │     │ summaries     │
│ YouTube     │     │ • Insights   │     │ into daily or │
│ Podcasts    │     │ • Actions    │     │ weekly report │
│ X/Twitter   │     │ • Technical  │     │               │
│ Perplexity  │     │   details    │     │ Structured:   │
│ Files/URLs  │     │              │     │ • Insights    │
└─────────────┘     └──────────────┘     │ • Trends      │
                                         │ • Actions     │
                                         └───────────────┘
                                                │
                                    ┌───────────┼───────────┐
                                    ▼           ▼           ▼
                              ┌──────────┐ ┌────────┐ ┌─────────┐
                              │  REVIEW  │ │PODCAST │ │  AUDIO  │
                              │ approve/ │ │ script │ │ DIGEST  │
                              │ revise   │ │ + TTS  │ │ (TTS)   │
                              └──────────┘ └────────┘ └─────────┘
```

**Run it all in one command:**

```bash
aca pipeline daily           # Ingest → Summarize → Digest
```

Or step by step for more control — see the [CLI section](#command-line-interface).

---

## Web Interface

Access the web UI at **http://localhost:5173** (development) or your deployed URL. The interface features a collapsible sidebar, dark/light theme toggle, and responsive design for tablet and desktop.

### Dashboard

The home page provides a bird's-eye view of your entire system:

- **Pipeline status cards** — content count, summaries, themes, digests, scripts, podcasts
- **Metrics** — pending summarizations, pending reviews, generation counts
- **Quick actions** — one-click buttons to Ingest Content, Generate Summaries, Create Digest, or Review Scripts
- **Recent activity** — latest pipeline execution results and suggested next steps

### Content Management

**Path**: `/contents`

Browse all ingested content from every source. The content table shows:

- Title, source type (Gmail, RSS, YouTube, etc.), publication, status, and date
- **Status tracking**: Pending → Parsing → Parsed → Processing → Completed → or Failed
- **Filters**: By status and source type
- **Sortable columns**: Click any column header

**Viewing content**: Click the eye icon on any row to open a detail dialog showing:

- Full article content rendered as markdown
- Toggle to raw markdown source view
- Metadata (author, publication, parser used)
- Link to the original source

**Ingesting new content**: Click "Ingest New" to fetch from Gmail, RSS, YouTube, or upload local files.

### Summaries

**Path**: `/summaries`

View AI-generated summaries with real-time progress tracking:

- **Live progress bar** when summarization is running (with SSE updates)
- **Stats**: Total summaries, average processing time, tokens used, models used
- Each summary includes: executive summary, key themes, strategic insights, technical details, and actionable items

Click "Generate Summaries" to process all pending content.

### Theme Analysis

**Path**: `/themes`

Discover patterns across your content:

- **Theme cards** showing name, category, trend (emerging/growing/stable), description, and relevance score
- **Configurable analysis**: Set date range, max themes, minimum newsletter count, and relevance threshold
- Knowledge graph integration surfaces historical context

### Digests

**Path**: `/digests`

Your aggregated intelligence reports:

- **Daily digests** — summarize a single day's content
- **Weekly digests** — higher-level synthesis across the week
- Structured sections: Executive Overview, Strategic Insights, Technical Developments, Emerging Trends, Actionable Recommendations
- Each digest tracks its source content for traceability
- **Status workflow**: Generating → Pending Review → Approved → Delivered (or Rejected for revision)

Click "Generate Digest" and choose daily or weekly.

### Review Workflow

**Path**: `/review`

The review hub is where you approve or revise AI-generated content:

**Review queue** (`/review`):
- Lists all digests and scripts pending your review
- Shows count of pending items

**Digest review** (`/review/digest/:id`):
- **Split-pane layout**: Source summaries on the left, digest content on the right
- **Revision chat**: Select text and discuss changes with the AI
- **Navigation**: Previous/Next buttons to cycle through the queue
- **Actions**: Approve or Reject (request revision)

**Script review** (`/review/script/:id`):
- Same split-pane layout with script dialogue on the right
- Review speaker assignments, emphasis notes, and section flow

**Summary review** (`/review/summary/:id`):
- Original content on the left, generated summary on the right
- Verify accuracy and completeness

### Podcast Scripts

**Path**: `/scripts`

Two-host dialogue scripts generated from approved digests:

- **Script structure**: Opening, segments (by theme), closing — with speaker assignments (ALEX/SAM)
- **Length options**: Short, medium, or long
- **Review workflow**: Generate → Review → Approve → Generate Audio
- View full dialogue with speaker badges, emphasis notes, and theme tags

### Podcasts & Audio

**Path**: `/podcasts`

Generated podcast audio from approved scripts:

- **Built-in audio player** with play/pause, skip forward/back 10s, progress bar, volume control
- **Playback speed**: 0.5x to 2x
- **Download** completed audio files
- Metadata: duration, file size, voice provider, audio format

### Audio Digests

**Path**: `/audio-digests`

Single-voice TTS readings of digests (simpler than full podcast production):

- Generate from any completed digest
- Configure voice, speed, and TTS provider
- Same audio player controls as podcasts
- Delete to free up storage

### Task History

**Path**: `/task-history`

Audit log of all pipeline executions:

- **Filters**: Time range (24h/7d/30d/all), task type (summarize, ingest, extract, etc.), status
- Track what ran, when, and whether it succeeded
- Useful for debugging failed jobs

### Settings

**Path**: `/settings`

Configure the system without touching config files:

**LLM Prompts**:
- View and edit every prompt template used in the pipeline
- Test prompts with sample variables
- Reset individual prompts to defaults

**Model Configuration**:
- Select which LLM model handles each pipeline step
- See cost per million tokens for each option
- Changes take effect immediately

**Notifications**:
- Enable or disable notifications per event type

**Voice Configuration**:
- Select TTS provider and voice for podcasts and audio digests
- Configure speech speed

**API Connections**:
- Health dashboard showing database, Neo4j, LLM providers, storage, and audio services
- Auto-refreshes every 60 seconds

---

## Command-Line Interface

The `aca` CLI is available after activating your virtual environment. Every command supports `--help` for detailed options.

### Ingesting Content

```bash
# From configured sources
aca ingest gmail                          # Gmail newsletters
aca ingest rss                            # RSS feeds
aca ingest substack                       # Substack paid subscriptions
aca ingest youtube                        # All YouTube (playlists + RSS)
aca ingest youtube-playlist               # YouTube playlists only (requires OAuth)
aca ingest youtube-rss                    # YouTube RSS feeds only
aca ingest podcast                        # Podcast feeds
aca ingest xsearch                        # X/Twitter via Grok API
aca ingest perplexity-search              # Perplexity Sonar web search

# From specific content
aca ingest files report.pdf slides.pptx   # Local files
aca ingest url https://example.com/post   # Direct URL

# Common options (available on most ingest commands)
  --max, -m INT       Maximum items to fetch
  --days, -d INT      Only fetch from the last N days
  --force, -f         Reprocess content already ingested
```

Examples:

```bash
# Ingest the last 3 days of RSS, max 20 per feed
aca ingest rss --days 3 --max 20

# Search X/Twitter with a custom prompt
aca ingest xsearch --prompt "AI agent frameworks launched this week"

# Search Perplexity for recent AI news
aca ingest perplexity-search --prompt "AI regulation updates" --recency week
```

### Summarizing Content

```bash
# Summarize all pending content (queued for background processing)
aca summarize pending

# Summarize with a limit
aca summarize pending --limit 10

# Summarize a specific item
aca summarize id 42

# Run synchronously (useful for debugging)
aca summarize pending --sync
```

### Creating Digests

```bash
# Daily digest for today
aca create-digest daily

# Daily digest for a specific date
aca create-digest daily --date 2026-02-27

# Weekly digest for the current week
aca create-digest weekly

# Weekly digest for a specific week
aca create-digest weekly --week 2026-02-23
```

### Running the Full Pipeline

```bash
# Complete daily pipeline: ingest all sources → summarize → create digest
aca pipeline daily

# Full pipeline for a specific date
aca pipeline daily --date 2026-02-27

# Weekly pipeline
aca pipeline weekly

# Wait for all background jobs to complete before returning
aca pipeline daily --wait
```

The pipeline runs all ingestion sources in parallel, then summarizes, then creates the digest.

### Reviewing Digests

```bash
# List pending reviews
aca review list

# View a digest's content
aca review view 15

# Start interactive revision session
aca review revise 15

# Finalization happens automatically when you exit the revision session
# Type "done" or press Ctrl-D to finalize
```

### Analyzing Themes

```bash
# Analyze themes from the last 7 days (default)
aca analyze themes

# Custom date range and parameters
aca analyze themes --start 2026-02-01 --end 2026-02-28 --max-themes 20
```

### Generating Podcasts

```bash
# Generate a podcast script from an approved digest
aca podcast generate --digest-id 15

# Choose script length
aca podcast generate --digest-id 15 --length extended

# List existing scripts
aca podcast list-scripts
```

### Managing Prompts

Every AI prompt in the system is customizable:

```bash
# List all prompts, grouped by category
aca prompts list

# Filter by category
aca prompts list --category pipeline

# View a specific prompt
aca prompts show pipeline.summarization.system

# Override a prompt
aca prompts set pipeline.summarization.system --value "You are a technical analyst..."

# Or load from a file
aca prompts set pipeline.summarization.system --file my-prompt.txt

# Test a prompt with variables
aca prompts test digest.daily_prompt --var date=2026-02-28 --var count=15

# Reset to default
aca prompts reset pipeline.summarization.system

# Export/import for backup
aca prompts export --output my-prompts.yaml
aca prompts import --file my-prompts.yaml
```

### Managing Settings

```bash
# List all setting overrides
aca settings list

# Get a specific setting
aca settings get model.summarization

# Change a setting
aca settings set model.summarization claude-sonnet-4-5

# Reset to default
aca settings reset model.summarization
```

### Job Queue Management

Background jobs are processed by an embedded worker that runs with the API server:

```bash
# List recent jobs
aca jobs list

# Filter by status
aca jobs list --status failed

# View job details
aca jobs show abc-123

# Retry a failed job
aca jobs retry abc-123

# Retry all failed jobs
aca jobs retry --failed

# View job history
aca jobs history --since 7d --type summarize

# Clean up old completed jobs
aca jobs cleanup --older-than 30d
```

To run a standalone worker (for higher throughput):

```bash
aca worker start                    # Default: 5 concurrent tasks
aca worker start --concurrency 10   # Up to 20 concurrent tasks
```

---

## Mobile App (Capacitor)

> **Status**: Planned

The mobile app will wrap the existing web UI using [Capacitor](https://capacitorjs.com/), providing native mobile features on iOS and Android.

### Planned Features

- **Native app experience** — home screen icon, splash screen, smooth navigation
- **Push notifications** — alerts when new digests are ready for review
- **Offline reading** — cache digests and summaries for reading without connectivity
- **Audio playback** — background podcast/audio digest playback with lock screen controls
- **Share integration** — share articles or digest excerpts to other apps
- **Biometric auth** — Face ID / fingerprint for secure access

### Architecture

Capacitor wraps the React web app in a native WebView and provides JavaScript bridges to native APIs (push notifications, filesystem, biometrics). The same API backend serves both the web and mobile interfaces.

```
┌──────────────────────────────┐
│        Mobile Device         │
│  ┌────────────────────────┐  │
│  │   Capacitor Shell      │  │
│  │  ┌──────────────────┐  │  │
│  │  │  React Web App   │  │  │
│  │  │  (same codebase) │  │  │
│  │  └────────┬─────────┘  │  │
│  │           │             │  │
│  │  Native Plugins:       │  │
│  │  • Push Notifications  │  │
│  │  • Filesystem Cache    │  │
│  │  • Biometric Auth      │  │
│  │  • Background Audio    │  │
│  └────────────┬───────────┘  │
│               │              │
└───────────────┼──────────────┘
                │ HTTPS
                ▼
        ┌───────────────┐
        │  Backend API  │
        └───────────────┘
```

### Getting Started (When Available)

```bash
cd web
pnpm cap:init           # Initialize Capacitor project
pnpm cap:build          # Build web assets + sync to native
pnpm cap:run:ios        # Run on iOS simulator
pnpm cap:run:android    # Run on Android emulator
```

---

## Desktop App (Tauri)

> **Status**: Planned

The desktop app will use [Tauri](https://tauri.app/) to provide a lightweight native application for macOS, Windows, and Linux.

### Planned Features

- **System tray** — minimize to tray with badge count for pending reviews
- **Native notifications** — OS-level alerts for new digests and completed pipelines
- **Keyboard shortcuts** — global hotkeys for quick actions
- **Offline mode** — local database sync for reading without internet
- **Auto-start** — optional launch at login
- **Menu bar integration** (macOS) — quick status view and actions from the menu bar
- **Small binary size** — Tauri uses the OS WebView, keeping the app under 10 MB

### Architecture

Tauri embeds the React frontend in the OS-native WebView (WebKit on macOS, WebView2 on Windows, WebKitGTK on Linux) with a Rust backend for native API access. Unlike Electron, it does not bundle Chromium, resulting in a much smaller application.

```
┌────────────────────────────────────┐
│          Desktop App (Tauri)       │
│  ┌──────────────────────────────┐  │
│  │     OS Native WebView       │  │
│  │  ┌────────────────────────┐  │  │
│  │  │    React Web App       │  │  │
│  │  │    (same codebase)     │  │  │
│  │  └───────────┬────────────┘  │  │
│  │              │               │  │
│  │  Rust Backend:               │  │
│  │  • System tray / menu bar    │  │
│  │  • Native notifications      │  │
│  │  • File system access        │  │
│  │  • Auto-updater              │  │
│  │  • Global shortcuts          │  │
│  └──────────────┬───────────────┘  │
│                 │                  │
└─────────────────┼──────────────────┘
                  │ HTTPS
                  ▼
          ┌───────────────┐
          │  Backend API  │
          └───────────────┘
```

### Getting Started (When Available)

```bash
cd web
pnpm tauri:dev          # Development with hot reload
pnpm tauri:build        # Create distributable binary
```

---

## Deployment

### Local Development

The quickest way to get running:

```bash
# Start infrastructure
docker compose up -d                # PostgreSQL + Neo4j
alembic upgrade head                # Initialize database

# Start the application
make dev-bg                         # API (port 8000) + frontend (port 5173)

# Verify
make verify-profile                 # Health check
```

**Alternative stacks:**

```bash
# With Opik observability
make opik-up && make dev-opik       # Adds tracing UI at port 5174

# With local Supabase
make supabase-up && make dev-supabase  # Supabase DB + storage

# Full stack (core + Opik)
make full-up
```

**Stop everything:**

```bash
make dev-stop                       # Stop API + frontend
make full-down                      # Stop all Docker services
```

### Cloud Deployment (Railway)

Railway provides the simplest single-platform deployment:

1. **Create a Railway project** and add a PostgreSQL service

2. **Set environment variables** on the Railway service:

```bash
PROFILE=railway                     # Or set individual vars
ANTHROPIC_API_KEY=sk-ant-...
ADMIN_API_KEY=your-admin-key
APP_SECRET_KEY=your-secret-key
ALLOWED_ORIGINS=https://your-domain.com
```

3. **Deploy** — the Docker entrypoint automatically runs database migrations on startup

4. **Verify** — visit your Railway URL and check `/health` and `/ready` endpoints

**Important notes:**
- Cloud databases start empty — migrations run automatically via `docker-entrypoint.sh`
- Set `ALLOWED_ORIGINS` to your frontend URL to avoid CORS errors
- The Railway `PORT` is dynamic — the entrypoint handles this automatically

### Database Providers

Choose the PostgreSQL provider that fits your needs:

| Provider | Best For | Key Feature |
|----------|----------|-------------|
| **Local** (default) | Development | Full control, Docker Compose |
| **Supabase** | Cloud hosting | Built-in storage, free tier |
| **Neon** | Serverless workflows | Auto-scaling, database branching |
| **Railway** | Single-platform deploy | PostgreSQL extensions, integrated |

Set explicitly in your environment:

```bash
DATABASE_PROVIDER=local              # or supabase, neon, railway
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

**Neon branching** for safe experimentation:

```bash
aca neon create test-branch          # Create isolated copy
aca neon connection test-branch      # Get connection string
# ... test changes safely ...
aca neon delete test-branch          # Clean up
```

### Storage Providers

File storage (images, podcasts, audio digests) supports multiple backends:

| Provider | Best For |
|----------|----------|
| **Local** (default) | Development — files in `data/` directory |
| **S3** | AWS or S3-compatible (MinIO) |
| **Supabase** | Supabase Storage (S3-compatible API) |
| **Railway** | Railway's MinIO integration |

```bash
STORAGE_PROVIDER=local               # or s3, supabase, railway
```

### Neo4j Providers

The knowledge graph (for theme analysis and historical context):

| Provider | Best For |
|----------|----------|
| **Local** (default) | Development — via Docker Compose |
| **AuraDB** | Production — free tier at [console.neo4j.io](https://console.neo4j.io/) |

```bash
NEO4J_PROVIDER=local                 # or auradb
NEO4J_LOCAL_URI=bolt://localhost:7687
```

### Observability

Monitor your system with pluggable observability:

| Provider | Best For |
|----------|----------|
| **noop** (default) | No overhead, disabled |
| **Opik** | Self-hosted tracing (run `make opik-up`) |
| **Braintrust** | Cloud evaluations and scoring |
| **OTel** | Generic OTLP backend (Jaeger, Grafana) |

```bash
OBSERVABILITY_PROVIDER=opik          # or braintrust, otel, noop
```

---

## Common Recipes

### Daily routine: automated morning digest

```bash
# Run the complete pipeline
aca pipeline daily

# Then open the web UI to review
# http://localhost:5173/review
```

### Add a new RSS feed

Edit `sources.d/rss.yaml`:

```yaml
sources:
  # ... existing feeds ...
  - name: New Newsletter
    url: https://newsletter.example.com/feed
    tags: [ai, startups]
```

Then ingest:

```bash
aca ingest rss
```

### Create a podcast from a digest

```bash
# 1. Make sure you have an approved digest
aca review list
aca review revise 15                 # Type "done" to approve

# 2. Generate the podcast script
aca podcast generate --digest-id 15 --length standard

# 3. Review the script in the web UI at /scripts
# 4. Approve the script
# 5. Generate audio from the Podcasts page in the web UI
```

### Ingest a single article you found interesting

```bash
aca ingest url https://example.com/great-article --tag ai --tag research
aca summarize pending
```

### Search your content library

The web UI provides search across all ingested content. For CLI-based search:

```bash
# Backfill search index (first time only)
aca manage backfill-chunks

# Search is then available via the API
# GET /api/v1/search?q=transformer+architecture
```

### Switch LLM models for cost savings

```bash
# Use Haiku for summarization (cheaper, faster)
aca settings set model.summarization claude-haiku-4-5

# Use Sonnet for digests (higher quality, customer-facing)
aca settings set model_digest_creation claude-sonnet-4-5
```

### Export data between environments

```bash
# Export from local
aca sync export backup.jsonl --from-profile local

# Import to staging
aca sync import backup.jsonl --to-profile staging --mode replace

# Or push directly
aca sync push --from-profile local --to-profile staging
```

### Customize AI prompts

```bash
# See what prompts are available
aca prompts list

# View the current summarization prompt
aca prompts show pipeline.summarization.system

# Override it
aca prompts set pipeline.summarization.system --file my-custom-prompt.txt

# Test it
aca prompts test pipeline.summarization.system --var content="Sample article text"
```

---

## Troubleshooting

### Services won't start

```bash
# Check Docker is running
docker compose ps

# Restart services
docker compose down && docker compose up -d

# Verify connectivity
aca manage verify-setup
```

### Database migration errors

```bash
# Check for multiple migration heads
alembic heads

# If multiple heads, merge them
alembic merge heads -m "merge migration heads"

# Apply
alembic upgrade head
```

### "Connection refused" errors

- **Database**: Ensure PostgreSQL is running on port 5432 (`docker compose ps`)
- **Neo4j**: Ensure Neo4j is running on port 7687
- **API**: Ensure the backend is running on port 8000 (`make dev-bg`)

### Content ingestion fails

- **Gmail**: Run `aca manage setup-gmail` to (re)authorize OAuth
- **YouTube playlists**: Ensure Google OAuth is configured; use `--public-only` to skip private playlists
- **X/Twitter**: Verify `XAI_API_KEY` is set
- **Perplexity**: Verify `PERPLEXITY_API_KEY` is set

### Settings or prompt API returns 500

The `ADMIN_API_KEY` environment variable must be set. Without it, admin endpoints are blocked by design:

```bash
aca manage generate-secret
# Add the output as ADMIN_API_KEY in .env or .secrets.yaml
```

### Frontend shows CORS errors

Set `ALLOWED_ORIGINS` to your frontend URL:

```bash
# .env
ALLOWED_ORIGINS=http://localhost:5173
```

For production, set it to your actual domain. When `ENVIRONMENT=production` and only localhost origins are configured, the CORS list is deliberately emptied.

### Profile configuration issues

```bash
# Validate your profile
aca profile validate local

# Check if secrets are resolving
aca profile inspect

# Check for missing secrets
aca manage check-profile-secrets
```
