from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import get_settings
from app.models.psi_run import PsiRun
from app.services.stabilization.service import InsufficientRunsError, stabilize_url


def _make_run(db_session, url_id, lcp, cls, tbt, fcp, perf=60.0, a11y=85.0, minutes_ago=0):
    run = PsiRun(
        url_id=url_id,
        run_timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
        strategy="mobile",
        category_scores={"performance": perf, "accessibility": a11y},
        core_web_vitals={"lcp_ms": lcp, "cls": cls, "tbt_ms": tbt, "fcp_ms": fcp, "speed_index_ms": lcp + 800},
        normalized_audits={},
        run_status="success",
    )
    db_session.add(run)
    db_session.commit()
    return run


def test_median_lcp_matches_spec_example(db_session, url):
    # Exact example from the product spec: 3.2, 4.1, 2.9, 3.7, 3.4 -> median 3.4
    values = [3200, 4100, 2900, 3700, 3400]
    for i, v in enumerate(values):
        _make_run(db_session, url.url_id, lcp=v, cls=0.05, tbt=100, fcp=1200, minutes_ago=len(values) - i)

    result = stabilize_url(db_session, url.url_id)
    assert result.median_metrics["lcp_ms"] == 3400.0
    assert result.run_count == 5


def test_insufficient_runs_raises(db_session, url):
    _make_run(db_session, url.url_id, lcp=3000, cls=0.05, tbt=100, fcp=1200)
    with pytest.raises(InsufficientRunsError):
        stabilize_url(db_session, url.url_id)


def test_high_variability_flags_window(db_session, url):
    # Wildly different LCP values across runs -> relative stdev should exceed threshold
    for i, v in enumerate([1000, 8000, 1200, 7800, 1100]):
        _make_run(db_session, url.url_id, lcp=v, cls=0.05, tbt=100, fcp=1200, minutes_ago=5 - i)

    result = stabilize_url(db_session, url.url_id)
    assert result.flagged is True
    assert result.variability_metrics["lcp_ms"] > get_settings().VARIABILITY_FLAG_RELATIVE_STDEV


def test_low_variability_not_flagged(db_session, url):
    for i, v in enumerate([3000, 3050, 2980, 3020, 3010]):
        _make_run(db_session, url.url_id, lcp=v, cls=0.05, tbt=100, fcp=1200, minutes_ago=5 - i)

    result = stabilize_url(db_session, url.url_id)
    assert result.flagged is False


def test_only_successful_runs_are_used(db_session, url):
    from app.models.psi_run import PsiRun as PR
    failed = PR(url_id=url.url_id, run_timestamp=datetime.now(timezone.utc), strategy="mobile",
                category_scores={}, core_web_vitals={}, normalized_audits={}, run_status="failed",
                error_message="boom")
    db_session.add(failed)
    db_session.commit()
    for i, v in enumerate([3000, 3050, 2980]):
        _make_run(db_session, url.url_id, lcp=v, cls=0.05, tbt=100, fcp=1200, minutes_ago=3 - i)

    result = stabilize_url(db_session, url.url_id)
    assert result.run_count == 3  # the failed run must not be counted
