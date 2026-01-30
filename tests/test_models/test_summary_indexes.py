from src.models.summary import Summary

def test_summary_created_at_index_exists():
    """Verify that the created_at column in Summary model is indexed."""
    # Find index on created_at
    created_at_index = None
    for index in Summary.__table__.indexes:
        # Check if index contains created_at column
        # index.columns is a collection of Column objects
        if "created_at" in [c.name for c in index.columns]:
            created_at_index = index
            break

    assert created_at_index is not None, "Index on created_at column missing in Summary model"
