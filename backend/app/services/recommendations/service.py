"""
Recommendation orchestration - the final stage of the pipeline described in
the product spec:

  stabilized metrics + runs -> evidence extraction -> rule-based candidate
  signals -> LLM synthesis -> hard server-side validation -> priority
  assignment -> persistence as an LlmRecommendation row.

The actual LLM-call + validation + priority step is shared with Quick
Analyze via recommendations/pipeline.py, so the two entry points can never
drift into different logic.
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.llm_recommendation import LlmRecommendation
from app.models.psi_run import PsiRun
from app.models.stabilized_metric import StabilizedMetric
from app.services.evidence.extractor import extract_evidence
from app.services.llm.prompts import PROMPT_VERSION
from app.services.recommendations.candidate_signals import generate_candidate_signals
from app.services.recommendations.pipeline import run_recommendation_pipeline
from app.services.recommendations.priority import overall_priority_rank
from app.services.stabilization.service import latest_stabilized

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

    ranked_items, validation_status, note, provider = await run_recommendation_pipeline(
        evidence, candidates, page_metrics=stabilized.median_metrics, settings=settings,
    )

    record = LlmRecommendation(
        url_id=url_id,
        generated_at=datetime.now(timezone.utc),
        root_cause_groups=[item.model_dump() for item in ranked_items],
        priority_rank=overall_priority_rank(ranked_items),
        source_run_ids=[r.run_id for r in runs],
        model_name=provider.model_name,
        prompt_version=PROMPT_VERSION,
        validation_status=validation_status,
        insufficient_evidence_note=note,
        created_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record
