import pytest

from app.core.config import get_settings
from app.schemas.recommendation import (
    LlmRecommendationSet,
    RecommendationItem,
)
from app.services.evidence.models import Evidence
from app.services.llm.base import LlmProviderError
from app.services.llm.mock_llm import MockLlmProvider
from app.services.recommendations.candidate_signals import (
    CandidateSignal,
    IMAGE_OPTIMIZATION,
    LAYOUT_SHIFT,
    THIRD_PARTY_BLOCKING,
    UNUSED_JAVASCRIPT,
)
from app.services.recommendations.priority import (
    assign_priorities,
    compute_priority_score,
    overall_priority_rank,
    score_to_rank,
)
from app.services.recommendations.validation import validate_and_resolve


def _item(**overrides):
    base = dict(
        candidate_id=THIRD_PARTY_BLOCKING,
        summary="x" * 20,
        evidence_refs=["E01"],
        impact="high",
        ease_of_fix="easy",
        confidence=0.95,
        suggested_fix="y" * 20,
    )
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_mock_llm_synthesizes_from_candidates():
    ev = Evidence(
        id="E01",
        metric="tbt_ms",
        description="Median TBT is 620ms.",
        value=620,
        severity="critical",
        evidence_strength="direct",
        tags=["tbt"],
    )

    candidate = CandidateSignal(
        candidate_id=THIRD_PARTY_BLOCKING,
        root_cause_hypothesis="Heavy third-party/ad-related execution",
        supporting_evidence=[ev],
        strength=0.9,
    )

    provider = MockLlmProvider()
    result = await provider.synthesize([ev], [candidate])

    assert len(result.recommendations) == 1

    rec = result.recommendations[0]

    assert rec.candidate_id == THIRD_PARTY_BLOCKING
    assert rec.evidence_refs == ["E01"]
    assert 0.0 <= rec.confidence <= 1.0


@pytest.mark.asyncio
async def test_mock_llm_with_no_candidates_returns_empty_with_note():
    provider = MockLlmProvider()

    result = await provider.synthesize([], [])

    assert result.recommendations == []
    assert result.insufficient_evidence_note is not None


def test_priority_score_and_rank_boundaries():
    high_conf_item = RecommendationItem(
        **_item(
            impact="high",
            ease_of_fix="easy",
            confidence=0.95,
        )
    )

    score = compute_priority_score(high_conf_item)

    assert score_to_rank(score) == "P0"

    low_item = RecommendationItem(
        **_item(
            impact="low",
            ease_of_fix="hard",
            confidence=0.1,
        )
    )

    assert score_to_rank(
        compute_priority_score(low_item)
    ) == "P3"


def test_assign_priorities_sorts_most_urgent_first():
    low = RecommendationItem(
        **_item(
            candidate_id=THIRD_PARTY_BLOCKING,
            impact="low",
            ease_of_fix="hard",
            confidence=0.2,
        )
    )

    high = RecommendationItem(
        **_item(
            candidate_id=IMAGE_OPTIMIZATION,
            impact="high",
            ease_of_fix="easy",
            confidence=0.9,
        )
    )

    ranked = assign_priorities([low, high])

    assert ranked[0].candidate_id == IMAGE_OPTIMIZATION
    assert ranked[0].priority in ("P0", "P1")
    assert overall_priority_rank(ranked) == ranked[0].priority


class _BrokenProvider:
    """Simulates a real LLM provider returning invalid output."""

    model_name = "broken-test-provider"

    async def synthesize(self, evidence, candidates, page_metrics=None):
        raise LlmProviderError(
            "model returned non-JSON garbage"
        )


