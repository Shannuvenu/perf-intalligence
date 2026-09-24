"""
Shared tail of the recommendation pipeline: evidence + candidates -> LLM
synthesis -> hard server-side validation -> deterministic priority.

Used by BOTH the monitored-URL flow (recommendations/service.py) and Quick
Analyze (api/quick_analyze.py) so the two never drift into different logic
(product spec section 18) - there is exactly one place that calls the LLM
provider and decides what survives validation.
"""
import logging

from app.core.config import Settings, get_settings
from app.schemas.recommendation import RecommendationItem
from app.services.evidence.models import Evidence
from app.services.llm.base import LlmProviderError
from app.services.llm.client import get_llm_provider
from app.services.recommendations.candidate_signals import CandidateSignal
from app.services.recommendations.priority import assign_priorities
from app.services.recommendations.validation import validate_and_resolve

logger = logging.getLogger(__name__)


async def run_recommendation_pipeline(
    evidence: list[Evidence],
    candidates: list[CandidateSignal],
    page_metrics: dict | None = None,
    settings: Settings | None = None,
):
    """Returns (ranked_items, validation_status, insufficient_evidence_note, provider)."""
    settings = settings or get_settings()
    provider = get_llm_provider(settings)

    try:
        result = await provider.synthesize(evidence, candidates, page_metrics)
    except LlmProviderError as exc:
        # A genuine technical failure (network/parsing/schema) - distinct
        # from "the LLM answered but every recommendation failed hard
        # validation", which is a valid, successful empty result. Callers
        # that need to tell the two apart can check for this exact status.
        logger.warning("LLM synthesis failed: %s", exc)
        return [], "invalid", str(exc), provider

    items, status, note = validate_and_resolve(result, evidence, candidates, settings)
    ranked: list[RecommendationItem] = assign_priorities(items, settings)
    return ranked, status, note, provider
