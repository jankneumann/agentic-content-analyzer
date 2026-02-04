# Proposal: Add Profile-Based Make Targets and Opik Integration

## Change ID
`add-profile-make-targets`

## Summary
Add make targets that allow developers to easily switch between different configuration profiles and integrate Opik self-hosted observability into the local development stack for E2E LLM tracing.

## Why
Currently, switching between profiles requires manually setting `PROFILE=<name>` environment variables before running commands. This is error-prone and doesn't provide a streamlined developer experience for common workflows like:

1. **Local development without observability** - The default `make dev` workflow
2. **Local development with LLM tracing** - Requires starting Opik stack + setting profile
3. **Verifying profile configurations work E2E** - No automated validation

Additionally, the existing `docker-compose.opik.yml` has a port conflict:
- Opik frontend uses port 5173 (same as Vite dev server)
- Developers cannot run both simultaneously for E2E testing

## What
1. **New Make Targets**: Add profile-aware make targets (`dev-local`, `dev-opik`, `opik-up`, `opik-down`, `verify-profile`)
2. **New Profile**: Create `local-opik.yaml` that extends `local` with Opik observability enabled
3. **Port Fix**: Change Opik frontend from port 5173 to 5174 to avoid Vite conflict
4. **E2E Verification**: Add `verify-profile` and `verify-opik` targets to validate configuration works end-to-end

## Success Criteria
- [ ] `make opik-up` starts the Opik stack and waits for it to be healthy
- [ ] `make dev-opik` starts the API with Opik tracing enabled (fails if Opik not running)
- [ ] Opik UI accessible at http://localhost:5174 (no conflict with Vite on 5173)
- [ ] `make verify-opik` sends a test trace and confirms it appears in Opik
- [ ] Documentation updated with profile-based development workflow

## Out of Scope
- Cloud Opik (Comet) integration (already supported via API key)
- Profile switching at runtime (requires app restart)
- UI for profile selection (use make targets or CLI)
