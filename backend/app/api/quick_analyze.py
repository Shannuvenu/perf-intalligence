"""
Quick Analyze: paste a raw PSI/Lighthouse JSON report (e.g. from an email,
or a report run outside this tool) and get the same evidence-backed, ranked
fix list the rest of the app produces - without adding a URL, without
running PSI, without needing multiple runs to stabilize.

This deliberately reuses the exact same pipeline stages as the monitored-URL
flow (normalize -> evidence -> candidate signals -> LLM synthesis) so the
two paths never drift into different logic. The only difference: since
there's only one report, "stabilization" is a single-run window (run_count=1,
no variability data) built in memory - nothing is written to the database.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.models.psi_run import PsiRun
from app.models.stabilized_metric import StabilizedMetric
from app.schemas.recommendation import RecommendationItem
from app.services.evidence.extractor import extract_evidence
from app.services.llm.base import LlmProviderError
from app.services.llm.client import get_llm_provider
from app.services.psi.normalizer import PsiParsingError, normalize_psi_result
from app.services.recommendations.candidate_signals import generate_candidate_signals
from app.services.recommendations.priority import assign_priorities

router = APIRouter(prefix="/api/quick-analyze", tags=["quick-analyze"])


class QuickAnalyzeResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    recommendations: list[RecommendationItem]
    model_name: str
    note: str | None = None


@router.post("", response_model=QuickAnalyzeResponse)
async def quick_analyze(report: dict = Body(...)) -> QuickAnalyzeResponse:
    try:
        normalized = normalize_psi_result(report)
    except PsiParsingError as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse this as a PSI/Lighthouse report: {exc}") from exc

    now = datetime.now(timezone.utc)

    # In-memory only - never added to a DB session, so nothing is persisted.
    fake_run = PsiRun(
        run_id=0, url_id=0, run_timestamp=now, strategy="mobile",
        category_scores=normalized["category_scores"],
        core_web_vitals=normalized["core_web_vitals"],
        normalized_audits=normalized["normalized_audits"],
        run_status="success",
    )
    median_metrics = dict(normalized["core_web_vitals"])
    median_metrics["performance_score"] = normalized["category_scores"].get("performance")
    median_metrics["accessibility_score"] = normalized["category_scores"].get("accessibility")
    fake_stabilized = StabilizedMetric(
        url_id=0, window_start=now, window_end=now, run_count=1,
        median_metrics=median_metrics, variability_metrics={}, flagged=False,
    )

    settings = get_settings()
    evidence = extract_evidence([fake_run], fake_stabilized, settings)
    candidates = generate_candidate_signals(evidence)

    provider = get_llm_provider(settings)
    try:
        result = await provider.synthesize(evidence, candidates)
    except LlmProviderError as exc:
        raise HTTPException(status_code=502, detail=f"LLM synthesis failed: {exc}") from exc

    ranked: list[RecommendationItem] = assign_priorities(result.recommendations, settings)
    top5 = ranked[:5]

    return QuickAnalyzeResponse(
        recommendations=top5,
        model_name=provider.model_name,
        note=result.insufficient_evidence_note if not top5 else None,
    )