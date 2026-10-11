# Dedicated backup/restore renderer; no application or worker paths.
path "secret/data/newsletter/gx10/backup" {
  capabilities = ["read"]
}
path "secret/metadata/newsletter/gx10/backup" {
  capabilities = ["read"]
}
path "auth/token/lookup-self" {
  capabilities = ["read"]
}
path "auth/token/renew-self" {
  capabilities = ["update"]
}
# Off-site bucket credentials, rendered only by the off-site unit.
path "secret/data/newsletter/gx10/backup-offsite" {
  capabilities = ["read"]
}
