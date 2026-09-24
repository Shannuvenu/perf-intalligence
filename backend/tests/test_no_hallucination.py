"""
Hallucination / evidence-grounding tests (product spec section 20).

These exercise the full evidence -> candidate -> LLM -> validation pipeline
using the deterministic mock LLM (which always plays by the rules) plus
hand-crafted "malicious" LLM outputs (to simulate a real LLM going off the
rails) fed straight into validate_and_resolve.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import get_settings
from app.models.psi_run import PsiRun
from app.models.stabilized_metric import StabilizedMetric
from app.schemas.recommendation import LlmRecommendationSet, RecommendationItem
from app.services.evidence.extractor import extract_evidence
from app.services.llm.mock_llm import MockLlmProvider
from app.services.recommendations.candidate_signals import (
    IMAGE_OPTIMIZATION,
    PAGE_WEIGHT,
    RENDER_BLOCKING,
    THIRD_PARTY_BLOCKING,
    UNUSED_JAVASCRIPT,
    generate_candidate_signals,
)
from app.services.recommendations.validation import validate_and_resolve


def _run(lcp=1800, cls=0.04, tbt=80, fcp=1200, unused_js=0, render_blocking=0, image_savings=0,
         third_party_ms=0, total_bytes=1_000_000):
    return PsiRun(
        url_id=1, run_timestamp=datetime.now(timezone.utc), strategy="mobile",
        category_scores={"performance": 80.0, "accessibility": 90.0},
        core_web_vitals={"lcp_ms": lcp, "cls": cls, "tbt_ms": tbt, "fcp_ms": fcp,
                          "speed_index_ms": lcp, "total_bytes": total_bytes},
        normalized_audits={
            "unused_javascript_bytes": unused_js,
            "render_blocking_savings_ms": render_blocking,
            "image_optimization_savings_bytes": image_savings,
            "third_party_blocking_ms": third_party_ms,
            "third_party_entities": [{"entity": "Ad Network", "blocking_time_ms": third_party_ms}] if third_party_ms else [],
            "layout_shift_sources": [],
            "accessibility_findings": [],
        },
        run_status="success",
    )


def _stabilized(lcp=1800, cls=0.04, tbt=80, fcp=1200, total_bytes=1_000_000):
    now = datetime.now(timezone.utc)
    return StabilizedMetric(
        url_id=1, window_start=now - timedelta(minutes=10), window_end=now, run_count=1,
        median_metrics={"lcp_ms": lcp, "cls": cls, "tbt_ms": tbt, "fcp_ms": fcp, "total_bytes": total_bytes,
                         "performance_score": 80.0, "accessibility_score": 90.0},
        variability_metrics={}, flagged=False,
    )


def _pipeline(run: PsiRun, stab: StabilizedMetric):
    settings = get_settings()
    evidence = extract_evidence([run], stab, settings)
    candidates = generate_candidate_signals(evidence)
    return evidence, candidates


# TEST 1 - Bad LCP only -> 0 root-cause recommendations.
@pytest.mark.asyncio
async def test_bad_lcp_only_produces_no_root_cause_recommendation():
    settings = get_settings()
    run = _run(lcp=settings.LCP_POOR_MS + 200)
    stab = _stabilized(lcp=settings.LCP_POOR_MS + 200)
    evidence, candidates = _pipeline(run, stab)

    # LCP alone must never create IMAGE_OPTIMIZATION / RENDER_BLOCKING / etc.
    assert candidates == []

    provider = MockLlmProvider()
    result = await provider.synthesize(evidence, candidates)
    items, status, note = validate_and_resolve(result, evidence, candidates, settings)
    assert items == []
    assert note is not None


# TEST 2 - Bad LCP + image evidence -> IMAGE_OPTIMIZATION candidate exists.
def test_bad_lcp_with_image_evidence_creates_image_candidate():
    settings = get_settings()
    run = _run(lcp=settings.LCP_POOR_MS + 200, image_savings=settings.IMAGE_SAVINGS_FLAG_BYTES + 200_000)
    stab = _stabilized(lcp=settings.LCP_POOR_MS + 200)
    evidence, candidates = _pipeline(run, stab)
    assert any(c.candidate_id == IMAGE_OPTIMIZATION for c in candidates)


# TEST 3 - Bad LCP + render-blocking evidence -> RENDER_BLOCKING candidate exists.
def test_bad_lcp_with_render_blocking_evidence_creates_candidate():
    settings = get_settings()
    run = _run(lcp=settings.LCP_POOR_MS + 200, render_blocking=400)
    stab = _stabilized(lcp=settings.LCP_POOR_MS + 200)
    evidence, candidates = _pipeline(run, stab)
    assert any(c.candidate_id == RENDER_BLOCKING for c in candidates)


# TEST 4 - Fake LLM evidence reference -> rejected.
def test_fake_evidence_ref_is_rejected():
    settings = get_settings()
    run = _run(lcp=settings.LCP_POOR_MS + 200, image_savings=300_000)
    stab = _stabilized(lcp=settings.LCP_POOR_MS + 200)
    evidence, candidates = _pipeline(run, stab)

    bad_item = RecommendationItem(
        candidate_id=IMAGE_OPTIMIZATION, summary="x" * 20, evidence_refs=["FAKE123"],
        impact="high", ease_of_fix="medium", confidence=0.9, suggested_fix="y" * 20,
    )
    result = LlmRecommendationSet(recommendations=[bad_item])
    items, status, note = validate_and_resolve(result, evidence, candidates, settings)
    assert items == []
    assert status == "needs_review"


# TEST 5 - Wrong candidate: only unused-JS evidence exists, LLM claims IMAGE_OPTIMIZATION.
def test_wrong_candidate_is_rejected():
    settings = get_settings()
    run = _run(unused_js=settings.UNUSED_JS_FLAG_BYTES + 50_000)
    stab = _stabilized()
    evidence, candidates = _pipeline(run, stab)
    assert any(c.candidate_id == UNUSED_JAVASCRIPT for c in candidates)
    assert not any(c.candidate_id == IMAGE_OPTIMIZATION for c in candidates)

    # LLM invents IMAGE_OPTIMIZATION, which was never a supported candidate.
    unused_js_evidence_id = next(e.id for e in evidence if e.metric == "unused_javascript_bytes")
    bad_item = RecommendationItem(
        candidate_id=IMAGE_OPTIMIZATION, summary="x" * 20, evidence_refs=[unused_js_evidence_id],
        impact="high", ease_of_fix="medium", confidence=0.9, suggested_fix="y" * 20,
    )
    result = LlmRecommendationSet(recommendations=[bad_item])
    items, status, note = validate_and_resolve(result, evidence, candidates, settings)
    assert items == []


# TEST 6 - Healthy page -> 0 recommendations.
@pytest.mark.asyncio
async def test_healthy_page_produces_zero_recommendations():
    run = _run()
    stab = _stabilized()
    evidence, candidates = _pipeline(run, stab)
    assert candidates == []

    provider = MockLlmProvider()
    result = await provider.synthesize(evidence, candidates)
    settings = get_settings()
    items, status, note = validate_and_resolve(result, evidence, candidates, settings)
    assert items == []
    assert status == "valid"


# TEST 7 - Unsupported ad claim: TBT poor but no third-party evidence -> rejected.
def test_unsupported_third_party_claim_is_rejected():
    settings = get_settings()
    run = _run(tbt=settings.TBT_POOR_MS + 100)  # no third_party_ms
    stab = _stabilized(tbt=settings.TBT_POOR_MS + 100)
    evidence, candidates = _pipeline(run, stab)
    assert not any(c.candidate_id == THIRD_PARTY_BLOCKING for c in candidates)

    tbt_evidence_id = next(e.id for e in evidence if e.metric == "tbt_ms")
    bad_item = RecommendationItem(
        candidate_id=THIRD_PARTY_BLOCKING, summary="Ads are blocking the main thread." + "x" * 10,
        evidence_refs=[tbt_evidence_id], impact="high", ease_of_fix="medium", confidence=0.9,
        suggested_fix="y" * 20,
    )
    result = LlmRecommendationSet(recommendations=[bad_item])
    items, status, note = validate_and_resolve(result, evidence, candidates, settings)
    assert items == []


# TEST 8 - Resource preservation from normalizer -> extractor.
def test_resource_preserved_from_normalizer_through_evidence():
    from app.services.psi.normalizer import normalize_psi_result

    raw = {
        "lighthouseResult": {
            "categories": {"performance": {"score": 0.5}, "accessibility": {"score": 0.9}},
            "audits": {
                "uses-optimized-images": {
                    "details": {"overallSavingsBytes": 219350, "items": [
                        {"url": "https://example.com/hero.jpg", "wastedBytes": 219350}
                    ]},
                },
            },
        }
    }
    normalized = normalize_psi_result(raw)
    items = normalized["normalized_audits"]["image_optimization_items"]
    assert items == [{"resource": "https://example.com/hero.jpg", "wasted_bytes": 219350}]

    settings = get_settings()
    run = _run(image_savings=settings.IMAGE_SAVINGS_FLAG_BYTES + 100_000)
    run.normalized_audits["image_optimization_items"] = items
    stab = _stabilized()
    evidence = extract_evidence([run], stab, settings)
    img_evidence = next(e for e in evidence if e.metric == "image_optimization_savings_bytes")
    assert img_evidence.id
    assert img_evidence.audit_id == "uses-optimized-images"
    assert img_evidence.resource == "https://example.com/hero.jpg"


# TEST 9 - Evidence membership: ref belongs to a DIFFERENT candidate -> rejected.
def test_evidence_ref_from_another_candidate_is_rejected():
    settings = get_settings()
    run = _run(image_savings=settings.IMAGE_SAVINGS_FLAG_BYTES + 100_000, render_blocking=400)
    stab = _stabilized()
    evidence, candidates = _pipeline(run, stab)

    render_blocking_evidence_id = next(e.id for e in evidence if e.metric == "render_blocking_savings_ms")
    bad_item = RecommendationItem(
        candidate_id=IMAGE_OPTIMIZATION, summary="x" * 20, evidence_refs=[render_blocking_evidence_id],
        impact="high", ease_of_fix="medium", confidence=0.9, suggested_fix="y" * 20,
    )
    result = LlmRecommendationSet(recommendations=[bad_item])
    items, status, note = validate_and_resolve(result, evidence, candidates, settings)
    assert items == []


# TEST 10 - Zero recommendations is a VALID result, not an error.
def test_zero_recommendations_is_valid_not_error():
    settings = get_settings()
    result = LlmRecommendationSet(recommendations=[], insufficient_evidence_note="Nothing actionable.")
    items, status, note = validate_and_resolve(result, [], [], settings)
    assert items == []
    assert status == "valid"
    assert note == "Nothing actionable."
def test_image_optimization_evidence_excludes_lcp():
    settings = get_settings()
    run = _run(
        lcp=settings.LCP_POOR_MS + 200,
        image_savings=settings.IMAGE_SAVINGS_FLAG_BYTES + 200_000,
    )
    stab = _stabilized(lcp=settings.LCP_POOR_MS + 200)

    evidence, candidates = _pipeline(run, stab)

    img = next(
        c for c in candidates
        if c.candidate_id == IMAGE_OPTIMIZATION
    )

    assert all(
        e.metric != "lcp_ms"
        for e in img.supporting_evidence
    )


def test_render_blocking_evidence_excludes_fcp():
    settings = get_settings()

    run = _run(render_blocking=400)
    stab = _stabilized()

    evidence, candidates = _pipeline(run, stab)

    rb = next(
        c for c in candidates
        if c.candidate_id == RENDER_BLOCKING
    )

    assert all(
        e.metric != "fcp_ms"
        for e in rb.supporting_evidence
    )


def test_third_party_blocking_evidence_excludes_tbt_and_unused_js():
    settings = get_settings()

    run = _run(
        third_party_ms=settings.THIRD_PARTY_TBT_FLAG_MS + 100,
        unused_js=settings.UNUSED_JS_FLAG_BYTES + 50_000,
    )
    stab = _stabilized()

    evidence, candidates = _pipeline(run, stab)

    tp = next(
        c for c in candidates
        if c.candidate_id == THIRD_PARTY_BLOCKING
    )

    assert all(
        e.metric not in ("tbt_ms", "unused_javascript_bytes")
        for e in tp.supporting_evidence
    )


def test_unused_javascript_evidence_excludes_tbt():
    settings = get_settings()

    run = _run(
        unused_js=settings.UNUSED_JS_FLAG_BYTES + 50_000
    )
    stab = _stabilized()

    evidence, candidates = _pipeline(run, stab)

    js = next(
        c for c in candidates
        if c.candidate_id == UNUSED_JAVASCRIPT
    )

    assert all(
        e.metric != "tbt_ms"
        for e in js.supporting_evidence
    )


def test_page_weight_evidence_excludes_image_savings():
    settings = get_settings()

    total_bytes = settings.BANDWIDTH_POOR_BYTES + 100_000

    run = _run(
        total_bytes=total_bytes,
        image_savings=settings.IMAGE_SAVINGS_FLAG_BYTES + 50_000,
    )

    stab = _stabilized(
        total_bytes=total_bytes,
    )

    evidence, candidates = _pipeline(run, stab)

    pw = next(
        c for c in candidates
        if c.candidate_id == PAGE_WEIGHT
    )

    assert all(
        e.metric != "image_optimization_savings_bytes"
        for e in pw.supporting_evidence
    )