"""Content creation prompt templates."""

from dataclasses import dataclass
from .base import BasePrompt


@dataclass
class BlogDraftPrompt(BasePrompt):
    topic: str
    voice: str = "RFD Content Frame"
    stage: str = "full_draft"

    def render(self) -> str:
        if self.stage == "q1_only":
            return (
                f"For the topic '{self.topic}': "
                "Write Question 1 of the five-question extraction — "
                "the specific scene prompt Robert needs to answer. "
                f"Save as memory 'Q1 ready: {self.topic}'."
            )
        if self.stage == "skeleton":
            return (
                f"Build a blog post skeleton for '{self.topic}' "
                f"using {self.voice}. "
                "Include: MOMENT, SURPRISE, STRUGGLE, LESSON, NEXT sections. "
                "Each section: write the prompt question Robert needs to answer "
                "plus relevant research context. "
                "Call create_blog_draft() with the skeleton."
            )
        return (
            f"Write a complete blog post about '{self.topic}' "
            f"in Robert's voice using {self.voice}. "
            "Pull context from memory and recent data tools. "
            "MOMENT: specific scene, stream of consciousness. "
            "SURPRISE: one sentence. "
            "STRUGGLE: honest friction. "
            "LESSON: distilled. "
            "NEXT: forward motion. "
            "Call create_blog_draft() with the full post."
        )


@dataclass
class LinkedInDraftPrompt(BasePrompt):
    topic: str
    angle: str = "developer audience"
    hook_style: str = "specific moment"

    def render(self) -> str:
        return (
            f"Draft a LinkedIn post about '{self.topic}' "
            f"for a {self.angle}. "
            f"Hook style: {self.hook_style}. "
            "No generic motivational language. "
            "Specific, honest, useful. "
            f"Save draft to memory as 'LinkedIn draft: {self.topic}'."
        )


@dataclass
class RedditPostDraftPrompt(BasePrompt):
    subreddit: str
    topic: str
    post_type: str = "discussion"

    def render(self) -> str:
        return (
            f"Draft a {self.post_type} post for {self.subreddit} "
            f"about '{self.topic}'. "
            "Authentic voice, no promotion. "
            "Genuine contribution to the community. "
            f"Save draft to memory as 'Reddit draft: {self.topic}'."
        )
