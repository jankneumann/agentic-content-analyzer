"""Test Summary model performance optimizations."""

from sqlalchemy import inspect, create_engine
from src.models.base import Base
from src.models.summary import Summary


def test_summary_model_used_index():
    """Verify that the model_used column in summaries table is indexed.

    This test creates its own in-memory SQLite database to be independent of
    complex global fixtures that might fail in some environments.
    """
    # Use in-memory SQLite for speed and isolation
    engine = create_engine("sqlite:///:memory:")

    # Create tables
    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    indexes = inspector.get_indexes("summaries")

    # Check if ix_summaries_model_used exists
    index_names = [i["name"] for i in indexes]

    # Note: SQLite might auto-generate index names if not explicitly named in some contexts,
    # but SQLAlchemy usually respects the name we give in the migration or model.
    # However, since we rely on `Base.metadata.create_all` in tests (not migration scripts directly),
    # the index name comes from the Model definition `index=True` which defaults to `ix_table_column`.

    assert "ix_summaries_model_used" in index_names, f"Index ix_summaries_model_used not found. Available: {index_names}"

    # Verify the column
    index = next(i for i in indexes if i["name"] == "ix_summaries_model_used")
    assert index["column_names"] == ["model_used"]
