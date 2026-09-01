# GX-10 validation status: INCOMPLETE

Automated static and fixture checks are partial evidence only. They do not
satisfy task 8.5's clean local-stack requirement and must never be represented
as a live cold-restart pass.

The following live checks remain incomplete in this environment:

- rootful Podman access and a clean Compose down/up/down/up cold restart;
- Caddy configuration validation inside the pinned container;
- initialized, authenticated, and unsealed OpenBao lifecycle checks;
- live authenticated Squid CONNECT, denied direct route, and failure matrix;
- persistent-mount survival and post-start dependency-loss readiness;
- registry provenance for the approved ARM64 `ubuntu/squid:6.6-24.04_beta`
  manifest during a real rootful Podman run.

## Explicit first-install OpenBao ceremony

First installation is separate from the normal cold-restart path. A root
operator must create `/etc/aca/gx10/bao-seed.json` with mode `0600`; it contains
three JSON objects named `runtime`, `operator`, and `proxy`, populated with the
fields consumed by `render-secrets.sh`. With the reviewed image environment in
place and the normal runtime stopped, run:

```bash
sudo systemctl start aca-gx10-openbao-provision.service
sudo test -s /etc/aca/gx10/openbao-provisioned.ready
```

The one-shot ceremony initializes an uninitialized OpenBao instance, writes
the generated bootstrap token and unseal key as root-owned `0600` operator
files, enables KV v2 and AppRole idempotently, installs the least-privilege
policy, and seeds all three GX-10 paths. The unit has no `[Install]` section and
is not referenced by `aca-gx10.service` or `aca-gx10-secrets.service`, so a cold
restart cannot silently rerun initialization. After verifying the ceremony,
the operator should remove or rotate the seed source according to the external
secret-management procedure.

## Live clean-stack gate

No live cold-restart success is claimed. Task 8.5 must remain unchecked until
the following command exits successfully on a clean GX-10 host:

```bash
sudo --preserve-env=GX10_APP_IMAGE,GX10_SQUID_DIGEST,GX10_LANGFUSE_WORKER_DIGEST \
  scripts/gx10/verify_clean_stack.sh
```

The gate verifies the protected application, Squid, and dedicated Langfuse
worker image pins against registry manifests before
starting services, renders and validates Compose, checks root-owned `0600`
runtime files, executes the failure harness, validates Caddy and OpenBao in
their pinned containers, stops mapped dependencies and requires unhealthy role
transitions with local diagnostics and recovery, seeds every required
persistent mount and native queued-operation/Langfuse/ClickHouse records,
performs a true down/up cold restart, verifies every record, brings the stack
down, and only then emits checksum-protected evidence under
`/srv/aca/validation`.
