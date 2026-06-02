"""
Pydantic payload schemas for the chain system.
All chain payloads must conform to one of these schemas.
Schema version is embedded in every model.
"""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field, model_validator


class BasePayload(BaseModel):
    """Base for all chain payloads."""
    model_config = {"extra": "allow"}  # allow additional fields

    chain_id: str
    step_id: str | None = None
    schema_version: str = "v1"

    def to_db_dict(self) -> dict:
        """Serialize for DB storage — all fields as JSON-safe dict."""
        return self.model_dump(mode="json")

    @classmethod
    def from_db_dict(cls, data: dict) -> "BasePayload":
        return cls(**data)


class RFDFrame(BaseModel):
    moment: str = ""
    surprise: str = ""
    struggle: str = ""
    lesson: str = ""
    next: str = ""

    def is_complete(self) -> bool:
        return all([self.moment, self.surprise,
                    self.struggle, self.lesson, self.next])


class TextDraftPayload(BasePayload):
    """text/draft — blog post or written content in progress."""
    payload_type: str = "text/draft"
    title: str
    body: str
    layer: str  # technical | project | personal | business | content
    word_count: int | None = None
    tags: list[str] = Field(default_factory=list)
    rfd_frame: RFDFrame | None = None

    @model_validator(mode="after")
    def compute_word_count(self) -> "TextDraftPayload":
        if self.word_count is None and self.body:
            self.word_count = len(self.body.split())
        return self


class DataStatsPayload(BasePayload):
    """data/stats — metrics snapshot from any data source."""
    payload_type: str = "data/stats"
    source: str
    captured_at: str
    values: dict[str, Any]
    delta: dict[str, Any] | None = None
    threshold_flags: list[str] = Field(default_factory=list)


class DataResearchPayload(BasePayload):
    """data/research — web research results."""
    payload_type: str = "data/research"
    query: str
    sources: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    captured_at: str
    confidence: float | None = None


class ActionApprovalPayload(BasePayload):
    """action/approval — waiting for human decision."""
    payload_type: str = "action/approval"
    prompt: str
    payload_ref: str
    expires_at: str
    options: list[str] = Field(default_factory=lambda: ["approve", "reject"])
    default: str | None = None
    response: str | None = None


class AgentDecisionPayload(BasePayload):
    """agent/decision — output of an agent_step."""
    payload_type: str = "agent/decision"
    action: str  # call_tool | llm_call | complete | loop_back | fail
    target: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    reasoning: str = ""


# Registry mapping payload_type string to Pydantic class
PAYLOAD_SCHEMAS: dict[str, type[BasePayload]] = {
    "text/draft":       TextDraftPayload,
    "data/stats":       DataStatsPayload,
    "data/research":    DataResearchPayload,
    "action/approval":  ActionApprovalPayload,
    "agent/decision":   AgentDecisionPayload,
}


def validate_payload(payload_type: str, data: dict) -> BasePayload:
    """
    Validate and return a typed payload.
    Falls back to BasePayload if type not in registry.
    Never raises on unknown types — unknown is not invalid.
    """
    schema_cls = PAYLOAD_SCHEMAS.get(payload_type, BasePayload)
    return schema_cls(**data)
