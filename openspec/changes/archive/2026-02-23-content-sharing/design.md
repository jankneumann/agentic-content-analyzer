# Design: Content Sharing

## Context

Users want to share content with others who don't have access to the app. We need a simple sharing mechanism that doesn't require recipients to authenticate.

## Goals

1. Enable sharing via unique, unguessable links
2. Support sharing of content, summaries, digests, and audio
3. Provide mobile-friendly viewing experience
4. Include Open Graph tags for social sharing previews

## Non-Goals

1. User accounts for recipients
2. Analytics beyond basic view counts
3. Comments or reactions on shared content
4. Expiring share links (can add later)

## Decisions

### Decision 1: Token-Based Sharing

**What**: Use UUID4 tokens for share links.

**Why**: Unguessable (128-bit), no enumeration attacks, simple implementation.

```python
# Model fields
is_public: bool = False
share_token: str | None = None  # UUID4

# URL structure
/shared/content/550e8400-e29b-41d4-a716-446655440000
```

### Decision 2: Preserve Token on Disable

**What**: When sharing is disabled, keep the token but set `is_public=False`.

**Why**: Allows re-enabling sharing with the same URL.

```python
def disable_sharing(content):
    content.is_public = False
    # Don't clear share_token

def enable_sharing(content):
    if not content.share_token:
        content.share_token = str(uuid4())
    content.is_public = True
```

### Decision 3: Content Negotiation

**What**: Return HTML or JSON based on `Accept` header.

```python
@router.get("/shared/content/{token}")
async def get_shared_content(token: str, request: Request):
    content = get_by_share_token(token)
    if not content or not content.is_public:
        raise HTTPException(404)

    if "text/html" in request.headers.get("accept", ""):
        return templates.TemplateResponse("shared/content.html", {...})
    return content.to_dict()
```

### Decision 4: Open Graph Meta Tags

**What**: Include OG tags for rich social previews.

```html
<meta property="og:title" content="{{ content.title }}">
<meta property="og:description" content="{{ content.excerpt }}">
<meta property="og:type" content="article">
<meta property="og:url" content="{{ share_url }}">
{% if content.audio_url %}
<meta property="og:audio" content="{{ content.audio_url }}">
{% endif %}
```

### Decision 5: Rate Limiting

**What**: Limit requests to public endpoints.

**Why**: Prevent abuse and enumeration attempts.

```python
# Per IP: 100 requests/minute
# Per token: 1000 requests/hour
```

## Database Changes

```sql
-- Add to contents table
ALTER TABLE contents ADD COLUMN is_public BOOLEAN DEFAULT FALSE;
ALTER TABLE contents ADD COLUMN share_token VARCHAR(36);
CREATE UNIQUE INDEX idx_contents_share_token ON contents(share_token) WHERE share_token IS NOT NULL;

-- Same for newsletter_summaries, digests
```

## File Structure

```
src/api/
├── shared_routes.py      # Public /shared/* endpoints
├── content_routes.py     # Add share management endpoints
├── summary_routes.py     # Add share management endpoints
└── digest_routes.py      # Add share management endpoints

src/templates/shared/
├── base.html             # Base template with OG tags
├── content.html          # Article view
├── summary.html          # Summary view
└── digest.html           # Digest with audio player
```

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Token enumeration | UUID4 is 128-bit, rate limiting |
| Bandwidth abuse | Rate limiting per token |
| Stale shared content | Content updates reflect immediately |
