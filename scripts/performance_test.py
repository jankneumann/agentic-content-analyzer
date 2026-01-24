#!/usr/bin/env python3
"""Performance testing for unified Content model migration.

Tests query speed and storage efficiency of the new Content model
compared to the legacy Newsletter model.

Usage:
    python scripts/performance_test.py
    python scripts/performance_test.py --iterations 100
"""

import argparse
import statistics
import time
from datetime import datetime, timedelta

from sqlalchemy import func, text
from sqlalchemy.orm import joinedload

from src.models.content import Content, ContentStatus
from src.models.digest import Digest
from src.models.newsletter import Newsletter, ProcessingStatus
from src.models.summary import NewsletterSummary
from src.storage.database import get_db


def time_query(func, iterations=10):
    """Time a query function over multiple iterations."""
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        result = func()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to ms
    return {
        "min": min(times),
        "max": max(times),
        "mean": statistics.mean(times),
        "median": statistics.median(times),
        "stdev": statistics.stdev(times) if len(times) > 1 else 0,
        "result_count": len(result) if hasattr(result, "__len__") else 1,
    }


def run_query_benchmarks(iterations: int = 10):
    """Run query performance benchmarks."""
    print("\n" + "=" * 60)
    print("QUERY PERFORMANCE BENCHMARKS")
    print("=" * 60)

    with get_db() as db:
        # 1. Simple list queries
        print("\n--- Simple List Queries ---")

        def query_contents_list():
            return db.query(Content).order_by(Content.published_date.desc()).limit(50).all()

        def query_newsletters_list():
            return db.query(Newsletter).order_by(Newsletter.published_date.desc()).limit(50).all()

        content_stats = time_query(query_contents_list, iterations)
        newsletter_stats = time_query(query_newsletters_list, iterations)

        print(f"Content list (50 items):    {content_stats['mean']:.2f}ms (±{content_stats['stdev']:.2f}ms)")
        print(f"Newsletter list (50 items): {newsletter_stats['mean']:.2f}ms (±{newsletter_stats['stdev']:.2f}ms)")
        print(f"  → Difference: {((content_stats['mean'] - newsletter_stats['mean']) / newsletter_stats['mean'] * 100):+.1f}%")

        # 2. Filtered queries with status
        print("\n--- Filtered Queries (by status) ---")

        def query_contents_filtered():
            return (
                db.query(Content)
                .filter(Content.status == ContentStatus.COMPLETED)
                .order_by(Content.published_date.desc())
                .limit(50)
                .all()
            )

        def query_newsletters_filtered():
            return (
                db.query(Newsletter)
                .filter(Newsletter.status == ProcessingStatus.COMPLETED)
                .order_by(Newsletter.published_date.desc())
                .limit(50)
                .all()
            )

        content_stats = time_query(query_contents_filtered, iterations)
        newsletter_stats = time_query(query_newsletters_filtered, iterations)

        print(f"Content filtered:    {content_stats['mean']:.2f}ms (±{content_stats['stdev']:.2f}ms)")
        print(f"Newsletter filtered: {newsletter_stats['mean']:.2f}ms (±{newsletter_stats['stdev']:.2f}ms)")

        # 3. Join queries (Summary with source)
        print("\n--- Join Queries (Summary + Source) ---")

        def query_summaries_with_content():
            return (
                db.query(NewsletterSummary)
                .options(joinedload(NewsletterSummary.content))
                .filter(NewsletterSummary.content_id.isnot(None))
                .order_by(NewsletterSummary.created_at.desc())
                .limit(50)
                .all()
            )

        def query_summaries_with_newsletter():
            return (
                db.query(NewsletterSummary)
                .options(joinedload(NewsletterSummary.newsletter))
                .filter(NewsletterSummary.newsletter_id.isnot(None))
                .order_by(NewsletterSummary.created_at.desc())
                .limit(50)
                .all()
            )

        content_stats = time_query(query_summaries_with_content, iterations)
        newsletter_stats = time_query(query_summaries_with_newsletter, iterations)

        print(f"Summary+Content join:    {content_stats['mean']:.2f}ms (±{content_stats['stdev']:.2f}ms) [{content_stats['result_count']} results]")
        print(f"Summary+Newsletter join: {newsletter_stats['mean']:.2f}ms (±{newsletter_stats['stdev']:.2f}ms) [{newsletter_stats['result_count']} results]")

        # 4. Digest sources query (the one we just fixed)
        print("\n--- Digest Sources Query ---")

        # Get a digest with sources
        digest = db.query(Digest).filter(Digest.source_content_ids.isnot(None)).first()
        if digest and digest.source_content_ids:

            def query_digest_sources_content():
                return (
                    db.query(NewsletterSummary)
                    .join(Content, NewsletterSummary.content_id == Content.id)
                    .filter(NewsletterSummary.content_id.in_(digest.source_content_ids))
                    .order_by(Content.published_date.desc())
                    .all()
                )

            def query_digest_sources_period():
                return (
                    db.query(NewsletterSummary)
                    .join(Content, NewsletterSummary.content_id == Content.id)
                    .filter(Content.published_date >= digest.period_start)
                    .filter(Content.published_date <= digest.period_end)
                    .order_by(Content.published_date.desc())
                    .all()
                )

            id_stats = time_query(query_digest_sources_content, iterations)
            period_stats = time_query(query_digest_sources_period, iterations)

            print(f"By source_content_ids: {id_stats['mean']:.2f}ms (±{id_stats['stdev']:.2f}ms) [{id_stats['result_count']} results]")
            print(f"By period date range:  {period_stats['mean']:.2f}ms (±{period_stats['stdev']:.2f}ms) [{period_stats['result_count']} results]")
        else:
            print("No digest with source_content_ids found - skipping")

        # 5. Full-text search simulation (LIKE query)
        print("\n--- Text Search Queries ---")

        def query_content_search():
            return (
                db.query(Content)
                .filter(Content.markdown_content.ilike("%AI%"))
                .limit(20)
                .all()
            )

        def query_newsletter_search():
            return (
                db.query(Newsletter)
                .filter(Newsletter.raw_text.ilike("%AI%"))
                .limit(20)
                .all()
            )

        content_stats = time_query(query_content_search, iterations)
        newsletter_stats = time_query(query_newsletter_search, iterations)

        print(f"Content markdown search: {content_stats['mean']:.2f}ms (±{content_stats['stdev']:.2f}ms) [{content_stats['result_count']} results]")
        print(f"Newsletter text search:  {newsletter_stats['mean']:.2f}ms (±{newsletter_stats['stdev']:.2f}ms) [{newsletter_stats['result_count']} results]")


