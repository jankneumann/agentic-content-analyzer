# GX-10 validation status: INCOMPLETE

The package's static checkpoint previously completed with **305 passed** tests.
That is partial evidence only; it does not satisfy task 8.5's clean local stack
The remediation suite now completes with **310 passed** and zero failures,
errors, or skips. This remains static/fixture evidence, not a live-stack pass.
requirement.

The following live checks remain incomplete in this environment:

- Docker access and a clean Compose down/up/down/up cold restart;
- Caddy configuration validation inside the pinned container;
- initialized, authenticated, and unsealed OpenBao lifecycle checks;
- live authenticated Squid CONNECT, denied direct route, and failure matrix;
- persistent-mount survival and post-start dependency-loss readiness;
- registry provenance for `ubuntu/squid:6.13-25.10_beta`, whose reviewed tag
  returned HTTP 404 during validation.

No live cold-restart success is claimed. Task 8.5 must remain unchecked until
the following command exits successfully on a clean GX-10 host:

```bash
sudo --preserve-env=GX10_APP_IMAGE,GX10_SQUID_DIGEST \
  scripts/gx10/verify_clean_stack.sh
```

The gate verifies the protected image pins against registry manifests before
starting services, renders and validates Compose, checks root-owned 0600 runtime
files, executes the failure harness, validates Caddy and OpenBao in their pinned
containers, performs a true cold restart, reruns role readiness, and only then
