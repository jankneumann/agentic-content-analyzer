"""Proactive task definitions — the actual tasks that schedules trigger.

Each entry maps a task name to its default configuration. These serve
as templates when the scheduler enqueues work: the schedule's ``persona``,
``output``, and ``sources`` fields are layered on top at enqueue time.
"""

PROACTIVE_TASKS: dict[str, dict[str, str]] = {
    "scan_sources": {
        "task_type": "ingestion",
        "prompt": "Scan all enabled sources for new content and ingest any new items found.",
    },
    "trend_detection": {
        "task_type": "analysis",
        "prompt": "Analyze recent content to detect emerging trends, anomalies, and patterns.",
    },
    "weekly_synthesis": {
        "task_type": "synthesis",
        "prompt": "Synthesize the past week's content into key insights and trend summaries.",
    },
    "knowledge_maintenance": {
        "task_type": "maintenance",
        "prompt": "Perform knowledge graph maintenance: prune stale entries, merge duplicates.",
    },
    "cross_theme_discovery": {
        "task_type": "analysis",
        "prompt": "Discover connections between themes across the past 30 days of content.",
    },
}
