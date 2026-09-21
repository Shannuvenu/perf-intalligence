"""
Recommendation orchestration - the final stage of the pipeline described in
the product spec:

  stabilized metrics + runs -> evidence extraction -> rule-based candidate
  signals -> LLM synthesis -> Pydantic validation -> priority assignment ->
  persistence as an LlmRecommendation row.

This is intentionally the only place that calls the LLM synthesis provider
and the priority engine together, so API routes stay thin.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.llm_recommendation import LlmRecommendation
from app.models.psi_run import PsiRun
from app.models.stabilized_metric import StabilizedMetric
from app.schemas.recommendation import LlmRecommendationSet
from app.services.evidence.extractor import extract_evidence
from app.services.llm.base import LlmProviderError
from app.services.llm.client import get_llm_provider
from app.services.llm.prompts import PROMPT_VERSION
from app.services.recommendations.candidate_signals import generate_candidate_signals
from app.services.recommendations.priority import assign_priorities, overall_priority_rank
from app.services.stabilization.service import InsufficientRunsError, latest_stabilized

logger = logging.getLogger(__name__)


class NoStabilizedDataError(Exception):
    pass


async def generate_recommendations(
    db: Session, url_id: int, settings: Settings | None = None
) -> LlmRecommendation:
    settings = settings or get_settings()

    stabilized = latest_stabilized(db, url_id)
    if stabilized is None:
        raise NoStabilizedDataError(
            f"url_id={url_id} has no stabilized metrics yet. Run POST /api/urls/{url_id}/stabilize first."
        )

    window_run_stmt = (
        select(PsiRun)
        .where(PsiRun.url_id == url_id, PsiRun.run_status == "success",
               PsiRun.run_timestamp >= stabilized.window_start, PsiRun.run_timestamp <= stabilized.window_end)
        .order_by(PsiRun.run_timestamp.asc())
    )
    runs = list(db.scalars(window_run_stmt))
    if not runs:
        raise NoStabilizedDataError(f"No successful runs found in the stabilized window for url_id={url_id}.")

    evidence = extract_evidence(runs, stabilized, settings)
    candidates = generate_candidate_signals(evidence)

    provider = get_llm_provider(settings)
    try:
        result: LlmRecommendationSet = await provider.synthesize(evidence, candidates)
        validation_status = _validate(result, settings)
    except LlmProviderError as exc:
        logger.warning("LLM synthesis failed for url_id=%s: %s", url_id, exc)
        result = LlmRecommendationSet(recommendations=[], insufficient_evidence_note=str(exc))
        validation_status = "invalid"

    ranked_items = assign_priorities(result.recommendations, settings)

    record = LlmRecommendation(
        url_id=url_id,
        generated_at=datetime.now(timezone.utc),
        root_cause_groups=[item.model_dump() for item in ranked_items],
        priority_rank=overall_priority_rank(ranked_items),
        source_run_ids=[r.run_id for r in runs],
        model_name=provider.model_name,
        prompt_version=PROMPT_VERSION,
        validation_status=validation_status,
        insufficient_evidence_note=result.insufficient_evidence_note,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _validate(result: LlmRecommendationSet, settings: Settings) -> str:
    """Compute validation_status ourselves - never trust the model to grade
    its own homework (product spec section 12)."""
    if not result.recommendations:
        return "valid" if result.insufficient_evidence_note else "needs_review"

    for item in result.recommendations:
        if not item.evidence:
            return "invalid"  # schema should already prevent this, belt & suspenders
    low_confidence = any(item.confidence < settings.RECOMMENDATION_NEEDS_REVIEW_CONFIDENCE
                          for item in result.recommendations)
    return "needs_review" if low_confidence else "valid"
