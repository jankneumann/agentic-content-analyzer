# Read-only AppRole policy for the GX-10 secret renderer.  Runtime, operator,
# proxy, and third-party provider credentials rotate independently and never
# enter Compose YAML.
path "secret/data/newsletter/gx10/runtime" {
  capabilities = ["read"]
}

path "secret/data/newsletter/gx10/operator" {
  capabilities = ["read"]
}

path "secret/data/newsletter/gx10/proxy" {
  capabilities = ["read"]
}

path "secret/data/newsletter/gx10/providers" {
  capabilities = ["read"]
}

# Optional: credential-gated ingestion sources (worker only) and the alert route.
path "secret/data/newsletter/gx10/ingestion" {
  capabilities = ["read"]
}

path "secret/data/newsletter/gx10/alerts" {
  capabilities = ["read"]
}

path "secret/metadata/newsletter/gx10/runtime" {
  capabilities = ["read"]
}

path "auth/token/lookup-self" {
  capabilities = ["read"]
}

path "auth/token/renew-self" {
  capabilities = ["update"]
}
