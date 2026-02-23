# Implementation Tasks

## 1. Database Schema Changes

- [x] 1.1 Create Alembic migration for `contents` table:
  - `is_public: Boolean DEFAULT FALSE`
  - `share_token: VARCHAR(36), nullable, unique index`
- [x] 1.2 Create migration for `newsletter_summaries` table (same fields)
- [x] 1.3 Create migration for `digests` table (same fields)
- [x] 1.4 Test migrations and rollback

## 2. Update Models

- [x] 2.1 Add `is_public` and `share_token` to `Content` model
- [x] 2.2 Add fields to `NewsletterSummary` model
- [x] 2.3 Add fields to `Digest` model
- [x] 2.4 Create Pydantic schemas: `ShareRequest`, `ShareResponse`, `ShareStatus`

## 3. Share Management API

- [x] 3.1 Add `POST /api/v1/content/{id}/share` - enable sharing
- [x] 3.2 Add `GET /api/v1/content/{id}/share` - get share status
- [x] 3.3 Add `DELETE /api/v1/content/{id}/share` - disable sharing
- [x] 3.4 Duplicate for `/summaries/{id}/share`
- [x] 3.5 Duplicate for `/digests/{id}/share`

## 4. Public Share Endpoints

- [x] 4.1 Create `src/api/shared_routes.py`
- [x] 4.2 Implement `GET /shared/content/{token}`
- [x] 4.3 Implement `GET /shared/summary/{token}`
- [x] 4.4 Implement `GET /shared/digest/{token}`
- [x] 4.5 Implement `GET /shared/audio/{token}` (redirect to storage URL)
- [x] 4.6 Add content negotiation (HTML vs JSON)

## 5. Shared Content Templates

- [x] 5.1 Create `src/templates/shared/base.html` with OG tags
- [x] 5.2 Create `content.html` template
- [x] 5.3 Create `summary.html` template
- [x] 5.4 Create `digest.html` template with audio player
- [x] 5.5 Add responsive CSS for mobile
- [x] 5.6 Add "Shared via Newsletter Aggregator" attribution

## 6. Rate Limiting

- [x] 6.1 Add rate limiting middleware for `/shared/*`
- [x] 6.2 Configure limits (100/min per IP)
- [x] 6.3 Add `Retry-After` header on 429

## 7. Testing

- [x] 7.1 Unit tests for share token generation
- [x] 7.2 API tests for share management endpoints
- [x] 7.3 Tests for public access (valid token, invalid token, disabled share)
- [x] 7.4 Test HTML and JSON response formats
- [x] 7.5 Test rate limiting

## 8. Documentation

- [x] 8.1 Document sharing feature in user guide
- [x] 8.2 Add API documentation for share endpoints
