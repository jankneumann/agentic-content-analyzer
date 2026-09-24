# Tailnet Exposure (gx-10)

How the ACA API and OpenBao on the self-hosted gx-10 host are reached over
Tailscale, and how to prove nothing else can reach them.

> **The rule:** on gx-10, the API and OpenBao listen on **loopback only**.
> The single way in from another machine is `tailscale serve` on gx-10's
> Tailscale address, which terminates TLS with a browser-trusted certificate and
> is gated by the tailnet policy. Nothing binds `0.0.0.0` or a LAN address, and
> nothing is published to the internet (no Funnel, no router port forward).

Every later credential write (the `aca auth` capture CLI writing to OpenBao, the
worker healing rotated cookies, the extension syncing) assumes this baseline.

Placeholders used throughout: `gx-10.<tailnet>.ts.net` is gx-10's MagicDNS
name (`tailscale status --self` or the admin console shows yours);
`100.x.y.z` is its Tailscale IPv4 (`tailscale ip -4`).

---

## Topology

```
 phone / laptop (user-owned)          workstation (tag:workstation)
   Chrome, extension, web UI            aca auth ..., bao CLI, Chrome
        │  tcp:443 only                     │  tcp:443 + tcp:8200
        └──────────────┬────────────────────┘
                WireGuard (tailnet policy enforced here)
                       │
 gx-10 (tag:gx10) ─────┼────────────────────────────────────────────────
   tailscaled  100.x.y.z:443   ── tailscale serve (TLS, LE cert) ──► 127.0.0.1:8000  aca-api.service (uvicorn)
               100.x.y.z:8200  ── tailscale serve (TLS, LE cert) ──► 127.0.0.1:8200  OpenBao (docker, published on loopback)
               100.x.y.z:8443  ── tailscale serve (optional web UI) ► 127.0.0.1:<ui-port>
   worker / aca backup run ─────────────────────── http://127.0.0.1:8200 (never leaves the host)
 LAN (192.168.x.x) ── nothing listening for 8000 / 8200
```

## Bind addresses

| Service | Process binds | Reached from the tailnet at | Who may reach it | Config |
|---|---|---|---|---|
| ACA API | `127.0.0.1:8000` | `https://gx-10.<tailnet>.ts.net` (443) | phones, laptops, workstation | `deploy/gx10/aca-api.service` (`ACA_API_HOST`, `PORT`) |
| OpenBao API | `127.0.0.1:8200` (docker publish) | `https://gx-10.<tailnet>.ts.net:8200` | workstation only | `deploy/gx10/docker-compose.gx10.yml` (`ACA_BAO_BIND_ADDR`) |
| OpenBao cluster | `8201` inside the container only | not published | nobody | `deploy/gx10/openbao.hcl` |
| Web UI (optional) | `127.0.0.1:<ui-port>` | `https://gx-10.<tailnet>.ts.net:8443` | phones, laptops, workstation | `tailscale serve --https=8443` |
| MCP HTTP (if run) | set `MCP_HOST=127.0.0.1` (default is `0.0.0.0`) | not served | local only | `src/mcp_server.py` |

The settings that control this, all in `/etc/aca/aca.env`
(template: [`deploy/gx10/aca-gx10.env.example`](../deploy/gx10/aca-gx10.env.example)):

| Variable | gx-10 value | Consumer | Default elsewhere |
|---|---|---|---|
| `ACA_API_HOST` | `127.0.0.1` | `docker-entrypoint.sh` → `uvicorn --host` | `0.0.0.0` (correct inside a container; the published port decides exposure) |
| `PORT` | `8000` | `docker-entrypoint.sh` → `uvicorn --port` | `8000` (Railway injects its own) |
| `ACA_FORWARDED_ALLOW_IPS` | `127.0.0.1` | `uvicorn --forwarded-allow-ips` | `*` |
| `ACA_BAO_BIND_ADDR` | `127.0.0.1` | compose port publish host IP | `127.0.0.1` |

`ACA_FORWARDED_ALLOW_IPS` matters: uvicorn resolves the client IP from
`X-Forwarded-For` only for trusted peers, and that IP keys the login rate
limiter. `127.0.0.1` trusts `tailscale serve` (which connects from loopback)
and nobody else.

