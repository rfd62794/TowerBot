"""Prompt module — typed prompt dataclasses for PrivyBot."""

from .base import BasePrompt
from .monitoring import RedditMonitorPrompt, PyPIMonitorPrompt, ItchMonitorPrompt
from .analysis import MetricSnapshotPrompt, CommitSummaryPrompt, YouTubeAnalysisPrompt
from .content import BlogDraftPrompt, LinkedInDraftPrompt, RedditPostDraftPrompt
from .delegation import InvestigatePrompt, PlanningPrompt

__all__ = [
    "BasePrompt",
    "RedditMonitorPrompt",
    "PyPIMonitorPrompt",
    "ItchMonitorPrompt",
    "MetricSnapshotPrompt",
    "CommitSummaryPrompt",
    "YouTubeAnalysisPrompt",
    "BlogDraftPrompt",
    "LinkedInDraftPrompt",
    "RedditPostDraftPrompt",
    "InvestigatePrompt",
    "PlanningPrompt",
]
