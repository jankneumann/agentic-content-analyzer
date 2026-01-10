# Web UI Specification for AI Newsletter Aggregator

## Overview

This document specifies the requirements and implementation plan for a web-based UI that provides full control over the AI newsletter aggregation pipeline, from ingestion through podcast generation.

---

## Table of Contents

1. [Feature Requirements](#feature-requirements)
2. [Technical Stack](#technical-stack)
3. [Architecture Decisions](#architecture-decisions)
4. [API Design](#api-design)
5. [Component Architecture](#component-architecture)
6. [Implementation Phases](#implementation-phases)
7. [Development Workflow](#development-workflow)
8. [Future Extensions](#future-extensions)

---

## Feature Requirements

### Core Workflow Control

The UI must provide control over all pipeline steps:

| Step | Actions | Artifacts Viewable |
|------|---------|-------------------|
| **Ingestion** | Trigger Gmail/RSS fetch, view status | Raw newsletters, blog articles |
| **Summarization** | Trigger summarization, view progress | Newsletter summaries with key themes |
| **Theme Analysis** | Trigger analysis, explore entities | Themes, entities, relationships (graph + table) |
| **Digest Generation** | Create daily/weekly digests, review/revise | Multi-audience digests with sections |
| **Script Generation** | Generate podcast scripts, review/revise | Structured dialogue scripts |
| **Podcast Generation** | Generate audio, configure voices | Audio player with playback controls |

### Artifact Viewing

- **Newsletters**: Raw HTML/text, metadata, extracted links
- **Summaries**: Executive summary, key themes, strategic insights, technical details
- **Themes**: Interactive graph visualization AND structured table views
- **Digests**: Section-based view (executive, strategic, technical, trends, recommendations)
- **Scripts**: Dialogue view with speaker attribution, section breakdown
- **Podcasts**: Embedded audio player with duration, download option

### AI-Assisted Revision

At each pipeline step, users can:
- Engage in conversation with an AI chatbot to refine content
- Provide section-specific feedback
- View revision history
- Compare versions

**Chatbot Requirements:**
- Flexible model backend (configurable provider)
- Persisted conversation history
- Context-aware (has access to current artifact being revised)
- Web search grounding capability

### Knowledge Graph Features

- **Interactive Graph View**: Visualize entities and relationships using force-directed graph
- **Table View**: Structured list of entities with filters and search
- **Temporal Context**: Show how themes evolve over time
- **Related Concepts**: Surface connections between newsletter topics

---

## Technical Stack

### Frontend

| Technology | Purpose | Rationale |
|------------|---------|-----------|
| **Vite** | Build tool | Fast HMR, native ESM, excellent DX |
| **React 18** | UI framework | Component model, ecosystem, hooks |
| **TypeScript** | Language | Type safety, better IDE support, documentation |
| **shadcn/ui** | Component library | Tailwind-based, accessible, customizable |
| **Tailwind CSS** | Styling | Utility-first, consistent design, responsive |
| **TanStack Query** | Data fetching | Caching, background updates, optimistic UI |
| **TanStack Router** | Routing | Type-safe, file-based routes |
| **Zustand** | State management | Simple, performant, TypeScript-friendly |
| **pnpm** | Package manager | Fast, disk-efficient, strict dependencies |

### Backend (Additions to Existing)

| Technology | Purpose | Rationale |
|------------|---------|-----------|
| **FastAPI** | API framework | Already in use, async support, OpenAPI |
| **SSE (Server-Sent Events)** | Progress updates | Simple, HTTP-based, one-way push |
| **WebSockets** | Chat streaming | Bidirectional for AI conversations |

### Visualization

| Technology | Purpose |
|------------|---------|
| **react-force-graph** | Knowledge graph visualization |
| **recharts** | Charts and analytics |

### Testing

| Technology | Purpose |
|------------|---------|
| **Vitest** | Unit testing |
| **Playwright** | E2E testing, visual regression, screenshot capture |
| **Testing Library** | Component testing |

---

## Architecture Decisions

### Monorepo Structure

All code lives in a single repository:

```
agentic-newsletter-aggregator/
├── src/                    # Existing Python backend
│   ├── api/               # FastAPI routes
│   ├── processors/        # LLM orchestration
│   ├── models/            # SQLAlchemy models
│   └── ...
├── web/                    # NEW: Frontend application
│   ├── src/
│   │   ├── components/    # Reusable UI components
│   │   ├── features/      # Feature-specific modules
│   │   ├── hooks/         # Custom React hooks
│   │   ├── lib/           # Utilities and API client
│   │   ├── pages/         # Route pages
│   │   └── types/         # TypeScript types
│   ├── public/
│   ├── tests/             # Playwright tests
│   ├── package.json
│   ├── vite.config.ts
│   └── tsconfig.json
├── docker-compose.yml      # Updated with frontend service
└── docs/
```

### Port Configuration

| Service | Development | Production (Docker) |
|---------|-------------|---------------------|
| Frontend | `localhost:5173` | nginx on `:3000` |
| Backend API | `localhost:8000` | nginx proxies `/api/*` |
| PostgreSQL | `localhost:5432` | Internal network |
| Neo4j | `localhost:7687` | Internal network |

### Real-time Updates Strategy

**Hybrid Approach:**

1. **SSE (Server-Sent Events)** for task progress:
   - Summarization progress
   - Digest generation status
   - Audio generation progress
   - Simple, HTTP-based, works with existing infrastructure

2. **WebSockets** for AI chatbot:
   - Streaming LLM responses
   - Bidirectional conversation flow
   - Connection state management

### Supabase-Ready Architecture (Phase 4)

Design patterns to enable future Supabase migration:

1. **Repository Pattern**: Abstract database access behind interfaces
   ```typescript
   // Abstract interface
   interface NewsletterRepository {
     findAll(filters: NewsletterFilters): Promise<Newsletter[]>
     findById(id: string): Promise<Newsletter | null>
     create(data: CreateNewsletterDTO): Promise<Newsletter>
   }

   // FastAPI implementation (now)
   class FastAPINewsletterRepository implements NewsletterRepository { }

   // Supabase implementation (future)
   class SupabaseNewsletterRepository implements NewsletterRepository { }
   ```

2. **Auth Abstraction**: Prepare for Supabase Auth with Microsoft Entra ID
   ```typescript
   interface AuthProvider {
     getCurrentUser(): Promise<User | null>
     signIn(provider: 'microsoft'): Promise<void>
     signOut(): Promise<void>
   }
   ```

3. **Real-time Abstraction**: Wrap subscription logic
   ```typescript
   interface RealtimeProvider {
     subscribe<T>(channel: string, callback: (data: T) => void): Unsubscribe
   }
   ```

4. **File Storage Abstraction**: For podcast audio files
   ```typescript
   interface StorageProvider {
     upload(path: string, file: File): Promise<string>
     getUrl(path: string): string
   }
   ```

### Authentication Strategy

**Phase 1-3 (Single User):**
- No authentication required
- All endpoints publicly accessible on local network
- Session storage for UI preferences

**Phase 4 (Multi-User with Entra ID):**
- Supabase Auth with Microsoft Entra ID SAML/OIDC provider
- Row-Level Security (RLS) for data isolation
- JWT tokens for API authentication

---

## API Design

### New Endpoints Required

All endpoints prefixed with `/api/v1/`

#### Newsletters

```
GET    /newsletters                    # List with filters (status, date range, source)
GET    /newsletters/:id                # Get newsletter with full content
POST   /newsletters/ingest             # Trigger ingestion (gmail/rss)
GET    /newsletters/:id/summary        # Get associated summary
```

#### Summaries

```
GET    /summaries                      # List summaries with filters
GET    /summaries/:id                  # Get summary details
POST   /summaries/generate             # Trigger summarization for newsletter(s)
GET    /summaries/:id/status           # Get generation status (SSE endpoint)
```

#### Themes

```
GET    /themes                         # List theme analyses
GET    /themes/:id                     # Get theme analysis details
GET    /themes/:id/graph               # Get graph data (nodes + edges)
POST   /themes/analyze                 # Trigger theme analysis
GET    /themes/entities                # List all entities
GET    /themes/relationships           # List all relationships
```

#### Digests

```
GET    /digests                        # List digests with filters
GET    /digests/:id                    # Get digest with sections
POST   /digests/generate               # Generate new digest
POST   /digests/:id/review             # Submit review (approve/reject/revise)
POST   /digests/:id/sections/:idx/revise  # Revise specific section
GET    /digests/:id/history            # Get revision history
GET    /digests/:id/status             # Generation status (SSE endpoint)
```

#### Scripts (Existing, extended)

```
GET    /scripts                        # List scripts
GET    /scripts/:id                    # Get script with dialogue
POST   /scripts/generate               # Generate from digest
POST   /scripts/:id/review             # Submit review
POST   /scripts/:id/sections/:idx/revise  # Revise section
GET    /scripts/:id/status             # Generation status (SSE endpoint)
```

#### Podcasts

```
GET    /podcasts                       # List podcasts
GET    /podcasts/:id                   # Get podcast metadata
POST   /podcasts/generate              # Generate audio from script
GET    /podcasts/:id/audio             # Stream audio file
GET    /podcasts/:id/status            # Generation status (SSE endpoint)
```

#### Chat (AI Revision Assistant)

```
POST   /chat/conversations             # Create new conversation
GET    /chat/conversations/:id         # Get conversation history
POST   /chat/conversations/:id/messages  # Send message (WebSocket upgrade available)
DELETE /chat/conversations/:id         # Delete conversation
```

#### System

```
GET    /system/health                  # Health check
GET    /system/config                  # Get UI configuration
GET    /system/models                  # List available LLM models
```

### SSE Event Format

```typescript
interface ProgressEvent {
  type: 'progress' | 'complete' | 'error'
  taskId: string
  step: string
  progress: number  // 0-100
  message: string
  data?: any
}
```

---

## Component Architecture

### Page Structure

```
/                           → Dashboard (overview, recent activity)
/newsletters                → Newsletter list with filters
/newsletters/:id            → Newsletter detail view
/summaries                  → Summary list
/summaries/:id              → Summary detail with revision chat
/themes                     → Theme analysis list
/themes/:id                 → Theme detail (graph + table views)
/digests                    → Digest list with status filters
/digests/:id                → Digest detail with section editor
/digests/:id/review         → Digest review workflow
/scripts                    → Script list
/scripts/:id                → Script detail with dialogue view
/scripts/:id/review         → Script review workflow
/podcasts                   → Podcast list
/podcasts/:id               → Podcast player page
/settings                   → Configuration (models, voices, etc.)
```

### Core Components

```
components/
├── ui/                     # shadcn/ui primitives
│   ├── button.tsx
│   ├── card.tsx
│   ├── dialog.tsx
│   └── ...
├── layout/
│   ├── AppShell.tsx        # Main layout with sidebar
│   ├── Sidebar.tsx         # Navigation sidebar
│   ├── Header.tsx          # Top header with actions
│   └── PageContainer.tsx   # Consistent page wrapper
├── data-display/
│   ├── DataTable.tsx       # Generic data table with sorting/filtering
│   ├── StatusBadge.tsx     # Status indicator badges
│   ├── Timeline.tsx        # Activity timeline
│   └── MetadataPanel.tsx   # Display metadata key-value pairs
├── workflow/
│   ├── PipelineProgress.tsx    # Multi-step progress indicator
│   ├── TaskCard.tsx            # Individual task status card
│   └── ActionButton.tsx        # Trigger workflow actions
├── content/
│   ├── MarkdownRenderer.tsx    # Render markdown content
│   ├── SectionEditor.tsx       # Edit digest/script sections
│   ├── DialogueView.tsx        # Display podcast dialogue
│   └── SourceCitation.tsx      # Show source references
├── graph/
│   ├── KnowledgeGraph.tsx      # Interactive force-directed graph
│   ├── EntityNode.tsx          # Graph node component
│   └── RelationshipEdge.tsx    # Graph edge component
├── chat/
│   ├── ChatPanel.tsx           # Slide-out chat panel
│   ├── ChatMessage.tsx         # Individual message bubble
│   ├── ChatInput.tsx           # Message input with send
│   └── StreamingMessage.tsx    # Streaming response display
└── media/
    ├── AudioPlayer.tsx         # Podcast audio player
    ├── VideoEmbed.tsx          # YouTube embed (future)
    └── WaveformVisualizer.tsx  # Audio waveform (future)
```

### Feature Modules

```
features/
├── newsletters/
│   ├── NewsletterList.tsx
│   ├── NewsletterDetail.tsx
│   ├── NewsletterFilters.tsx
│   ├── IngestButton.tsx
│   └── hooks/
│       └── useNewsletters.ts
├── summaries/
│   ├── SummaryList.tsx
│   ├── SummaryDetail.tsx
│   ├── SummarizeButton.tsx
│   └── hooks/
│       └── useSummaries.ts
├── themes/
│   ├── ThemeList.tsx
│   ├── ThemeDetail.tsx
│   ├── ThemeGraph.tsx
│   ├── ThemeTable.tsx
│   └── hooks/
│       └── useThemes.ts
├── digests/
│   ├── DigestList.tsx
│   ├── DigestDetail.tsx
│   ├── DigestReview.tsx
│   ├── SectionReviser.tsx
│   └── hooks/
│       └── useDigests.ts
├── scripts/
│   ├── ScriptList.tsx
│   ├── ScriptDetail.tsx
│   ├── ScriptReview.tsx
│   ├── DialogueEditor.tsx
│   └── hooks/
│       └── useScripts.ts
├── podcasts/
│   ├── PodcastList.tsx
│   ├── PodcastPlayer.tsx
│   ├── GenerateAudioButton.tsx
│   └── hooks/
│       └── usePodcasts.ts
└── chat/
    ├── RevisionChat.tsx
    ├── ChatProvider.tsx
    └── hooks/
        ├── useChat.ts
        └── useConversation.ts
```

---

## Implementation Phases

### Phase 1: Core Foundation (MVP)

**Goal:** Working UI with basic navigation and newsletter/summary viewing

#### 1.1 Project Setup
- [ ] Initialize Vite + React + TypeScript project in `/web`
- [ ] Configure pnpm workspace
- [ ] Set up Tailwind CSS
- [ ] Install and configure shadcn/ui
- [ ] Configure ESLint + Prettier
- [ ] Set up path aliases (@/ for src/)
- [ ] Create base TypeScript types from backend models

**Commit:** `feat(web): initialize frontend project with Vite, React, TypeScript, and shadcn/ui`

#### 1.2 Layout and Navigation
- [ ] Create AppShell layout component
- [ ] Implement responsive Sidebar with navigation
- [ ] Create Header with breadcrumbs
- [ ] Set up TanStack Router with file-based routes
- [ ] Implement PageContainer for consistent page layout

**Commit:** `feat(web): add layout components and navigation structure`

#### 1.3 API Client Setup
- [ ] Create typed API client using fetch
- [ ] Set up TanStack Query provider
- [ ] Configure Vite proxy for development
- [ ] Create base hooks for API calls
- [ ] Implement error handling utilities

**Commit:** `feat(web): configure API client with TanStack Query`

#### 1.4 Backend API - Newsletters
- [ ] Create `/api/v1/newsletters` router
- [ ] Implement list endpoint with filters
- [ ] Implement detail endpoint
- [ ] Implement ingestion trigger endpoint
- [ ] Add OpenAPI documentation

**Commit:** `feat(api): add newsletter endpoints`

#### 1.5 Newsletter Feature
- [ ] Create NewsletterList page with DataTable
- [ ] Implement filters (status, source, date range)
- [ ] Create NewsletterDetail page
- [ ] Add raw content viewer (HTML/text toggle)
- [ ] Implement IngestButton with loading state

**Commit:** `feat(web): implement newsletter list and detail views`

#### 1.6 Backend API - Summaries
- [ ] Create `/api/v1/summaries` router
- [ ] Implement list/detail endpoints
- [ ] Implement summarization trigger endpoint
- [ ] Add SSE endpoint for progress

**Commit:** `feat(api): add summary endpoints with SSE progress`

#### 1.7 Summary Feature
- [ ] Create SummaryList page
- [ ] Create SummaryDetail page with sections
- [ ] Implement SummarizeButton with progress indicator
- [ ] Connect to SSE for real-time updates

**Commit:** `feat(web): implement summary views with real-time progress`

#### 1.8 Dashboard
- [ ] Create Dashboard page
- [ ] Add recent activity timeline
- [ ] Show pipeline status overview
- [ ] Add quick action buttons
- [ ] Display key metrics (counts, processing stats)

**Commit:** `feat(web): implement dashboard with activity overview`

#### 1.9 Docker Integration
- [ ] Create Dockerfile for frontend
- [ ] Add nginx configuration
- [ ] Update docker-compose.yml
- [ ] Configure production build

**Commit:** `feat(docker): add frontend container with nginx`

#### 1.10 Playwright Setup
- [ ] Install and configure Playwright
- [ ] Create first visual test for Dashboard
- [ ] Set up screenshot comparison
- [ ] Add to CI workflow (GitHub Actions)

**Commit:** `test(e2e): configure Playwright with visual regression tests`

---

### Phase 2: Full Pipeline UI

**Goal:** Complete UI for all pipeline steps with basic review workflows

#### 2.1 Backend API - Themes
- [ ] Create `/api/v1/themes` router
- [ ] Implement list/detail endpoints
- [ ] Add graph data endpoint (nodes + edges format)
- [ ] Implement analysis trigger endpoint

**Commit:** `feat(api): add theme analysis endpoints`

#### 2.2 Theme Feature - Table View
- [ ] Create ThemeList page
- [ ] Create ThemeDetail page
- [ ] Implement ThemeTable with entity listing
- [ ] Add filters by category, trend, date

**Commit:** `feat(web): implement theme analysis table views`

#### 2.3 Theme Feature - Graph View
- [ ] Install react-force-graph
- [ ] Create KnowledgeGraph component
- [ ] Implement EntityNode with tooltips
- [ ] Add zoom/pan controls
- [ ] Implement node click to show details

**Commit:** `feat(web): add interactive knowledge graph visualization`

#### 2.4 Backend API - Digests
- [ ] Create `/api/v1/digests` router
- [ ] Implement CRUD endpoints
- [ ] Add review workflow endpoints
- [ ] Add section revision endpoint
- [ ] Add SSE for generation progress

**Commit:** `feat(api): add digest endpoints with review workflow`

#### 2.5 Digest Feature
- [ ] Create DigestList page with status filters
- [ ] Create DigestDetail page with section view
- [ ] Implement section-based content display
- [ ] Add metadata panel (model, tokens, timing)

**Commit:** `feat(web): implement digest list and detail views`

#### 2.6 Digest Review Workflow
- [ ] Create DigestReview page
- [ ] Implement approve/reject buttons
- [ ] Add section feedback form
- [ ] Show revision history
- [ ] Implement revision comparison view

**Commit:** `feat(web): add digest review and revision workflow`

#### 2.7 Script Feature
- [ ] Extend existing script API if needed
- [ ] Create ScriptList page
- [ ] Create ScriptDetail with DialogueView
- [ ] Implement speaker-attributed dialogue display
- [ ] Add script metadata panel

**Commit:** `feat(web): implement script list and detail views`

#### 2.8 Script Review Workflow
- [ ] Create ScriptReview page
- [ ] Implement section-by-section review
- [ ] Add dialogue editing capability
- [ ] Show revision history

**Commit:** `feat(web): add script review workflow`

#### 2.9 Backend API - Podcasts
- [ ] Create `/api/v1/podcasts` router
- [ ] Implement list/detail endpoints
- [ ] Add audio generation trigger
- [ ] Add audio streaming endpoint
- [ ] Add SSE for generation progress

**Commit:** `feat(api): add podcast endpoints with audio streaming`

#### 2.10 Podcast Feature
- [ ] Create PodcastList page
- [ ] Create AudioPlayer component
- [ ] Implement playback controls (play/pause, seek, volume)
- [ ] Add download button
- [ ] Show generation progress

**Commit:** `feat(web): implement podcast player and list views`

#### 2.11 Playwright Tests - Phase 2
- [ ] Add tests for theme graph interaction
- [ ] Add tests for digest review workflow
- [ ] Add tests for script review workflow
- [ ] Add tests for audio player
- [ ] Update CI with new test suites

**Commit:** `test(e2e): add Playwright tests for Phase 2 features`

---

### Phase 3: Advanced Features

**Goal:** AI chatbot for revisions, enhanced UX, comprehensive testing

#### 3.1 Backend - Chat Infrastructure
- [ ] Create conversation model in database
- [ ] Create `/api/v1/chat` router
- [ ] Implement conversation CRUD
- [ ] Add WebSocket endpoint for streaming
- [ ] Implement context injection (current artifact)
- [ ] Add web search grounding capability

**Commit:** `feat(api): add chat infrastructure with WebSocket streaming`

#### 3.2 Chat UI Components
- [ ] Create ChatPanel slide-out component
- [ ] Implement ChatMessage with markdown support
- [ ] Create ChatInput with send button
- [ ] Add StreamingMessage for live responses
- [ ] Implement typing indicators

**Commit:** `feat(web): implement chat UI components`

#### 3.3 Revision Chat Integration
- [ ] Create RevisionChat component
- [ ] Integrate with SummaryDetail
- [ ] Integrate with DigestReview
- [ ] Integrate with ScriptReview
- [ ] Persist conversations per artifact

**Commit:** `feat(web): integrate AI revision chat across pipeline`

#### 3.4 Chat Features Enhancement
- [ ] Add model selection in chat
- [ ] Implement conversation history sidebar
- [ ] Add "apply suggestion" button
- [ ] Show source citations in responses
- [ ] Add conversation export

**Commit:** `feat(web): enhance chat with model selection and history`

#### 3.5 Real-time Progress Enhancement
- [ ] Create unified ProgressProvider
- [ ] Implement toast notifications for completions
- [ ] Add background task queue visualization
- [ ] Show estimated time remaining

**Commit:** `feat(web): enhance real-time progress with notifications`

#### 3.6 Settings Page
- [ ] Create Settings page
- [ ] Add model configuration section
- [ ] Add voice configuration for podcasts
- [ ] Add theme/appearance settings
- [ ] Implement settings persistence

**Commit:** `feat(web): implement settings page`

#### 3.7 Search and Filtering
- [ ] Add global search component
- [ ] Implement full-text search API
- [ ] Add advanced filters UI
- [ ] Implement saved filter presets

**Commit:** `feat(web): add global search and advanced filtering`

#### 3.8 Keyboard Shortcuts
- [ ] Implement keyboard navigation
- [ ] Add shortcut hints in UI
- [ ] Create keyboard shortcut help modal

**Commit:** `feat(web): add keyboard shortcuts for power users`

#### 3.9 Comprehensive Playwright Tests
- [ ] Add chat interaction tests
- [ ] Add full workflow E2E tests
- [ ] Add accessibility tests
- [ ] Add performance benchmarks
- [ ] Generate test coverage report

**Commit:** `test(e2e): comprehensive Playwright test suite`

#### 3.10 Documentation
- [ ] Create component documentation
- [ ] Add inline code comments (TypeScript-focused)
- [ ] Document API client usage
- [ ] Create developer setup guide

**Commit:** `docs: add frontend documentation and code comments`

---

### Phase 4: Cloud-Ready & Extensions

**Goal:** Prepare for Supabase migration, add authentication, optimize for cloud

#### 4.1 Repository Pattern Implementation
- [ ] Create abstract repository interfaces
- [ ] Refactor API client to use repositories
- [ ] Create FastAPI repository implementations
- [ ] Add repository provider context

**Commit:** `refactor(web): implement repository pattern for data access`

#### 4.2 Auth Abstraction
- [ ] Create AuthProvider interface
- [ ] Implement mock auth for development
- [ ] Add auth context and hooks
- [ ] Create protected route wrapper

**Commit:** `feat(web): add authentication abstraction layer`

#### 4.3 Supabase Integration (Optional)
- [ ] Add Supabase client dependency
- [ ] Create Supabase repository implementations
- [ ] Create Supabase auth provider
- [ ] Add environment-based provider switching

**Commit:** `feat(web): add Supabase provider implementations`

#### 4.4 Real-time Abstraction
- [ ] Create RealtimeProvider interface
- [ ] Implement SSE provider (current)
- [ ] Prepare Supabase realtime provider
- [ ] Add provider switching logic

**Commit:** `refactor(web): abstract real-time subscriptions`

#### 4.5 File Storage Abstraction
- [ ] Create StorageProvider interface
- [ ] Implement local/API storage provider
- [ ] Prepare Supabase storage provider
- [ ] Update podcast audio handling

**Commit:** `feat(web): add storage provider abstraction`

#### 4.6 Performance Optimization
- [ ] Implement code splitting
- [ ] Add lazy loading for routes
- [ ] Optimize bundle size
- [ ] Add service worker for caching
- [ ] Implement virtual scrolling for large lists

**Commit:** `perf(web): optimize bundle size and add code splitting`

#### 4.7 Mobile Responsiveness
- [ ] Audit responsive breakpoints
- [ ] Optimize touch interactions
- [ ] Add mobile navigation (hamburger menu)
- [ ] Test on various screen sizes

**Commit:** `feat(web): enhance mobile responsiveness`

#### 4.8 Cloud Deployment Configuration
- [ ] Create Vercel configuration
- [ ] Document Supabase setup
- [ ] Create deployment guide
- [ ] Add environment variable documentation

**Commit:** `docs: add cloud deployment documentation`

---

## Development Workflow

### Git Branch Strategy

- **Main branch:** `main` (protected)
- **Feature branch:** `claude/newsletter-aggregator-ui-gn90w`
- **Commit per feature:** Each checkbox item = one commit

### Commit Message Format

```
<type>(<scope>): <description>

Types: feat, fix, refactor, test, docs, perf, chore
Scopes: web, api, docker, e2e
```

### Development Commands

```bash
# Frontend development
cd web
pnpm install
pnpm dev              # Start Vite dev server (port 5173)
pnpm build            # Production build
pnpm test             # Run Vitest
pnpm test:e2e         # Run Playwright tests
pnpm lint             # ESLint check
pnpm typecheck        # TypeScript check

# Backend (existing)
source .venv/bin/activate
uvicorn src.api.app:app --reload  # Start FastAPI (port 8000)

# Full stack (Docker)
docker compose up -d              # Start all services
docker compose logs -f web        # Watch frontend logs
```

### Visual Validation Process

1. Implement feature
2. Run Playwright tests locally: `pnpm test:e2e`
3. Review generated screenshots in `tests/screenshots/`
4. Commit with feature
5. CI runs tests and compares screenshots

---

## Future Extensions

### YouTube Integration (Post-Phase 4)
- Embedded video player for referenced content
- Transcript ingestion with timestamps
- Quote extraction with video timestamp links

### AG-UI Protocol Integration (Post-Phase 4)
- Standardized agentic UI events
- Enhanced chat experience with tool visibility
- Real-time agent state display (thinking, tool calls)

### Multi-User with Microsoft Entra ID
- Supabase Auth with Entra ID SAML/OIDC
- Row-Level Security for data isolation
- Team workspaces
- Audit logging

### Advanced Analytics
- Usage metrics dashboard
- Cost tracking per pipeline step
- Quality metrics over time
- A/B testing for different models

---

## Appendix: TypeScript Type Definitions

Core types to be generated from backend models:

```typescript
// Newsletter types
interface Newsletter {
  id: string
  source: 'gmail' | 'rss'
  sourceId: string
  title: string
  sender: string
  publication: string | null
  publishedDate: string
  rawHtml: string | null
  rawText: string | null
  extractedLinks: Record<string, string>[]
  contentHash: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  ingestedAt: string
  processedAt: string | null
  errorMessage: string | null
}

// Summary types
interface NewsletterSummary {
  id: string
  newsletterId: string
  executiveSummary: string
  keyThemes: string[]
  strategicInsights: string[]
  technicalDetails: string[]
  actionableItems: string[]
  notableQuotes: string[]
  relevantLinks: string[]
  agentFramework: string
  modelUsed: string
  createdAt: string
  tokenUsage: number
  processingTimeSeconds: number
}

// Theme types
interface ThemeAnalysis {
  id: string
  analysisDate: string
  startDate: string
  endDate: string
  newsletterCount: number
  themes: Theme[]
  totalThemes: number
  emergingThemesCount: number
  topTheme: string
}

interface Theme {
  name: string
  category: ThemeCategory
  trend: ThemeTrend
  confidence: number
  mentions: number
  sources: string[]
  summary: string
  relatedEntities: Entity[]
}

type ThemeCategory =
  | 'ml_ai' | 'devops_infra' | 'data_engineering'
  | 'business_strategy' | 'tools_products'
  | 'research_academia' | 'security' | 'other'

type ThemeTrend =
  | 'emerging' | 'growing' | 'established' | 'declining' | 'one_off'

// Digest types
interface Digest {
  id: string
  digestType: 'daily' | 'weekly' | 'sub_digest'
  periodStart: string
  periodEnd: string
  title: string
  executiveOverview: string
  strategicInsights: DigestSection[]
  technicalDevelopments: DigestSection[]
  emergingTrends: DigestSection[]
  actionableRecommendations: Record<string, string[]>
  sources: Source[]
  status: DigestStatus
  reviewedBy: string | null
  revisionCount: number
  createdAt: string
}

type DigestStatus =
  | 'pending' | 'generating' | 'completed' | 'failed'
  | 'pending_review' | 'approved' | 'rejected' | 'delivered'

// Script types
interface PodcastScript {
  id: string
  digestId: string
  title: string
  length: 'brief' | 'standard' | 'extended'
  wordCount: number
  estimatedDurationSeconds: number
  sections: PodcastSection[]
  intro: DialogueTurn[]
  outro: DialogueTurn[]
  status: ScriptStatus
  revisionCount: number
}

interface PodcastSection {
  sectionType: 'intro' | 'strategic' | 'technical' | 'trend' | 'outro'
  title: string
  dialogue: DialogueTurn[]
  sourcesCited: string[]
}

interface DialogueTurn {
  speaker: 'alex' | 'sam'
  text: string
  emphasis: 'excited' | 'thoughtful' | 'concerned' | 'amused' | null
  pauseAfter: number | null
}

// Podcast types
interface Podcast {
  id: string
  scriptId: string
  audioUrl: string
  audioFormat: string
  durationSeconds: number
  fileSizeBytes: number
  voiceProvider: string
  status: 'generating' | 'completed' | 'failed'
  createdAt: string
}

// Chat types
interface Conversation {
  id: string
  artifactType: 'summary' | 'digest' | 'script'
  artifactId: string
  messages: ChatMessage[]
  createdAt: string
  updatedAt: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: string
  metadata?: {
    model?: string
    tokenUsage?: number
    webSearchUsed?: boolean
  }
}
```

---

*Document Version: 1.0*
*Last Updated: 2025-01-04*
*Status: Ready for Implementation*
