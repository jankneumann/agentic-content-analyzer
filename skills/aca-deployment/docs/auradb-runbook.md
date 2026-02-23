# AuraDB Operations Runbook

Neo4j AuraDB hosts the knowledge graph, providing entity resolution, theme tracking, and historical context for content analysis.

## Architecture

The knowledge graph stores:
- **Entities**: People, organizations, technologies, concepts extracted from content
- **Relationships**: Co-occurrence, mentions, influences between entities
- **Themes**: Recurring topics tracked across time windows

The app connects to AuraDB via the Bolt protocol (`neo4j+s://` for cloud).

## CLI Reference

The `aura` CLI manages AuraDB instances. It's optional — the app itself uses the Neo4j Python driver directly.

```bash
# Authentication
aura auth login                        # Browser-based OAuth
aura version                           # Verify installation

# Instance management
aura instance list                     # List all instances
aura instance list --output table      # Tabular output

# Lifecycle
aura instance pause <instance-id>      # Pause (saves costs)
aura instance resume <instance-id>     # Resume from pause
aura instance snapshot create <id>     # Create backup snapshot

# Instance details
aura instance get <instance-id>        # Full instance info
```

### Installing the Aura CLI

The `aura` CLI is a standalone binary from Neo4j:

```bash
# macOS (Intel)
curl -L https://github.com/neo4j/aura-cli/releases/latest/download/aura-darwin-amd64 -o aura
chmod +x aura && sudo mv aura /usr/local/bin/

# macOS (Apple Silicon)
curl -L https://github.com/neo4j/aura-cli/releases/latest/download/aura-darwin-arm64 -o aura
chmod +x aura && sudo mv aura /usr/local/bin/

# Linux
curl -L https://github.com/neo4j/aura-cli/releases/latest/download/aura-linux-amd64 -o aura
chmod +x aura && sudo mv aura /usr/local/bin/
```

## Configuration

### Profile settings

```yaml
# profiles/railway-neon.yaml (or railway.yaml)
providers:
  neo4j: auradb

settings:
  neo4j:
    neo4j_auradb_uri: "${NEO4J_AURADB_URI}"
    neo4j_auradb_user: neo4j
    neo4j_auradb_password: "${NEO4J_AURADB_PASSWORD}"
```

### Secrets

```yaml
# .secrets.yaml
NEO4J_AURADB_URI: neo4j+s://xxxxxxxx.databases.neo4j.io
NEO4J_AURADB_PASSWORD: your-auradb-password
```

### Local development alternative

For local development, use Docker instead of AuraDB:

```yaml
# profiles/local.yaml
providers:
  neo4j: local

settings:
  neo4j:
    neo4j_local_uri: bolt://localhost:7687
    neo4j_local_user: neo4j
    neo4j_local_password: newsletter_password
```

## Common Operations

### Check instance status

```bash
# Via aura CLI
aura instance list --output table

# Via profile (when aura CLI not installed)
aca profile show ${PROFILE:-local} 2>/dev/null | grep -i neo4j
```

### Pause for cost savings

AuraDB free tier instances auto-pause after inactivity. Paid instances can be paused manually:

```bash
aura instance pause <instance-id>
# Instance becomes unavailable immediately
# Knowledge graph queries will fail until resumed
```

### Resume from pause

```bash
aura instance resume <instance-id>
# Takes 1-2 minutes to become fully available
# Monitor with: aura instance get <instance-id>
```

### Create a backup snapshot

```bash
aura instance snapshot create <instance-id>
# Snapshots are stored by Neo4j, accessible from the console
```

### Test connectivity

```bash
# Quick connectivity test using cypher-shell (if installed)
cypher-shell -a "$NEO4J_AURADB_URI" \
  -u neo4j \
  -p "$NEO4J_AURADB_PASSWORD" \
  "RETURN 1"

# Or via Python
python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('$NEO4J_AURADB_URI', auth=('neo4j', '$NEO4J_AURADB_PASSWORD'))
with driver.session() as s:
    print(s.run('RETURN 1').single()[0])
driver.close()
"
```

## Troubleshooting

### Instance is paused

AuraDB free-tier instances auto-pause after 3 days of inactivity. Resume via the console or CLI:

```bash
aura instance resume <instance-id>
```

The app will get connection errors until the instance finishes resuming (1-2 minutes).

### Connection URI format

AuraDB uses `neo4j+s://` (encrypted) for cloud instances. Local Neo4j uses `bolt://` (unencrypted) or `bolt+s://` (encrypted).

Wrong URI format causes silent connection failures. Verify:
```bash
echo "$NEO4J_AURADB_URI"  # Should start with neo4j+s://
```

### Password contains special characters

If the AuraDB-generated password contains special characters, ensure it's properly quoted in `.secrets.yaml`:

```yaml
# Correct — quote values with special chars
NEO4J_AURADB_PASSWORD: "p@ss!word#123"

# Wrong — YAML may interpret special characters
NEO4J_AURADB_PASSWORD: p@ss!word#123
```

### App doesn't check Neo4j health

The `/ready` endpoint checks only PostgreSQL and the queue. Neo4j failures are silent from a health check perspective. Monitor via:
- Application logs (look for Neo4j connection errors)
- `aura instance list` for instance status
- Knowledge graph features returning empty results

### Free tier limitations

AuraDB free tier:
- 200K nodes, 400K relationships
- Auto-pauses after 3 days idle
- Single instance per account
- No snapshots (paid feature)

For production use with this project's knowledge graph, the free tier is typically sufficient unless ingesting very high content volumes.

### Setting up AuraDB from scratch

1. Go to [console.neo4j.io](https://console.neo4j.io/)
2. Create a free AuraDB instance
3. Save the generated password (shown only once)
4. Copy the connection URI (`neo4j+s://...`)
5. Add to `.secrets.yaml`:
   ```yaml
   NEO4J_AURADB_URI: neo4j+s://xxxxxxxx.databases.neo4j.io
   NEO4J_AURADB_PASSWORD: generated-password
   ```
6. Set `NEO4J_PROVIDER=auradb` in your profile
