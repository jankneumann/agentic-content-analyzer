"""Durable application workflows shared by every transport."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.workflows.audio_digest import AudioDigestWorkflow
    from src.workflows.digest import DigestWorkflow
    from src.workflows.podcast_audio import PodcastAudioWorkflow
    from src.workflows.podcast_script import PodcastScriptWorkflow
    from src.workflows.summarization import SummarizationWorkflow
    from src.workflows.theme_analysis import ThemeAnalysisWorkflow

_WORKFLOW_EXPORTS = {
    "AudioDigestWorkflow": "src.workflows.audio_digest",
    "DigestWorkflow": "src.workflows.digest",
    "PodcastAudioWorkflow": "src.workflows.podcast_audio",
    "PodcastScriptWorkflow": "src.workflows.podcast_script",
    "SummarizationWorkflow": "src.workflows.summarization",
    "ThemeAnalysisWorkflow": "src.workflows.theme_analysis",
}

__all__ = [
    "AudioDigestWorkflow",
    "DigestWorkflow",
    "PodcastAudioWorkflow",
    "PodcastScriptWorkflow",
    "SummarizationWorkflow",
    "ThemeAnalysisWorkflow",
]


def __getattr__(name: str) -> Any:
    """Load workflow exports on first use without creating package import cycles."""
    module_name = _WORKFLOW_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