def run_storage_analysis():
    """Analyze storage usage of Content vs Newsletter models."""
    print("\n" + "=" * 60)
    print("STORAGE ANALYSIS")
    print("=" * 60)

    with get_db() as db:
        # Table sizes (PostgreSQL specific)
        print("\n--- Table Sizes ---")
        try:
            result = db.execute(
                text("""
                SELECT
                    relname as table_name,
                    pg_size_pretty(pg_total_relation_size(relid)) as total_size,
                    pg_size_pretty(pg_relation_size(relid)) as data_size,
                    pg_size_pretty(pg_indexes_size(relid)) as index_size
                FROM pg_catalog.pg_statio_user_tables
                WHERE relname IN ('contents', 'newsletters', 'newsletter_summaries', 'digests', 'documents')
                ORDER BY pg_total_relation_size(relid) DESC
            """)
            )
            for row in result:
                print(f"  {row.table_name:25} Total: {row.total_size:>10}  Data: {row.data_size:>10}  Index: {row.index_size:>10}")
        except Exception as e:
            print(f"  (Table size query not supported: {e})")

        # Column size estimates
        print("\n--- Average Row Sizes (estimated) ---")

        # Content model
        content_stats = db.execute(
            text("""
            SELECT
                COUNT(*) as count,
                AVG(LENGTH(markdown_content)) as avg_markdown,
                AVG(COALESCE(LENGTH(raw_content), 0)) as avg_raw,
                AVG(LENGTH(title)) as avg_title
            FROM contents
        """)
        ).fetchone()

        if content_stats and content_stats.count > 0:
            print(f"  Content ({content_stats.count} rows):")
            print(f"    avg markdown_content: {content_stats.avg_markdown:,.0f} bytes")
            print(f"    avg raw_content:      {content_stats.avg_raw:,.0f} bytes")
            print(f"    avg title:            {content_stats.avg_title:,.0f} bytes")

        # Newsletter model
        newsletter_stats = db.execute(
            text("""
            SELECT
                COUNT(*) as count,
                AVG(COALESCE(LENGTH(raw_text), 0)) as avg_raw_text,
                AVG(COALESCE(LENGTH(raw_html), 0)) as avg_raw_html,
                AVG(LENGTH(title)) as avg_title
            FROM newsletters
        """)
        ).fetchone()

        if newsletter_stats and newsletter_stats.count > 0:
            print(f"  Newsletter ({newsletter_stats.count} rows):")
            print(f"    avg raw_text:  {newsletter_stats.avg_raw_text:,.0f} bytes")
            print(f"    avg raw_html:  {newsletter_stats.avg_raw_html:,.0f} bytes")
            print(f"    avg title:     {newsletter_stats.avg_title:,.0f} bytes")

        # Summary markdown stats
        summary_stats = db.execute(
            text("""
            SELECT
                COUNT(*) as count,
                AVG(COALESCE(LENGTH(markdown_content), 0)) as avg_markdown,
                COUNT(CASE WHEN markdown_content IS NOT NULL THEN 1 END) as with_markdown
            FROM newsletter_summaries
        """)
        ).fetchone()

        if summary_stats and summary_stats.count > 0:
            print(f"  Summaries ({summary_stats.count} rows):")
            print(f"    with markdown_content: {summary_stats.with_markdown}")
            print(f"    avg markdown_content:  {summary_stats.avg_markdown:,.0f} bytes")

        # Index usage
        print("\n--- Index Usage Statistics ---")
        try:
            result = db.execute(
                text("""
                SELECT
                    schemaname,
                    relname as table_name,
                    indexrelname as index_name,
                    idx_scan as scans,
                    idx_tup_read as tuples_read,
                    idx_tup_fetch as tuples_fetched
                FROM pg_stat_user_indexes
                WHERE relname IN ('contents', 'newsletters', 'newsletter_summaries')
                ORDER BY idx_scan DESC
                LIMIT 15
            """)
            )
            print(f"  {'Index Name':<45} {'Scans':>10} {'Reads':>10}")
            print("  " + "-" * 70)
            for row in result:
                print(f"  {row.index_name:<45} {row.scans:>10} {row.tuples_read:>10}")
        except Exception as e:
            print(f"  (Index stats not available: {e})")


