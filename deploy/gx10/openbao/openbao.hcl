ui = false
# OpenBao 2.x dropped mlock support and refuses to start if disable_mlock is
# set at all. Harden swap on the host instead (see openbao.org post-install).
api_addr = "http://openbao:8200"
cluster_addr = "https://openbao:8201"

storage "raft" {
  path = "/openbao/data"
  node_id = "aca-gx10-openbao"
}

listener "tcp" {
  address = "0.0.0.0:8200"
  cluster_address = "0.0.0.0:8201"
  tls_disable = true
}

telemetry {
  disable_hostname = true
  prometheus_retention_time = "30s"
}
