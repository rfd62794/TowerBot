"""Analysis prompt templates."""

from dataclasses import dataclass
from .base import BasePrompt


@dataclass
class MetricSnapshotPrompt(BasePrompt):
    sources: list[str]
    label: str = "Daily metrics"
    compare_yesterday: bool = True

    def render(self) -> str:
        src = ", ".join(self.sources)
        compare = (
            " Compare to yesterday's memory snapshot."
            if self.compare_yesterday else ""
        )
        return (
            f"Pull metrics from: {src}.{compare} "
            f"Save as memory '{self.label} YYYY-MM-DD' with key numbers. "
            "Note any significant change."
        )


@dataclass
class CommitSummaryPrompt(BasePrompt):
    days: int = 7
    repo: str = None

    def render(self) -> str:
        target = self.repo or "the PrivyBot repo"
        return (
            f"Get recent commits from {target} "
            f"for the last {self.days} days. "
            "Summarize what was built, what changed, "
            "and what it means for the next session. "
            "Save summary to memory."
        )


@dataclass
class YouTubeAnalysisPrompt(BasePrompt):
    days: int = 28
    include_top_videos: bool = True
    include_retention: bool = False

    def render(self) -> str:
        parts = [
            f"Pull YouTube channel stats for the last {self.days} days."
        ]
        if self.include_top_videos:
            parts.append("Get top 5 videos by views.")
        if self.include_retention:
            parts.append(
                "Get retention curve for the top video."
            )
        parts.append(
            "Summarize performance and identify one actionable insight."
        )
        return " ".join(parts)