The dev files are untouched: `docker-compose.openbao.yml` (dev mode, `8200` on
all interfaces) and the `make api` targets (`--host 0.0.0.0`) are for a
workstation and must **not** run on gx-10. The gx-10 compose file is
standalone rather than an overlay because Compose concatenates `ports` across
`-f` files, so an overlay cannot remove the dev overlay's `0.0.0.0:8200`.

## Setup

Prerequisites, once per tailnet (admin console → **DNS**): enable **MagicDNS**
and **HTTPS Certificates**. Each client that should resolve the name must run
Tailscale with "Use Tailscale DNS" on.

On gx-10, from the checkout at `/opt/aca`:

```bash
# 0. Tag the host (tags are owned per the policy below). Note that `tailscale up`
#    resets any non-default flags you do not repeat.
sudo tailscale up --advertise-tags=tag:gx10

# 1. Environment file (root-owned, 0600), then edit every <placeholder>.
sudo install -d -m 0755 /etc/aca
sudo install -m 0600 -o root -g root deploy/gx10/aca-gx10.env.example /etc/aca/aca.env
sudo $EDITOR /etc/aca/aca.env

# 2. OpenBao, published on loopback. Then init/unseal/seed per docs/OPENBAO.md.
sudo docker compose -p aca-gx10 --env-file /etc/aca/aca.env \
  -f deploy/gx10/docker-compose.gx10.yml up -d

# 3. API, bound to loopback.
sudo useradd --system --home /opt/aca --shell /usr/sbin/nologin aca   # once
sudo install -m 0644 deploy/gx10/aca-api.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now aca-api.service

# 4. Publish both to the tailnet with Let's Encrypt certificates for the MagicDNS name.
sudo tailscale serve --bg 8000                                   # https://gx-10.<tailnet>.ts.net      -> 127.0.0.1:8000
sudo tailscale serve --bg --https=8200 http://127.0.0.1:8200     # https://gx-10.<tailnet>.ts.net:8200 -> 127.0.0.1:8200
# optional web UI:
# sudo tailscale serve --bg --https=8443 http://127.0.0.1:<ui-port>
tailscale serve status
```

`--bg` persists the serve config across reboots. `tailscale serve` obtains and
renews the certificate itself; the first HTTPS request after enabling it can
take a few seconds while the certificate is issued. Undo with
`sudo tailscale serve --https=8200 off` (or `sudo tailscale serve reset`).

**Never run `tailscale funnel`** for either service; Funnel publishes to the
internet. `tailscale funnel status` must report nothing.

## Tailscale policy (ACL sketch)

Tailnet groups contain *users*, not devices, so the workstation/mobile split is
made with a tag: the workstation is `tag:workstation` and gets OpenBao; phones
and laptops stay user-owned devices of `group:aca-operators` and get the API
only. Paste into the admin console (**Access controls**), replacing the email.
The policy file is HuJSON, so comments are allowed.

```jsonc
{
  "groups": {
    "group:aca-operators": ["operator@example.com"]
  },

  "tagOwners": {
    "tag:gx10":        ["autogroup:admin"],
    "tag:workstation": ["autogroup:admin"]
  },

  "grants": [
    // Phones and laptops (user-owned devices): the API over HTTPS, nothing else.
    { "src": ["group:aca-operators"], "dst": ["tag:gx10"], "ip": ["tcp:443"] },

    // Optional web UI served on :8443.
    { "src": ["group:aca-operators"], "dst": ["tag:gx10"], "ip": ["tcp:8443"] },

    // The workstation: the API plus OpenBao (writes browser-session cookies).
    { "src": ["tag:workstation"], "dst": ["tag:gx10"], "ip": ["tcp:443", "tcp:8200"] }

    // Add your own admin path (e.g. Tailscale SSH or tcp:22) separately.
    // REMOVE the default allow-all grant/acl ({"src":["*"],"dst":["*"],...}) —
    // with it in place, every rule above is moot.
  ],

  "tests": [
    { "src": "operator@example.com", "accept": ["tag:gx10:443"], "deny": ["tag:gx10:8200"] },
    { "src": "tag:workstation",      "accept": ["tag:gx10:443", "tag:gx10:8200"] }
  ]
}
```

