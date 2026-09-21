"""
Multiple-run stabilization.

Never feed a single noisy PSI run to the LLM. This service takes the most
recent N runs (N = STABILIZATION_WINDOW_RUNS, overridable per-call) for a
URL, computes median metrics, and flags the window as unstable when
variability (relative stdev) exceeds a configurable threshold.
"""
import statistics
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.psi_run import PsiRun
from app.models.stabilized_metric import StabilizedMetric

_METRICS = ["lcp_ms", "cls", "tbt_ms", "fcp_ms", "speed_index_ms", "total_bytes"]


class InsufficientRunsError(Exception):
    """Raised when there aren't enough successful runs to stabilize."""


def _relative_stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = statistics.fmean(values)
    if mean == 0:
        return 0.0
    return statistics.stdev(values) / mean


def stabilize_url(db: Session, url_id: int, window_runs: int | None = None,
                   settings: Settings | None = None) -> StabilizedMetric:
    settings = settings or get_settings()
    window = window_runs or settings.STABILIZATION_WINDOW_RUNS

    stmt = (
        select(PsiRun)
        .where(PsiRun.url_id == url_id, PsiRun.run_status == "success")
        .order_by(PsiRun.run_timestamp.desc())
        .limit(window)
    )
    runs = list(db.scalars(stmt))

    if len(runs) < settings.STABILIZATION_MIN_RUNS:
        raise InsufficientRunsError(
            f"url_id={url_id} has only {len(runs)} successful run(s); need at least "
            f"{settings.STABILIZATION_MIN_RUNS} to stabilize."
        )

    runs = list(reversed(runs))  # chronological order for window_start/end

    median_metrics: dict[str, float | None] = {}
    variability_metrics: dict[str, float] = {}
    flagged = False

    for metric in _METRICS:
        values = [r.core_web_vitals.get(metric) for r in runs if r.core_web_vitals.get(metric) is not None]
        if not values:
            median_metrics[metric] = None
            variability_metrics[metric] = 0.0
            continue
        median_metrics[metric] = round(statistics.median(values), 3)
        rel_stdev = round(_relative_stdev(values), 4)
        variability_metrics[metric] = rel_stdev
        if rel_stdev > settings.VARIABILITY_FLAG_RELATIVE_STDEV:
            flagged = True

    perf_values = [r.category_scores.get("performance") for r in runs if r.category_scores.get("performance") is not None]
    a11y_values = [r.category_scores.get("accessibility") for r in runs if r.category_scores.get("accessibility") is not None]
    median_metrics["performance_score"] = round(statistics.median(perf_values), 1) if perf_values else None
    median_metrics["accessibility_score"] = round(statistics.median(a11y_values), 1) if a11y_values else None

    stabilized = StabilizedMetric(
        url_id=url_id,
        window_start=runs[0].run_timestamp,
        window_end=runs[-1].run_timestamp,
        run_count=len(runs),
        median_metrics=median_metrics,
        variability_metrics=variability_metrics,
        flagged=flagged,
        created_at=datetime.now(timezone.utc),
    )
    db.add(stabilized)
    db.commit()
    db.refresh(stabilized)
    return stabilized


def latest_stabilized(db: Session, url_id: int) -> StabilizedMetric | None:
    stmt = (
        select(StabilizedMetric)
        .where(StabilizedMetric.url_id == url_id)
        .order_by(StabilizedMetric.created_at.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()
