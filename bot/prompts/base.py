"""Base prompt contract for all PrivyBot prompt templates."""

from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class BasePrompt(ABC):
    """
    Base class for all PrivyBot prompt templates.
    Dataclass now — migrate to Pydantic(BaseModel) later
    by swapping @dataclass for class X(BaseModel).
    render() contract stays identical.
    """

    @abstractmethod
    def render(self) -> str:
        """Return the full prompt string for agent.respond()."""
        ...

    def __str__(self) -> str:
        return self.render()