Notes:

- Tagging a device removes its user identity. If the workstation must stay
  user-owned, replace `tag:workstation` with a `hosts` alias for its Tailscale IP
  (`"hosts": {"aca-workstation": "100.a.b.c"}`) and use that alias as the `src`.
- gx-10 needs no inbound grant for itself: the worker and `aca backup run` use
  loopback.
- Do not grant the `funnel` node attribute to `tag:gx10`.

## Client values

| Client | Setting | Value |
|---|---|---|
| Workstation (`aca auth ...`, `bao`, seed script) | `BAO_ADDR` | **`BAO_ADDR=https://gx-10.<tailnet>.ts.net:8200`** |
| Processes on gx-10 (API, worker, backup) | `BAO_ADDR` | `http://127.0.0.1:8200` |
| CLI in HTTP mode, MCP HTTP client, iOS Shortcut | API URL | `https://gx-10.<tailnet>.ts.net` |
| Chrome extension (Options → API URL) | API URL | `https://gx-10.<tailnet>.ts.net` |
| Web UI build | `VITE_API_URL` | `https://gx-10.<tailnet>.ts.net` |

`hvac` (the OpenBao client) verifies the certificate against the system/certifi
bundle, which already trusts Let's Encrypt, so no `BAO_CACERT` is needed. Use the
full MagicDNS name: the certificate is not valid for `gx-10`, `100.x.y.z`, or
`localhost`.

### CORS

Only browser origins need CORS; the CLI, MCP, and Shortcuts do not.

```bash
# /etc/aca/aca.env
ENVIRONMENT=production
ALLOWED_ORIGINS=https://gx-10.<tailnet>.ts.net:8443,chrome-extension://<extension-id>
```

- **Web UI on `:8443`**: its origin differs from the API's only by port, so it
  is cross-origin but *same-site*. The `SameSite=Lax` session cookie is sent, so
  `AUTH_COOKIE_CROSS_ORIGIN` stays `false`. Set it to `true` only if the UI is
  served from a different host.
- **Chrome extension**: the extension currently declares no host permission, so
  its fetches carry `Origin: chrome-extension://<extension-id>` (the ID shown on
  `chrome://extensions`) and are CORS-checked. Once the manifest gains
  `"host_permissions": ["https://gx-10.<tailnet>.ts.net/*"]`, Chrome exempts the
  extension from CORS for that host and the `chrome-extension://` entry can go.
  See [extension/README.md](../extension/README.md).
- In production, leaving `ALLOWED_ORIGINS` at the localhost dev default yields an
  **empty** allow-list (deny all), by design.

## Browser-session sync endpoint

The Chrome extension's "Sync session" action pushes freshly read cookies to the
API over the tailnet. It is the laptop-side answer to a session-expiry alert;
`aca auth session substack|x` stays the workstation path.

```bash
# X: both cookies, written together
curl -sS -X PUT "https://gx-10.<tailnet>.ts.net/api/v1/browser-sessions/x" \
  -H "X-Admin-Key: $ADMIN_API_KEY" -H "Content-Type: application/json" \
  --data @x-session.json        # {"auth_token": "...", "ct0": "..."}
# Substack: {"substack_sid": "..."} to /api/v1/browser-sessions/substack
```

- **Auth:** the `X-Admin-Key` header only. A web-UI session cookie or the
  unconfigured-development bypass gets `401`. Every call is written to
  `audit_log` (operation `browser_sessions.sync`, `admin_key_fp` from the raw
  header, notes with site, outcome and key names; never a value).
- **Body:** exactly the site's cookie fields (unknown fields `422`), each a
  cookie value of at most 4096 characters; bodies over 16 KiB get `413`.
- **Validation:** before writing, the API makes the same single request as the
  CLI (Substack subscriptions / X `account/settings.json`). A refused session is
  `422` `session_invalid`; a site outage, throttle or network error is `502`
  `session_validation_unavailable`. Nothing is written in either case.
