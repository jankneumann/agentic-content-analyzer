# Add Sync session button to the Chrome extension

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `add-sync-session-button-to-the-chrome-extension`
> Effort: S
> Priority: 7

## Summary

Add a Sync session action to the extension that reads the substack.sid, auth_token, and ct0 cookies via the cookies permission with host permissions for substack.com and x.com, and posts them over the tailnet to the session sync endpoint.

## Dependencies

- `ri-14`

## Acceptance Outcomes

- The extension manifest declares cookies and host permissions for substack.com and x.com only.
- Clicking Sync session posts the three cookies to the endpoint with the admin key header and shows success or the endpoint error without displaying cookie values.
- The extension README documents the tailnet API URL and the sync action.

## Rationale

Completes the laptop-side manual refresh path so an expiry alert can be resolved without opening DevTools.
