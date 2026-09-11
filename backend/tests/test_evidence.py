from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.models.psi_run import PsiRun
from app.models.stabilized_metric import StabilizedMetric
from app.services.evidence.extractor import extract_evidence


def _run(url_id, unused_js=0, third_party_ms=0, image_savings=0, a11y_findings=None, minutes_ago=0):
    return PsiRun(
        url_id=url_id,
        run_timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        strategy="mobile",
        category_scores={"performance": 55.0, "accessibility": 80.0},
        core_web_vitals={"lcp_ms": 4200, "cls": 0.05, "tbt_ms": 150, "fcp_ms": 1500, "speed_index_ms": 5000},
        normalized_audits={
            "unused_javascript_bytes": unused_js,
            "render_blocking_savings_ms": 0,
            "image_optimization_savings_bytes": image_savings,
            "third_party_blocking_ms": third_party_ms,
            "third_party_entities": [{"entity": "Ad Network", "blocking_time_ms": third_party_ms}] if third_party_ms else [],
            "layout_shift_sources": [],
            "accessibility_findings": a11y_findings or [],
        },
        run_status="success",
    )


def _stabilized(url_id, lcp=4200, cls=0.05, tbt=150, fcp=1500, run_count=3, flagged=False):
    now = datetime.now(timezone.utc)
    return StabilizedMetric(
        url_id=url_id, window_start=now - timedelta(minutes=30), window_end=now, run_count=run_count,
        median_metrics={"lcp_ms": lcp, "cls": cls, "tbt_ms": tbt, "fcp_ms": fcp,
                         "performance_score": 55.0, "accessibility_score": 80.0},
        variability_metrics={"lcp_ms": 0.05}, flagged=flagged,
    )


def test_poor_lcp_produces_critical_evidence():
    settings = get_settings()
    stab = _stabilized(1, lcp=settings.LCP_POOR_MS + 500)
    runs = [_run(1)]
    evidence = extract_evidence(runs, stab, settings)
    lcp_evidence = [e for e in evidence if e.metric == "lcp_ms"]
    assert len(lcp_evidence) == 1
    assert lcp_evidence[0].severity == "critical"


def test_good_lcp_produces_no_evidence():
    settings = get_settings()
    stab = _stabilized(1, lcp=1500)  # well under LCP_GOOD_MS
    runs = [_run(1)]
    evidence = extract_evidence(runs, stab, settings)
    assert not [e for e in evidence if e.metric == "lcp_ms"]


def test_unused_js_evidence_uses_average_across_window():
    settings = get_settings()
    stab = _stabilized(1)
    runs = [_run(1, unused_js=50_000, minutes_ago=3), _run(1, unused_js=250_000, minutes_ago=1)]
    evidence = extract_evidence(runs, stab, settings)
    js_evidence = [e for e in evidence if e.metric == "unused_javascript_bytes"]
    assert len(js_evidence) == 1
    assert js_evidence[0].value == 150_000  # mean of 50k and 250k


def test_accessibility_evidence_requires_majority_of_runs():
    settings = get_settings()
    stab = _stabilized(1, run_count=4)
    finding = {"id": "image-alt", "title": "Images missing alt text", "affected_nodes": ["img.hero"]}
    # Only appears in 1 of 4 runs -> should NOT be surfaced as evidence
    runs = [_run(1, a11y_findings=[finding], minutes_ago=4), _run(1, minutes_ago=3),
            _run(1, minutes_ago=2), _run(1, minutes_ago=1)]
    evidence = extract_evidence(runs, stab, settings)
    assert not [e for e in evidence if e.metric == "a11y_image-alt"]

    # Appears in 3 of 4 runs -> should be surfaced
    runs_majority = [_run(1, a11y_findings=[finding], minutes_ago=m) for m in (4, 3, 2)] + [_run(1, minutes_ago=1)]
    evidence_majority = extract_evidence(runs_majority, stab, settings)
    assert [e for e in evidence_majority if e.metric == "a11y_image-alt"]


def test_variability_flag_surfaces_info_evidence():
    settings = get_settings()
    stab = _stabilized(1, flagged=True)
    runs = [_run(1)]
    evidence = extract_evidence(runs, stab, settings)
    assert [e for e in evidence if e.metric == "variability" and e.severity == "info"]
