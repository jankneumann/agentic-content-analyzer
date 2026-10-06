# OpenBao server configuration for the gx-10 host.
#
# Mounted read-only at /openbao/config/openbao.hcl by docker-compose.gx10.yml.
# See docs/TAILNET.md for how this listener is reached and docs/OPENBAO.md for
# init, unseal, AppRole, and seeding.
#
# Exposure is decided OUTSIDE this file. The listener below binds every
# interface INSIDE the container; the compose file publishes it on the host at
# ${ACA_BAO_BIND_ADDR:-127.0.0.1}:8200 only, and `tailscale serve` is the single
# path in from another machine. Never publish 8200 without a host IP.

ui = false

# Integrated (raft) storage: `aca backup run` captures OpenBao with
# `bao operator raft snapshot save`, which requires it. Single node.
storage "raft" {
  path    = "/openbao/file"
  node_id = "gx10"
}

# Recommended with integrated storage (mlock would pin the whole raft mmap).
disable_mlock = true

listener "tcp" {
  address         = "0.0.0.0:8200"
  cluster_address = "0.0.0.0:8201"

  # TLS terminates at `tailscale serve`, which holds the browser-trusted
  # certificate for gx-10.<tailnet>.ts.net. Plain HTTP here only ever crosses
  # the host's loopback interface. If you instead bind 8200 directly to the
  # Tailscale address (docs/TAILNET.md, "Direct bind"), WireGuard encrypts the
  # hop, but prefer enabling TLS with a `tailscale cert` pair.
  tls_disable = true

  # Deliberately no x_forwarded_for_* settings: with them, OpenBao REJECTS a
  # connection from an authorized address that carries no X-Forwarded-For
  # header (x_forwarded_for_reject_not_present defaults to true), which is
  # exactly what the local worker and `aca backup run` send. The audit log
  # therefore records the local proxy address for tailnet callers.
}

# Raft requires both. They are addresses this node advertises to itself; the
# cluster port (8201) is never published.
api_addr     = "http://127.0.0.1:8200"
cluster_addr = "http://127.0.0.1:8201"
