# Change: Add staging profile for CI/CD validation

## Why
CI/CD needs a production-like staging profile that bridges local development and Railway production while sending observability to a dedicated staging project.

## What Changes
- Add a `profiles/staging.yaml` template targeting Railway + AuraDB + MinIO with staging-specific env overrides
- Document the staging profile and guidance for seeding curated data in `docs/PROFILES.md`
- Update profile configuration specs to include the staging template

## Impact
- Affected specs: `specs/profile-configuration/spec.md`
- Affected code/docs: `profiles/staging.yaml`, `docs/PROFILES.md`