- **Write:** one KV v2 merge-PATCH on `BAO_MOUNT_PATH/BAO_SECRET_PATH`
  (`SUBSTACK_SESSION_COOKIE`, or `X_AUTH_TOKEN` + `X_CT0`, each with
  `<KEY>_SAVED_AT`), then the API's own credential cache is updated with the
  same `saved_at`. The response lists `site`, `keys_written` and `saved_at`.
- **OpenBao required:** the API needs `BAO_ADDR` and `BAO_ROLE_ID`/`BAO_SECRET_ID`
  (the `newsletter-app` role with the `patch` capability, seeded by
  `scripts/bao_seed_newsletter.py --with-session-roles`) or `BAO_TOKEN`. Without
  them the endpoint answers `503` `openbao_not_configured` and names what is
  missing. It never falls back to `.secrets.yaml`, the environment or Railway.
  A PATCH OpenBao refuses is `502` `openbao_write_failed`.
- **Rate limit:** 10 calls per 5 minutes per client IP (`429` with
  `Retry-After`), since every call costs a request to Substack or X.

## Verify

### 1. Listener check (on gx-10)

```bash
sudo ss -ltnp '( sport = :8000 or sport = :8200 )'
```

Expected — both in the **Local Address** column on `127.0.0.1`:

```
State  Recv-Q Send-Q Local Address:Port  Peer Address:Port Process
LISTEN 0      2048       127.0.0.1:8000       0.0.0.0:*     users:(("uvicorn",pid=1234,fd=7))
LISTEN 0      4096       127.0.0.1:8200       0.0.0.0:*     users:(("docker-proxy",pid=2345,fd=4))
```

The `0.0.0.0:*` in the **Peer** column is normal (any remote peer). A failure
looks like `0.0.0.0:8200`, `*:8200`, `[::]:8000`, or a LAN address in the
**Local** column. `tailscaled` may or may not show its own `443`/`8200` sockets
on `100.x.y.z` depending on version; those are the serve front ends and are
expected.

As an assertion:

```bash
sudo ss -ltnH '( sport = :8000 or sport = :8200 )' | awk '{print $4}' \
  | grep -Ev '^(127\.0\.0\.1|\[::1\]|100\.[0-9.]+|\[fd7a:115c:a1e0:[0-9a-f:]*\]):[0-9]+$' \
  && echo "FAIL: listener beyond loopback/tailnet" || echo "OK: loopback/tailnet only"
```

### 2. Negative checks

```bash
# From another machine on the LAN (NOT via Tailscale): both must be refused/time out.
curl -m 3 http://<gx-10-lan-ip>:8000/health
curl -m 3 http://<gx-10-lan-ip>:8200/v1/sys/health

# From a phone or laptop on the tailnet: 8200 must time out (policy deny).
curl -m 3 https://gx-10.<tailnet>.ts.net:8200/v1/sys/health
```

### 3. Positive checks

```bash
# Any allowed device: API over HTTPS with a publicly trusted certificate.
curl -sS https://gx-10.<tailnet>.ts.net/health

# Issuer should be Let's Encrypt; subject the MagicDNS name.
openssl s_client -connect gx-10.<tailnet>.ts.net:443 -servername gx-10.<tailnet>.ts.net </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -enddate

# Workstation only: OpenBao.
BAO_ADDR=https://gx-10.<tailnet>.ts.net:8200 bao status
```

In Chrome, `https://gx-10.<tailnet>.ts.net/health` loads with the padlock and
no interstitial. That is the acceptance bar: no "Proceed anyway", no manually
installed CA.

## Alternatives

**Direct bind (no serve for OpenBao).** Set `ACA_BAO_BIND_ADDR=100.x.y.z` and
skip the `--https=8200` serve. Traffic is WireGuard-encrypted but plain HTTP, so
the workstation uses `BAO_ADDR=http://gx-10.<tailnet>.ts.net:8200`, and processes
on gx-10 must use the same address (loopback is no longer published). Docker
fails to publish on `100.x.y.z` if `tailscaled` is not up yet; add a drop-in
ordering `docker.service` after `tailscaled.service`. The same applies to the API
with `ACA_API_HOST=100.x.y.z`, but then there is no trusted certificate unless you
also use `tailscale cert`.