@pytest.mark.asyncio
async def test_invalid_llm_output_is_handled_not_raised(
    monkeypatch,
    db_session,
    url,
):
    from app.models.psi_run import PsiRun
    from app.models.stabilized_metric import StabilizedMetric
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    run = PsiRun(
        url_id=url.url_id,
        run_timestamp=now,
        strategy="mobile",
        category_scores={
            "performance": 50,
            "accessibility": 80,
        },
        core_web_vitals={
            "lcp_ms": 5000,
            "cls": 0.3,
            "tbt_ms": 700,
            "fcp_ms": 2500,
            "speed_index_ms": 6000,
        },
        normalized_audits={},
        run_status="success",
    )

    db_session.add(run)
    db_session.commit()

    stab = StabilizedMetric(
        url_id=url.url_id,
        window_start=now,
        window_end=now,
        run_count=1,
        median_metrics={
            "lcp_ms": 5000,
            "cls": 0.3,
            "tbt_ms": 700,
            "fcp_ms": 2500,
            "performance_score": 50,
            "accessibility_score": 80,
        },
        variability_metrics={},
        flagged=False,
    )

    db_session.add(stab)
    db_session.commit()

    import app.services.recommendations.pipeline as pipeline_module

    monkeypatch.setattr(
        pipeline_module,
        "get_llm_provider",
        lambda settings=None: _BrokenProvider(),
    )

    import app.services.recommendations.service as svc

    record = await svc.generate_recommendations(
        db_session,
        url.url_id,
    )

    assert record.validation_status == "invalid"
    assert record.root_cause_groups == []


def test_validate_accepts_well_formed_recommendation():
    ev = Evidence(
        id="E01",
        metric="tbt_ms",
        description="Median TBT is 620ms.",
        value=620,
        severity="critical",
        evidence_strength="direct",
        tags=["tbt"],
    )

    candidate = CandidateSignal(
        candidate_id=THIRD_PARTY_BLOCKING,
        root_cause_hypothesis="Heavy third-party/ad-related execution",
        supporting_evidence=[ev],
        strength=0.9,
    )

    item = RecommendationItem(
        **_item(
            candidate_id=THIRD_PARTY_BLOCKING,
            evidence_refs=["E01"],
            confidence=0.95,
        )
    )

    result_set = LlmRecommendationSet(
        recommendations=[item]
    )

    items, status, note = validate_and_resolve(
        result_set,
        [ev],
        [candidate],
        get_settings(),
    )

    assert len(items) == 1
    assert status == "valid"
    assert items[0].evidence == [ev.description]


def test_weak_evidence_forces_needs_review_even_if_llm_is_confident():
    """
    Weak evidence must force low confidence regardless of what
    confidence value the LLM reports.
    """

    ev = Evidence(
        id="E01",
        metric="tbt_ms",
        description="d",
        value=1,
        severity="warning",
        evidence_strength="insufficient",
        tags=[],
    )

    candidate = CandidateSignal(
        candidate_id=THIRD_PARTY_BLOCKING,
        root_cause_hypothesis="t",
        supporting_evidence=[ev],
        strength=0.5,
    )

    item = RecommendationItem(
        **_item(
            candidate_id=THIRD_PARTY_BLOCKING,
            evidence_refs=["E01"],
            confidence=0.99,
        )
    )

    result_set = LlmRecommendationSet(
        recommendations=[item]
    )

    items, status, note = validate_and_resolve(
        result_set,
        [ev],
        [candidate],
        get_settings(),
    )

    assert items[0].confidence == 0.4
    assert status == "needs_review"


def test_llm_reported_impact_ease_confidence_do_not_control_priority():
    """
    Same evidence must produce the same resolved priority inputs,
    regardless of what the LLM reports.
    """

    settings = get_settings()

    ev = Evidence(
        id="E01",
        metric="third_party_blocking_ms",
        description="d",
        value=500,
        severity="warning",
        evidence_strength="derived",
        tags=["third-party"],
    )

    candidate = CandidateSignal(
        candidate_id=THIRD_PARTY_BLOCKING,
        root_cause_hypothesis="t",
        supporting_evidence=[ev],
        strength=0.6,
    )

    optimistic = RecommendationItem(
        **_item(
            candidate_id=THIRD_PARTY_BLOCKING,
            evidence_refs=["E01"],
            impact="high",
            ease_of_fix="easy",
            confidence=1.0,
        )
    )

    pessimistic = RecommendationItem(
        **_item(
            candidate_id=THIRD_PARTY_BLOCKING,
            evidence_refs=["E01"],
            impact="low",
            ease_of_fix="hard",
            confidence=0.1,
        )
    )

    items_a, _, _ = validate_and_resolve(
        LlmRecommendationSet(
            recommendations=[optimistic]
        ),
        [ev],
        [candidate],
        settings,
    )

    items_b, _, _ = validate_and_resolve(
        LlmRecommendationSet(
            recommendations=[pessimistic]
        ),
        [ev],
        [candidate],
        settings,
    )

    assert items_a[0].impact == items_b[0].impact
    assert items_a[0].ease_of_fix == items_b[0].ease_of_fix
    assert items_a[0].confidence == items_b[0].confidence

    assert compute_priority_score(
        items_a[0]
    ) == compute_priority_score(
        items_b[0]
    )


