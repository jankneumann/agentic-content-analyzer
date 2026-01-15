# Implementation Tasks

## 1. Database Schema Changes

- [ ] 1.1 Create Alembic migration for `contents` table:
  - `is_public: Boolean DEFAULT FALSE`
  - `share_token: VARCHAR(36), nullable, unique index`
- [ ] 1.2 Create migration for `newsletter_summaries` table (same fields)
- [ ] 1.3 Create migration for `digests` table (same fields)
- [ ] 1.4 Test migrations and rollback

## 2. Update Models

- [ ] 2.1 Add `is_public` and `share_token` to `Content` model
- [ ] 2.2 Add fields to `NewsletterSummary` model
- [ ] 2.3 Add fields to `Digest` model
- [ ] 2.4 Create Pydantic schemas: `ShareRequest`, `ShareResponse`, `ShareStatus`

## 3. Share Management API

- [ ] 3.1 Add `POST /api/v1/content/{id}/share` - enable sharing
- [ ] 3.2 Add `GET /api/v1/content/{id}/share` - get share status
- [ ] 3.3 Add `DELETE /api/v1/content/{id}/share` - disable sharing
- [ ] 3.4 Duplicate for `/summaries/{id}/share`
- [ ] 3.5 Duplicate for `/digests/{id}/share`

## 4. Public Share Endpoints

- [ ] 4.1 Create `src/api/shared_routes.py`
- [ ] 4.2 Implement `GET /shared/content/{token}`
- [ ] 4.3 Implement `GET /shared/summary/{token}`
- [ ] 4.4 Implement `GET /shared/digest/{token}`
- [ ] 4.5 Implement `GET /shared/audio/{token}` (redirect to storage URL)
- [ ] 4.6 Add content negotiation (HTML vs JSON)

## 5. Shared Content Templates

- [ ] 5.1 Create `src/templates/shared/base.html` with OG tags
- [ ] 5.2 Create `content.html` template
- [ ] 5.3 Create `summary.html` template
- [ ] 5.4 Create `digest.html` template with audio player
- [ ] 5.5 Add responsive CSS for mobile
- [ ] 5.6 Add "Shared via Newsletter Aggregator" attribution

## 6. Rate Limiting

- [ ] 6.1 Add rate limiting middleware for `/shared/*`
- [ ] 6.2 Configure limits (100/min per IP)
- [ ] 6.3 Add `Retry-After` header on 429

## 7. Testing

- [ ] 7.1 Unit tests for share token generation
- [ ] 7.2 API tests for share management endpoints
- [ ] 7.3 Tests for public access (valid token, invalid token, disabled share)
- [ ] 7.4 Test HTML and JSON response formats
- [ ] 7.5 Test rate limiting

## 8. Documentation

- [ ] 8.1 Document sharing feature in user guide
- [ ] 8.2 Add API documentation for share endpoints
