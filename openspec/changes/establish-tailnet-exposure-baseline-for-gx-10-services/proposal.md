# Establish tailnet exposure baseline for gx-10 services

> Parent roadmap: `x-bookmarks-session-capture`
> Change ID: `establish-tailnet-exposure-baseline-for-gx-10-services`
> Effort: M
> Priority: 3

## Summary

Bind OpenBao and the API on gx-10 to the Tailscale interface only, give the API a trusted certificate on its MagicDNS name, and record the bind addresses, ACL sketch, and BAO_ADDR in docs/TAILNET.md linked from CLAUDE.md and docs/SETUP.md.

## Dependencies

- None

## Acceptance Outcomes

- docs/TAILNET.md exists, is linked from CLAUDE.md and docs/SETUP.md, and documents bind addresses, the Tailscale ACL sketch, the tailscale serve or cert recipe, and the workstation BAO_ADDR value.
- The documented compose or systemd configuration binds OpenBao and the API to the Tailscale address and the documented listener check shows no 0.0.0.0 listener for port 8200 or the API port.
- The API answers over HTTPS on its MagicDNS hostname with a certificate Chrome trusts without a manual exception.
- The Chrome extension README states the tailnet API URL and the matching host permission note.

## Rationale

Every unattended credential write in later items (capture CLI, adapter write-back, extension sync) assumes the workstation and worker reach OpenBao and the API privately over the tailnet with no public port exposure.
