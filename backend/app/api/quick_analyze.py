"""
Quick Analyze: two entry points that skip the multi-tenant Sites/URLs setup
and produce the same evidence-backed, ranked fix list the rest of the app
produces.

1. quick_analyze()      - POST /api/quick-analyze
   Paste a raw PSI/Lighthouse JSON report (e.g. from an email, or a report
   run outside this tool). No PSI call is made here.

2. quick_analyze_url()  - POST /api/quick-analyze/url
   Paste a URL. This calls the real (or mock) PSI provider once, right now,
   for that URL - no Site/Url record required. This is the "Paste URL ->
   Run PageSpeed" entry point.

Both deliberately reuse the exact same pipeline stages as the monitored-URL
flow (normalize -> evidence -> candidate signals -> LLM synthesis) so none
of these paths ever drift into different logic. In both cases "stabilization"
is a single-run window (run_count=1, no variability data) built in memory -
nothing is written to the database or to raw storage.
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.core.config import get_settings
from app.models.psi_run import PsiRun
from app.models.stabilized_metric import StabilizedMetric
from app.schemas.recommendation import RecommendationItem
from app.services.evidence.extractor import extract_evidence
from app.services.llm.base import LlmProviderError
from app.services.llm.client import get_llm_provider
from app.services.psi.base import PsiProviderError
from app.services.psi.client import get_psi_provider
from app.services.psi.normalizer import PsiParsingError, normalize_psi_result
from app.services.recommendations.candidate_signals import generate_candidate_signals
from app.services.recommendations.priority import assign_priorities

router = APIRouter(prefix="/api/quick-analyze", tags=["quick-analyze"])


class QuickAnalyzeResponse(BaseModel):
    model_config = {"protected_namespaces": ()}

    recommendations: list[RecommendationItem]
    model_name: str
    note: str | None = None
    # Populated for both entry points so the frontend can show metric cards
    # (Performance/Accessibility/LCP/CLS/...) alongside the recommendations,
    # not just the fix list.
    category_scores: dict[str, float | None] | None = None
    core_web_vitals: dict[str, float | None] | None = None


class QuickUrlAnalyzeRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    strategy: Literal["mobile", "desktop"] | None = None

    @field_validator("url")
    @classmethod
    def must_be_http_url(cls, v: str) -> str:
        if not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("url must start with http:// or https://")
        return v


async def _analyze_normalized(normalized: dict, strategy: str) -> QuickAnalyzeResponse:
    """Shared tail of both entry points: build an in-memory single-run
    'stabilized' window from an already-normalized PSI result, then run the
    evidence -> candidate signals -> LLM pipeline exactly as the
    monitored-URL flow does (see services/recommendations/service.py)."""
    now = datetime.now(timezone.utc)

    fake_run = PsiRun(
        run_id=0, url_id=0, run_timestamp=now, strategy=strategy,
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
        category_scores=normalized["category_scores"],
        core_web_vitals=normalized["core_web_vitals"],
    )


@router.post("", response_model=QuickAnalyzeResponse)
async def quick_analyze(report: dict = Body(...)) -> QuickAnalyzeResponse:
    try:
        normalized = normalize_psi_result(report)
    except PsiParsingError as exc:
        raise HTTPException(status_code=422, detail=f"Could not parse this as a PSI/Lighthouse report: {exc}") from exc
    return await _analyze_normalized(normalized, strategy="mobile")


@router.post("/url", response_model=QuickAnalyzeResponse)
async def quick_analyze_url(payload: QuickUrlAnalyzeRequest) -> QuickAnalyzeResponse:
    """The 'paste a URL, click Run PageSpeed' entry point."""
    settings = get_settings()
    strategy = payload.strategy or settings.PSI_STRATEGY
    provider = get_psi_provider(settings)

    try:
        raw = await provider.run_psi(payload.url, strategy)
        normalized = normalize_psi_result(raw)
    except PsiProviderError as exc:
        raise HTTPException(status_code=502, detail=f"PageSpeed run failed: {exc}") from exc
    except PsiParsingError as exc:
        raise HTTPException(status_code=502, detail=f"PageSpeed returned an unparsable report: {exc}") from exc

    return await _analyze_normalized(normalized, strategy=strategy)