"""Test Summary model performance optimizations."""

from src.models.base import Base


def test_summary_model_used_index():
    """Verify that the model_used column in summaries table is indexed.

    Previously this test created an in-memory SQLite engine and called
    Base.metadata.create_all(engine) to introspect the resulting schema.
    That fails now that the model graph references PostgreSQL-only
    JSONB columns (SQLite's type compiler has no ``visit_JSONB``).

    Introspect the SQLAlchemy model metadata directly instead — same
    invariant, no DB engine required.
    """
    summaries_table = Base.metadata.tables["summaries"]

    matching_indexes = [
        ix for ix in summaries_table.indexes if [c.name for c in ix.columns] == ["model_used"]
    ]
    assert matching_indexes, (
        f"No single-column index on `model_used` found in `summaries` table. "
        f"Indexes: {[ix.name for ix in summaries_table.indexes]}"
    )

    # SQLAlchemy auto-names single-column index=True indexes as ix_<table>_<column>.
    assert any(ix.name == "ix_summaries_model_used" for ix in matching_indexes), (
        f"Expected index name ix_summaries_model_used not found among "
        f"{[ix.name for ix in matching_indexes]}"
    )
