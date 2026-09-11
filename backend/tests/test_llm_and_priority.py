import pytest

from app.schemas.recommendation import RecommendationItem
from app.services.evidence.models import Evidence
from app.services.llm.base import LlmProviderError
from app.services.llm.mock_llm import MockLlmProvider
from app.services.recommendations.candidate_signals import CandidateSignal
from app.services.recommendations.priority import (
    assign_priorities,
    compute_priority_score,
    overall_priority_rank,
    score_to_rank,
)
from app.services.recommendations.service import _validate
from app.schemas.recommendation import LlmRecommendationSet


@pytest.mark.asyncio
async def test_mock_llm_synthesizes_from_candidates():
    ev = Evidence(metric="tbt_ms", description="Median TBT is 620ms.", value=620, severity="critical", tags=["tbt"])
    candidate = CandidateSignal(
        root_cause_hypothesis="Heavy third-party/ad-related execution",
        supporting_evidence=[ev],
        strength=0.9,
    )
    provider = MockLlmProvider()
    result = await provider.synthesize([ev], [candidate])

    assert len(result.recommendations) == 1
    rec = result.recommendations[0]
    assert rec.root_cause == "Heavy third-party/ad-related execution"
    assert ev.description in rec.evidence
    assert 0.0 <= rec.confidence <= 1.0


@pytest.mark.asyncio
async def test_mock_llm_with_no_candidates_returns_empty_with_note():
    provider = MockLlmProvider()
    result = await provider.synthesize([], [])
    assert result.recommendations == []
    assert result.insufficient_evidence_note is not None


def test_priority_score_and_rank_boundaries():
    high_conf_item = RecommendationItem(
        root_cause="XYZ issue", summary="x" * 20, evidence=["e"], impact="high", ease_of_fix="easy",
        confidence=0.95, suggested_fix="y" * 20,
    )
    score = compute_priority_score(high_conf_item)
    assert score_to_rank(score) == "P0"

    low_item = RecommendationItem(
        root_cause="XYZ issue", summary="x" * 20, evidence=["e"], impact="low", ease_of_fix="hard",
        confidence=0.1, suggested_fix="y" * 20,
    )
    assert score_to_rank(compute_priority_score(low_item)) == "P3"


def test_assign_priorities_sorts_most_urgent_first():
    low = RecommendationItem(root_cause="Low", summary="x" * 20, evidence=["e"], impact="low",
                              ease_of_fix="hard", confidence=0.2, suggested_fix="y" * 20)
    high = RecommendationItem(root_cause="High", summary="x" * 20, evidence=["e"], impact="high",
                               ease_of_fix="easy", confidence=0.9, suggested_fix="y" * 20)
    ranked = assign_priorities([low, high])
    assert ranked[0].root_cause == "High"
    assert ranked[0].priority in ("P0", "P1")
    assert overall_priority_rank(ranked) == ranked[0].priority


class _BrokenProvider:
    """Simulates a real LLM provider returning unparseable/invalid output."""

    model_name = "broken-test-provider"

    async def synthesize(self, evidence, candidates):
        raise LlmProviderError("model returned non-JSON garbage")


@pytest.mark.asyncio
async def test_invalid_llm_output_is_handled_not_raised(monkeypatch, db_session, url):
    from app.models.psi_run import PsiRun
    from app.models.stabilized_metric import StabilizedMetric
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    run = PsiRun(url_id=url.url_id, run_timestamp=now, strategy="mobile",
                 category_scores={"performance": 50, "accessibility": 80},
                 core_web_vitals={"lcp_ms": 5000, "cls": 0.3, "tbt_ms": 700, "fcp_ms": 2500, "speed_index_ms": 6000},
                 normalized_audits={}, run_status="success")
    db_session.add(run)
    db_session.commit()
    stab = StabilizedMetric(url_id=url.url_id, window_start=now, window_end=now, run_count=1,
                             median_metrics={"lcp_ms": 5000, "cls": 0.3, "tbt_ms": 700, "fcp_ms": 2500,
                                             "performance_score": 50, "accessibility_score": 80},
                             variability_metrics={}, flagged=False)
    db_session.add(stab)
    db_session.commit()

    import app.services.recommendations.service as svc
    monkeypatch.setattr(svc, "get_llm_provider", lambda settings=None: _BrokenProvider())

    record = await svc.generate_recommendations(db_session, url.url_id)
    assert record.validation_status == "invalid"
    assert record.root_cause_groups == []


def test_validate_flags_low_confidence_as_needs_review():
    item = RecommendationItem(root_cause="XYZ issue", summary="x" * 20, evidence=["e"], impact="medium",
                               ease_of_fix="medium", confidence=0.2, suggested_fix="y" * 20)
    from app.core.config import get_settings
    result_set = LlmRecommendationSet(recommendations=[item])
    assert _validate(result_set, get_settings()) == "needs_review"


def test_validate_marks_confident_set_as_valid():
    item = RecommendationItem(root_cause="XYZ issue", summary="x" * 20, evidence=["e"], impact="medium",
                               ease_of_fix="medium", confidence=0.9, suggested_fix="y" * 20)
    from app.core.config import get_settings
    result_set = LlmRecommendationSet(recommendations=[item])
    assert _validate(result_set, get_settings()) == "valid"