def test_pessimistic_llm_confidence_is_overridden_not_merely_capped():
    """
    Strong evidence must determine confidence, not the LLM's
    self-reported confidence.
    """

    ev = Evidence(
        id="E01",
        metric="third_party_blocking_ms",
        description="d",
        value=500,
        severity="critical",
        evidence_strength="direct",
        tags=["third-party"],
    )

    candidate = CandidateSignal(
        candidate_id=THIRD_PARTY_BLOCKING,
        root_cause_hypothesis="t",
        supporting_evidence=[ev],
        strength=0.9,
    )

    item = RecommendationItem(
        **_item(
            candidate_id=THIRD_PARTY_BLOCKING,
            evidence_refs=["E01"],
            confidence=0.1,
        )
    )

    items, status, _ = validate_and_resolve(
        LlmRecommendationSet(
            recommendations=[item]
        ),
        [ev],
        [candidate],
        get_settings(),
    )

    assert items[0].confidence == 1.0
    assert status == "valid"


def test_priority_still_uses_existing_weighted_formula_and_thresholds():
    """
    Priority remains deterministic while preserving the existing
    score formula and P0-P3 thresholds.
    """

    settings = get_settings()

    # ---------------------------------------------------------------
    # Critical + LAYOUT_SHIFT + easy + direct
    #
    # 0.5*1.0 + 0.3*1.0 + 0.2*1.0 = 1.0 -> P0
    # ---------------------------------------------------------------

    ev1 = Evidence(
        id="E01",
        metric="cls",
        description="d",
        value=0.3,
        severity="critical",
        evidence_strength="direct",
        tags=["cls"],
    )

    c1 = CandidateSignal(
        candidate_id=LAYOUT_SHIFT,
        root_cause_hypothesis="t",
        supporting_evidence=[ev1],
        strength=1.0,
    )

    item1 = RecommendationItem(
        **_item(
            candidate_id=LAYOUT_SHIFT,
            evidence_refs=["E01"],
        )
    )

    items1, _, _ = validate_and_resolve(
        LlmRecommendationSet(
            recommendations=[item1]
        ),
        [ev1],
        [c1],
        settings,
    )

    assert score_to_rank(
        compute_priority_score(items1[0])
    ) == "P0"

    # ---------------------------------------------------------------
    # Warning + UNUSED_JAVASCRIPT + hard + derived
    #
    # 0.5*0.6 + 0.3*0.3 + 0.2*0.85 = 0.56 -> P1
    # ---------------------------------------------------------------

    ev2 = Evidence(
        id="E01",
        metric="unused_javascript_bytes",
        description="d",
        value=200_000,
        severity="warning",
        evidence_strength="derived",
        tags=["unused-js"],
    )

    c2 = CandidateSignal(
        candidate_id=UNUSED_JAVASCRIPT,
        root_cause_hypothesis="t",
        supporting_evidence=[ev2],
        strength=0.5,
    )

    item2 = RecommendationItem(
        **_item(
            candidate_id=UNUSED_JAVASCRIPT,
            evidence_refs=["E01"],
        )
    )

    items2, _, _ = validate_and_resolve(
        LlmRecommendationSet(
            recommendations=[item2]
        ),
        [ev2],
        [c2],
        settings,
    )

    assert score_to_rank(
        compute_priority_score(items2[0])
    ) == "P1"