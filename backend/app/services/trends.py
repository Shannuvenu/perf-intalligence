"""
Trend computation (product spec section 16). Deliberately simple: split the
run history in half chronologically, compare the mean of each half, and
classify direction with a configurable percent-change threshold. No
overengineering - this is meant to be eyeballed on a chart, not a forecasting
model.
"""
import statistics
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.psi_run import PsiRun

_TREND_THRESHOLD_PCT = 0.05  # 5% change between halves to call it improving/regressing
_LOWER_IS_BETTER = {"lcp_ms", "cls", "tbt_ms", "fcp_ms", "speed_index_ms"}
_HIGHER_IS_BETTER = {"performance_score", "accessibility_score"}

TREND_METRICS = ["performance_score", "accessibility_score", "lcp_ms", "cls", "tbt_ms", "fcp_ms"]

Direction = Literal["improving", "stable", "regressing", "insufficient_data"]


def _extract_value(run: PsiRun, metric: str) -> float | None:
    if metric in ("performance_score", "accessibility_score"):
        key = metric.replace("_score", "")
        return run.category_scores.get(key)
    return run.core_web_vitals.get(metric)


def _direction(values: list[float], metric: str) -> Direction:
    if len(values) < 2:
        return "insufficient_data"
    mid = len(values) // 2
    first_half, second_half = values[:mid] if mid > 0 else values[:1], values[mid:]
    first_mean = statistics.fmean(first_half)
    second_mean = statistics.fmean(second_half)
    if first_mean == 0:
        return "stable"
    pct_change = (second_mean - first_mean) / abs(first_mean)

    better_is_higher = metric in _HIGHER_IS_BETTER
    if abs(pct_change) < _TREND_THRESHOLD_PCT:
        return "stable"
    improved = pct_change > 0 if better_is_higher else pct_change < 0
    return "improving" if improved else "regressing"


def compute_trends(db: Session, url_id: int, metrics: list[str] | None = None) -> list[dict]:
    metrics = metrics or TREND_METRICS
    stmt = (
        select(PsiRun)
        .where(PsiRun.url_id == url_id, PsiRun.run_status == "success")
        .order_by(PsiRun.run_timestamp.asc())
    )
    runs = list(db.scalars(stmt))

    results = []
    for metric in metrics:
        points = [{"timestamp": r.run_timestamp, "value": _extract_value(r, metric)} for r in runs]
        clean_values = [p["value"] for p in points if p["value"] is not None]
        results.append({
            "metric": metric,
            "direction": _direction(clean_values, metric),
            "points": points,
        })
    return results
