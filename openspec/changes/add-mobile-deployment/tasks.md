# Implementation Tasks

> **Status**: 53/59 tasks complete. Remaining: Migration testing and pg_cron runtime setup (requires Neon database access).

## 1. DatabaseProvider Queue Abstraction

- [x] 1.1 Add `get_queue_url()` method to DatabaseProvider protocol
- [x] 1.2 Add `get_queue_options()` method for worker engine config
- [x] 1.3 Add `supports_pg_cron()` method to indicate pg_cron availability
- [x] 1.4 Implement queue methods in LocalProvider
- [x] 1.5 Implement queue methods in SupabaseProvider
- [x] 1.6 Implement queue methods in NeonProvider

## 2. PGQueuer Setup

- [x] 2.1 Create `src/queue/setup.py` module
- [x] 2.2 Configure PGQueuer with DatabaseProvider integration
- [x] 2.3 Add graceful fallback to FastAPI BackgroundTasks
- [x] 2.4 Create queue initialization function

## 3. Content Extraction Tasks

- [x] 3.1 Create `src/tasks/content.py` with task definitions
- [x] 3.2 Implement `extract_url_content` task
- [x] 3.3 Add error handling and retry logic
- [x] 3.4 Integrate with existing Content model

## 4. Worker Process

- [x] 4.1 Create `src/worker.py` entry point
- [x] 4.2 Configure worker to use direct database connection
- [x] 4.3 Add graceful shutdown handling
- [x] 4.4 Add logging for job processing

## 5. URL Content Extractor

- [x] 5.1 Create `src/services/url_extractor.py`
- [x] 5.2 Integrate trafilatura for HTML-to-markdown conversion
- [x] 5.3 Add timeout handling (30s max per URL)
- [x] 5.4 Handle common errors (404, timeout, blocked)
- [x] 5.5 Extract metadata (title, author, date)

## 6. Save URL API Endpoints

- [x] 6.1 Create `src/api/save_routes.py`
- [x] 6.2 Implement `POST /api/v1/content/save-url` endpoint
- [x] 6.3 Add URL validation
- [x] 6.4 Add duplicate detection by source_url
- [x] 6.5 Implement `GET /api/v1/content/{id}/status` endpoint
- [x] 6.6 Configure CORS for mobile clients

## 7. Mobile Save Template

- [x] 7.1 Create `GET /save` endpoint
- [x] 7.2 Create `src/templates/save.html` mobile-optimized template
- [x] 7.3 Pre-fill form from URL query parameters
- [x] 7.4 Add JavaScript for async form submission
- [x] 7.5 Show success/error states

## 8. Railway Deployment Config

- [x] 8.1 Update Dockerfile for Railway compatibility
- [x] 8.2 Create `railway.toml` configuration
- [x] 8.3 Configure web service (API)
- [x] 8.4 Configure worker service
- [x] 8.5 Set up environment variables

## 9. iOS Shortcuts Documentation

- [x] 9.1 Create `shortcuts/README.md`
- [x] 9.2 Document Shortcut installation steps
- [x] 9.3 Document Shortcut configuration (API URL)
- [x] 9.4 Add troubleshooting section

## 10. Database Migration

- [x] 10.1 Create Alembic migration for PGQueuer tables
- [x] 10.2 Add `pgqueuer_jobs` table schema
- [x] 10.3 Add indexes for job status and entrypoint
- [ ] 10.4 Test migration on local PostgreSQL
- [ ] 10.5 Test migration on Neon

## 11. pg_cron Scheduled Jobs

- [ ] 11.1 Enable pg_cron extension on Neon (`CREATE EXTENSION IF NOT EXISTS pg_cron`)
- [x] 11.2 Create `pgqueuer_enqueue` helper function (in migration)
- [ ] 11.3 Schedule daily newsletter scan job (6 AM UTC)
- [x] 11.4 Document scheduled job management (docs/PG_CRON_SETUP.md)
- [ ] 11.5 Add job monitoring/logging

## 12. Testing

- [x] 12.1 Manual testing of save URL endpoint
- [x] 12.2 Manual testing of iOS Shortcuts flow
- [x] 12.3 Test content extraction with various URLs
- [x] 12.4 Add unit tests for url_extractor.py
- [x] 12.5 Add integration tests for save_routes.py
- [ ] 12.6 Test pg_cron job execution
