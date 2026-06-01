"""Generic delegation prompt templates."""

from dataclasses import dataclass
from .base import BasePrompt


@dataclass
class InvestigatePrompt(BasePrompt):
    question: str
    context: str = None
    return_format: str = "summary"

    def render(self) -> str:
        ctx = f"\nContext: {self.context}" if self.context else ""
        fmt_map = {
            "summary": "Return a 2-3 sentence summary.",
            "bullets": "Return 3-5 bullet points.",
            "data": "Return structured data with key numbers.",
        }
        fmt = fmt_map.get(self.return_format, "Return a summary.")
        return f"Investigate: {self.question}{ctx}\n{fmt}"


@dataclass
class PlanningPrompt(BasePrompt):
    objective: str
    constraints: list[str] = None
    output: str = "directive"

    def render(self) -> str:
        constraints_text = ""
        if self.constraints:
            constraints_text = (
                "\nConstraints: " + "; ".join(self.constraints)
            )
        out_map = {
            "directive": "Produce a complete RFD directive.",
            "summary": "Produce a 3-sentence plan summary.",
            "action_list": "Produce an ordered action list.",
        }
        out = out_map.get(self.output, "Produce a plan.")
        return (
            f"Plan: {self.objective}{constraints_text}\n{out}"
        )
