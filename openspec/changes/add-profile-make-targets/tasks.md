# Tasks: Add Profile-Based Make Targets and Opik Integration

## Phase 1: Fix Port Conflict
> Fix the Opik frontend port to avoid conflict with Vite dev server

- [x] Update `docker-compose.opik.yml` to expose Opik frontend on port 5174 instead of 5173
- [x] Update header comments in `docker-compose.opik.yml` to reflect new port
- [x] Test Opik stack starts and UI is accessible at http://localhost:5174

## Phase 2: Create local-opik Profile
> Create a profile that enables Opik observability for local development

- [x] Create `profiles/local-opik.yaml` extending `local` profile
- [x] Set `providers.observability: opik` in the new profile
- [x] Set `otel_exporter_otlp_endpoint` to `http://localhost:5174/api/v1/private/otel`
- [x] Validate profile with `python -m src.cli profile validate local-opik`

## Phase 3: Add Opik Stack Management Targets
> Add make targets for starting/stopping the Opik observability stack

- [x] Add `opik-up` target: starts Opik stack with health check wait
- [x] Add `opik-down` target: stops Opik stack
- [x] Add `opik-logs` target: tails Opik stack logs
- [x] Test `make opik-up` waits for backend health check before returning

## Phase 4: Add Profile-Based Dev Targets
> Add make targets that set profile and start development servers

- [x] Add `dev-local` target: runs `PROFILE=local make dev-bg`
- [x] Add `dev-opik` target: checks Opik running, then runs `PROFILE=local-opik make dev-bg`
- [x] Add `full-up` target: starts main services + Opik stack
- [x] Add `full-down` target: stops all services including Opik

## Phase 5: Add E2E Verification Targets
> Add make targets to verify profile configuration works end-to-end

- [x] Add `verify-profile` target: checks API health, validates current profile
- [x] Add `verify-opik` target: sends test trace, confirms Opik receives it
- [x] Test `make verify-opik` with `PROFILE=local-opik` shows trace in Opik UI

## Phase 6: Documentation
> Update documentation with profile-based workflow

- [x] Add "Profile-Based Development" section to `docs/PROFILES.md`
- [x] Add make target quick reference to `CLAUDE.md`
- [x] Update `docs/SETUP.md` with Opik local development instructions

## Validation
- [ ] Run `make opik-up && make dev-opik` and verify API starts with Opik tracing
- [ ] Run `make verify-opik` and confirm trace appears in Opik UI at http://localhost:5174
- [ ] Run `make full-down` and verify all services stop cleanly
- [ ] Verify Vite dev server (port 5173) can run simultaneously with Opik (port 5174)
