"""
This is the most important schema in the app: it's the contract the LLM's
output must satisfy before we ever show it to a developer as a "recommendation".

Design principles (per product spec section 11/12):
  - Every recommendation MUST carry evidence strings - free-form claims with
    no evidence attached are rejected outright.
  - impact / ease_of_fix / confidence are the only inputs to priority. The
    LLM does not get to assign its own priority - see
    app/services/recommendations/priority.py for why.
  - validation_status is computed by us, not by the model.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Impact = Literal["high", "medium", "low"]
Ease = Literal["easy", "medium", "hard"]
ValidationStatus = Literal["valid", "invalid", "needs_review"]


class RecommendationItem(BaseModel):
    root_cause: str = Field(..., min_length=3, max_length=200)
    summary: str = Field(..., min_length=10, max_length=1000)
    evidence: list[str] = Field(..., min_length=1)
    affected_audits: list[str] = Field(default_factory=list)
    impact: Impact
    ease_of_fix: Ease
    confidence: float = Field(..., ge=0.0, le=1.0)
    suggested_fix: str = Field(..., min_length=10, max_length=2000)

    # Filled in by our priority engine after the LLM responds - never trusted
    # from the model directly.
    priority: str | None = None

    @field_validator("evidence")
    @classmethod
    def evidence_entries_not_blank(cls, v: list[str]) -> list[str]:
        cleaned = [e.strip() for e in v if e and e.strip()]
        if not cleaned:
            raise ValueError("evidence must contain at least one non-empty entry")
        return cleaned


class LlmRecommendationSet(BaseModel):
    """The raw structured shape we ask the LLM (or mock) to produce."""

    recommendations: list[RecommendationItem]
    insufficient_evidence_note: str | None = None


class RecommendationRead(BaseModel):
    model_config = {"protected_namespaces": ()}

    recommendation_id: int
    url_id: int
    generated_at: str
    root_cause_groups: list[RecommendationItem]
    priority_rank: str
    source_run_ids: list[int]
    model_name: str
    prompt_version: str
    validation_status: ValidationStatus