def run_api_benchmarks(iterations: int = 5):
    """Benchmark API endpoint response times."""
    import requests

    print("\n" + "=" * 60)
    print("API ENDPOINT BENCHMARKS")
    print("=" * 60)

    base_url = "http://localhost:8000/api/v1"

    endpoints = [
        ("GET /contents", f"{base_url}/contents?limit=20"),
        ("GET /contents (filtered)", f"{base_url}/contents?status=completed&limit=20"),
        ("GET /summaries", f"{base_url}/summaries?limit=20"),
        ("GET /digests", f"{base_url}/digests?limit=10"),
        ("GET /newsletters (deprecated)", f"{base_url}/newsletters?limit=20"),
    ]

    print(f"\n{'Endpoint':<35} {'Mean':>10} {'Min':>10} {'Max':>10}")
    print("-" * 70)

    for name, url in endpoints:
        times = []
        for _ in range(iterations):
            try:
                start = time.perf_counter()
                resp = requests.get(url, timeout=10)
                end = time.perf_counter()
                if resp.status_code == 200:
                    times.append((end - start) * 1000)
            except Exception:
                pass

        if times:
            mean = statistics.mean(times)
            print(f"{name:<35} {mean:>8.1f}ms {min(times):>8.1f}ms {max(times):>8.1f}ms")
        else:
            print(f"{name:<35} {'FAILED':>10}")


def main():
    parser = argparse.ArgumentParser(description="Performance testing for Content model")
    parser.add_argument("--iterations", "-n", type=int, default=10, help="Number of iterations per test")
    parser.add_argument("--skip-api", action="store_true", help="Skip API benchmarks")
    args = parser.parse_args()

    print("=" * 60)
    print("CONTENT MODEL PERFORMANCE TEST")
    print(f"Iterations: {args.iterations}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    run_query_benchmarks(args.iterations)
    run_storage_analysis()

    if not args.skip_api:
        run_api_benchmarks(args.iterations)

    print("\n" + "=" * 60)
    print("PERFORMANCE TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
