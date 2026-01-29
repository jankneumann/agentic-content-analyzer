"""Tests for Summary model."""

from src.models.summary import Summary

def test_summary_created_at_index_exists():
    """Verify that the created_at column in Summary table is indexed.

    This is critical for performance when sorting or filtering summaries by date.
    """
    # Check if any index covers the 'created_at' column
    has_index = False

    # Inspect the indexes defined on the Table object
    for index in Summary.__table__.indexes:
        # Check if 'created_at' is in the columns of this index
        if 'created_at' in [c.name for c in index.columns]:
            has_index = True
            break

    assert has_index, "Summary.created_at should be indexed for performance"
