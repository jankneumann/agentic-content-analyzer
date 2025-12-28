"""CLI script to query the Graphiti knowledge graph."""

import argparse
import asyncio
import json
from datetime import datetime, timedelta

from src.storage.graphiti_client import GraphitiClient
from src.utils.logging import get_logger, setup_logging

# Setup logging
setup_logging()
logger = get_logger(__name__)


async def search_concepts(query: str, limit: int = 10) -> None:
    """
    Search for concepts in the knowledge graph.

    Args:
        query: Search query
        limit: Maximum number of results
    """
    async with GraphitiClient() as graphiti:
        logger.info(f"Searching for: {query}")
        results = await graphiti.search_related_concepts(query, limit=limit)

        if not results:
            print(f"\nNo results found for: {query}")
            return

        print(f"\n{'='*80}")
        print(f"Search results for: {query}")
        print(f"{'='*80}\n")

        for i, result in enumerate(results, 1):
            print(f"{i}. {json.dumps(result, indent=2, default=str)}\n")


async def get_temporal_trends(
    concepts: list[str],
    days_back: int = 30,
) -> None:
    """
    Get temporal trends for concepts.

    Args:
        concepts: List of concepts to track
        days_back: How many days back to search
    """
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)

    async with GraphitiClient() as graphiti:
        logger.info(
            f"Getting temporal context for {len(concepts)} concepts "
            f"over {days_back} days"
        )
        results = await graphiti.get_temporal_context(
            concepts=concepts,
            start_date=start_date,
            end_date=end_date,
        )

        if not results:
            print(f"\nNo temporal data found for: {', '.join(concepts)}")
            return

        print(f"\n{'='*80}")
        print(f"Temporal trends for: {', '.join(concepts)}")
        print(f"Date range: {start_date.date()} to {end_date.date()}")
        print(f"{'='*80}\n")

        for i, result in enumerate(results, 1):
            print(f"{i}. {json.dumps(result, indent=2, default=str)}\n")


async def main() -> None:
    """Run knowledge graph queries."""
    parser = argparse.ArgumentParser(
        description="Query the Graphiti knowledge graph"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="Search query for concepts and entities",
    )
    parser.add_argument(
        "--temporal",
        nargs="+",
        help="Track temporal trends for concepts (space-separated list)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to look back for temporal queries (default: 30)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of results (default: 10)",
    )

    args = parser.parse_args()

    try:
        if args.query:
            # Search for concepts
            await search_concepts(args.query, limit=args.limit)

        elif args.temporal:
            # Get temporal trends
            await get_temporal_trends(args.temporal, days_back=args.days)

        else:
            print("Error: Must specify either --query or --temporal")
            parser.print_help()
            return

    except Exception as e:
        logger.error(f"Query failed: {e}")
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return


if __name__ == "__main__":
    asyncio.run(main())
