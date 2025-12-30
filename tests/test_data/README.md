# Test Data

This directory contains test fixtures for integration tests.

## Directory Structure

```
test_data/
├── newsletters/          # Sample newsletter JSON files
│   ├── newsletter_1_llm_advances.json
│   ├── newsletter_2_vector_databases.json
│   └── newsletter_3_agent_frameworks.json
└── README.md
```

## Newsletter Format

Each newsletter JSON file contains:

```json
{
  "source": "GMAIL",
  "source_id": "unique-test-id",
  "sender": "sender@example.com",
  "publication": "Publication Name",
  "title": "Newsletter Title",
  "published_date": "2025-01-13T10:00:00Z",
  "url": "https://example.com/newsletter",
  "raw_html": "<html>...</html>",
  "raw_text": "Plain text version..."
}
```

## Usage

Use the test data helpers in `tests/helpers/test_data.py`:

```python
from tests.helpers.test_data import create_test_newsletters_batch

# Load all test newsletters into database
newsletters = create_test_newsletters_batch(db_session)

# Load specific newsletters
newsletters = create_test_newsletters_batch(
    db_session,
    filenames=["newsletter_1_llm_advances.json"]
)
```

## Adding New Test Newsletters

1. Create a new JSON file in `newsletters/`
2. Follow the format above
3. Use descriptive filenames: `newsletter_N_topic.json`
4. Include realistic content for testing summarization and theme extraction
