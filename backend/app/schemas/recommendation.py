"""
This is the most important schema in the app: it's the contract the LLM's
output must satisfy before we ever show it to a developer as a "recommendation".

Design principles (per product spec sections 6/7/11/12):
  - The LLM does NOT invent a root cause. It must pick a `candidate_id` from
    the closed set the deterministic rule engine generated for this run, and
    reference evidence ONLY by `evidence_refs` (stable Evidence ids) - never
    by restating claims as free text. Server-side validation
    (recommendations/validation.py) rejects anything that doesn't check out:
    an unknown candidate_id, an evidence_ref that doesn't exist, or an
    evidence_ref that doesn't actually belong to that candidate.
  - `evidence` and `resources` and `affected_audits` below are SERVER-resolved
    display fields, filled in after validation from the real Evidence objects
    the ids point to - the LLM never supplies these directly, so there is no
    way for it to fabricate an evidence string that sounds plausible but was
    never checked.
  - impact / ease_of_fix / confidence are the only model-provided inputs to
    priority, and confidence is additionally capped server-side by the
    strength of the evidence actually referenced - see
    app/services/recommendations/priority.py and validation.py for why.
  - validation_status is computed by us, not by the model.
"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.recommendations.candidate_signals import KNOWN_CANDIDATE_IDS

Impact = Literal["high", "medium", "low"]
Ease = Literal["easy", "medium", "hard"]
ValidationStatus = Literal["valid", "invalid", "needs_review"]


class RecommendationItem(BaseModel):
    # What the LLM actually provides:
    candidate_id: str = Field(..., min_length=1, max_length=64)
    summary: str = Field(..., min_length=10, max_length=1000)
    problem_explanation: str | None = Field(default=None, max_length=3000)
    user_impact: str | None = Field(default=None, max_length=2000)
    fix_steps: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(..., min_length=1)
    impact: Impact
    ease_of_fix: Ease
    confidence: float = Field(..., ge=0.0, le=1.0)
    suggested_fix: str = Field(..., min_length=10, max_length=2000)

    # Server-resolved display fields - populated by
    # recommendations/validation.py from the real Evidence objects behind
    # evidence_refs, never trusted from the LLM directly. Left empty until
    # validation runs.
    root_cause: str = Field(default="")
    evidence: list[str] = Field(default_factory=list)
    resources: list[str] = Field(default_factory=list)
    affected_audits: list[str] = Field(default_factory=list)

    # Filled in by our priority engine after validation - never trusted
    # from the model directly.
    priority: str | None = None

    @field_validator("candidate_id")
    @classmethod
    def candidate_id_is_known(cls, v: str) -> str:
        if v not in KNOWN_CANDIDATE_IDS:
            raise ValueError(f"candidate_id '{v}' is not one of the deterministic candidates")
        return v

    @field_validator("evidence_refs")
    @classmethod
    def evidence_refs_not_blank(cls, v: list[str]) -> list[str]:
        cleaned = [e.strip() for e in v if e and e.strip()]
        if not cleaned:
            raise ValueError("evidence_refs must contain at least one non-empty entry")
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
    insufficient_evidence_note: str | None = None
