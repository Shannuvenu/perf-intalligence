"""
Positive-signal extraction - the mirror image of evidence/extractor.py.

extractor.py answers "what's wrong". This answers "what's already good, and
what technique is probably responsible" - used for competitor benchmarking:
when you point this tool at a competitor's site, this is what tells you
what THEY are doing right, not just how they compare on raw numbers.

Same thresholds as extractor.py (app/core/config.py) - a metric only counts
as a strength if it's inside the "good" band, so this never contradicts the
evidence extractor's "poor"/"needs improvement" calls.
"""
import statistics

from app.core.config import Settings, get_settings
from app.models.psi_run import PsiRun
from app.models.stabilized_metric import StabilizedMetric


def _mean_audit_value(runs: list[PsiRun], key: str) -> float:
    values = [r.normalized_audits.get(key, 0) or 0 for r in runs]
    return statistics.fmean(values) if values else 0.0


def extract_strengths(
    runs: list[PsiRun], stabilized: StabilizedMetric, settings: Settings | None = None
) -> list[str]:
    settings = settings or get_settings()
    m = stabilized.median_metrics
    strengths: list[str] = []

    lcp = m.get("lcp_ms")
    if lcp is not None and lcp <= settings.LCP_GOOD_MS:
        strengths.append(
            f"LCP is {lcp/1000:.1f}s (median of {stabilized.run_count} runs), within the good "
            f"threshold of {settings.LCP_GOOD_MS/1000:.1f}s - likely optimized/responsive images "
            f"and a fast hosting or CDN setup."
        )

    tbt = m.get("tbt_ms")
    if tbt is not None and tbt <= settings.TBT_GOOD_MS:
        strengths.append(
            f"TBT is {round(tbt)}ms, within the good threshold of {settings.TBT_GOOD_MS}ms - "
            f"main-thread JavaScript, including third-party tags, is well managed."
        )

    cls = m.get("cls")
    if cls is not None and cls <= settings.CLS_GOOD:
        strengths.append(
            f"CLS is {cls}, within the good threshold of {settings.CLS_GOOD} - space is properly "
            f"reserved for images and ad slots before they load."
        )


    total_bytes = m.get("total_bytes")
    if total_bytes is not None and total_bytes <= settings.BANDWIDTH_GOOD_BYTES:
        strengths.append(
            f"Total page weight is {total_bytes/1_000_000:.1f}MB, within a mobile-friendly budget of "
            f"{settings.BANDWIDTH_GOOD_BYTES/1_000_000:.1f}MB."
        )

    avg_unused_js = _mean_audit_value(runs, "unused_javascript_bytes")
    if runs and avg_unused_js < settings.UNUSED_JS_FLAG_BYTES:
        strengths.append("Minimal unused JavaScript shipped per page - likely code-split by route.")

    avg_third_party = _mean_audit_value(runs, "third_party_blocking_ms")
    if runs and avg_third_party < settings.THIRD_PARTY_TBT_FLAG_MS:
        strengths.append("Low third-party blocking time - ad/analytics tags are likely deferred or kept minimal.")

    avg_image_savings = _mean_audit_value(runs, "image_optimization_savings_bytes")
    if runs and avg_image_savings < settings.IMAGE_SAVINGS_FLAG_BYTES:
        strengths.append("Images are already well-optimized - little additional savings available from compression.")

    a11y = m.get("accessibility_score")
    if a11y is not None and a11y >= 90:
        strengths.append(f"Accessibility score is {a11y} - alt text, form labels and contrast are largely in order.")

    perf = m.get("performance_score")
    if perf is not None and perf >= 90:
        strengths.append(f"Overall performance score is {perf} - a well-optimized page across the board.")

    return strengths