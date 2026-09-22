# Expand linked articles from bookmarked posts

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `expand-linked-articles-from-bookmarked-posts`
> Effort: S
> Priority: 4

## Summary

When expand_links is enabled, submit one UrlIngestCommand per expanded outbound URL in a bookmarked post through OperationService while the post row remains the receipt, skipping media-only and self-referential X URLs and keeping the content_reference recorded either way.

## Dependencies

- `ri-12`

## Acceptance Outcomes

- With expand_links true, a fixture bookmark carrying one external link produces exactly one submitted url operation and a content_reference from the post to the article.
- With expand_links false, no url operation is submitted and the reference is still recorded.
- Media-only and self-referential x.com URLs never produce a url operation.

## Rationale

Bookmarks are usually receipts for an article; summarizing the linked article as its own row is what makes the bookmark gesture a useful capture path.