**`tailscale cert` instead of serve.** `sudo tailscale cert gx-10.<tailnet>.ts.net`
writes a `.crt`/`.key` pair that uvicorn (`--ssl-certfile/--ssl-keyfile`) or the
OpenBao listener (`tls_cert_file/tls_key_file`) can use directly on `100.x.y.z`.
Certificates last 90 days and you must re-run the command and restart the
service to renew, which serve does for you. Prefer serve.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `tailscale serve` errors that HTTPS is not enabled | HTTPS Certificates off for the tailnet | Admin console → DNS → enable HTTPS Certificates (MagicDNS first) |
| Chrome `NET::ERR_CERT_COMMON_NAME_INVALID` | Using `gx-10`, an IP, or `localhost` | Use the full `gx-10.<tailnet>.ts.net` name |
| Name does not resolve on a phone | Tailscale off, or "Use Tailscale DNS" disabled | Enable both in the Tailscale app |
| Timeout from a device that should be allowed | Policy does not grant it | Check the grant; run the policy `tests`; `tailscale ping gx-10` |
| `8200` reachable from a phone | Default allow-all rule still present, or phone tagged `tag:workstation` | Remove the allow-all rule; re-run the policy tests |
| `502 Bad Gateway` from the MagicDNS URL | Backend not listening on loopback | `systemctl status aca-api`; `curl http://127.0.0.1:8000/health`; `docker compose -p aca-gx10 ps` |
| `ss` shows `0.0.0.0:8200` | The dev overlay (`docker-compose.openbao.yml`) is running on gx-10, or `ACA_BAO_BIND_ADDR` is wrong | `docker ps --format '{{.Names}} {{.Ports}}'`; stop the dev stack; fix `/etc/aca/aca.env` |
| `ss` shows nothing for `8200` but it works | Docker userland proxy disabled; publishing is done by NAT rules | `sudo iptables -t nat -S DOCKER \| grep 8200` must show `-d 127.0.0.1/32` |
| `tailscale serve --https=8200` rejected | Older Tailscale client limits HTTPS serve ports | Upgrade, or serve on `8443`/`10000` and change the grant and `BAO_ADDR` to match |
| OpenBao answers `503` / `bao status` shows `Sealed true` | Restarted and not unsealed | Unseal per [OPENBAO.md](OPENBAO.md); the container is unhealthy until then |
| Docker: `cannot assign requested address` (direct bind) | `tailscaled` not up when the container started | Order `docker.service` after `tailscaled.service`, or use the loopback + serve recipe |
| CORS preflight `OPTIONS ... 400` | Origin not in `ALLOWED_ORIGINS` (empty in production by default) | Add the exact origin, including `:8443` or `chrome-extension://<id>` |
| All logins share one rate-limit bucket / audit shows `127.0.0.1` | Forwarded headers not trusted | `ACA_FORWARDED_ALLOW_IPS=127.0.0.1` and `--proxy-headers` (both set by the unit/entrypoint) |
| `aca-api` exits with `Profile 'production' not found` | No `production` profile on this checkout | Create it under `profiles/`, or set `PROFILE=` in `/etc/aca/aca.env` |

## Security notes

- Docker-published ports bypass `ufw`/`firewalld`. On gx-10 the bind address
  **is** the firewall, which is why every publish names a host IP.
- Issued certificates appear in public Certificate Transparency logs, so the
  MagicDNS name (and your tailnet name) becomes public. The services are still
  unreachable without tailnet membership and a matching grant.
- The Postgres, Neo4j, and FalkorDB services in the root `docker-compose.yml`
  publish on all interfaces with development credentials. Do not run that file
  unmodified on gx-10.

## Related

- [OpenBao](OPENBAO.md) — init, unseal, AppRole, seeding.
- [Backup & Restore](BACKUP_RESTORE.md) — `aca backup run` reads OpenBao over loopback.
- [Mobile deployment](MOBILE_DEPLOYMENT.md#frontend-as-separate-service) — `ALLOWED_ORIGINS`, `AUTH_COOKIE_CROSS_ORIGIN`.
- [Content capture](CONTENT_CAPTURE.md) and [extension/README.md](../extension/README.md).
