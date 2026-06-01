"""Monitoring prompt templates."""

from dataclasses import dataclass
from .base import BasePrompt


@dataclass
class RedditMonitorPrompt(BasePrompt):
    keywords: list[str]
    subreddits: list[str]
    hours: int = 24

    def render(self) -> str:
        subs = ", ".join(self.subreddits)
        kws = ", ".join(self.keywords)
        return (
            f"Search {subs} for mentions of {kws} "
            f"in the last {self.hours}h. "
            "If found: save as memory, mark URGENT. "
            "Report what you found."
        )


@dataclass
class PyPIMonitorPrompt(BasePrompt):
    package: str
    baseline_key: str
    spike_threshold_pct: float = 20.0

    def render(self) -> str:
        return (
            f"Check download stats for {self.package} on PyPI. "
            f"Compare to baseline in memory key '{self.baseline_key}'. "
            f"If downloads increased >{self.spike_threshold_pct}% "
            "day-over-day: mark URGENT. "
            f"Save current counts to memory as '{self.package} stats YYYY-MM-DD'. "
            "Report what you found."
        )


@dataclass
class ItchMonitorPrompt(BasePrompt):
    game: str = "VoidDrift"
    compare_yesterday: bool = True

    def render(self) -> str:
        compare = (
            " Compare to yesterday's memory if available."
            if self.compare_yesterday else ""
        )
        return (
            f"Check itch.io stats for {self.game}."
            f"{compare} "
            "Note any significant changes in views, plays, or collections. "
            f"Save as memory '{self.game} itch stats YYYY-MM-DD'."
        )
