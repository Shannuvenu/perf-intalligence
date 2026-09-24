"""
Deterministic evidence extraction (product spec section 9).

Runs BEFORE any LLM call. Turns stabilized metrics + normalized audit data
from the run window into a list of Evidence objects with explicit
thresholds, so nothing downstream has to "claim" a root cause without a
number behind it.

Every Evidence item gets a stable id (E01, E02, ...) assigned here, plus an
evidence_strength ("direct" | "derived" | "insufficient") and, where
Lighthouse gives it, the specific resource URL responsible. Candidate
generation and the LLM are only ever allowed to reference evidence by these
ids - see recommendations/candidate_signals.py and recommendations/validation.py.
"""
import statistics
from collections import Counter

from app.core.config import Settings, get_settings
from app.models.psi_run import PsiRun
from app.models.stabilized_metric import StabilizedMetric
from app.services.evidence.models import Evidence


def _mean_audit_value(runs: list[PsiRun], key: str) -> float:
    values = [r.normalized_audits.get(key, 0) or 0 for r in runs]
    return statistics.fmean(values) if values else 0.0


def _top_resource(runs: list[PsiRun], items_key: str, weight_key: str) -> str | None:
    """The single resource most responsible for an audit's savings, taken
    from the latest run that actually reports resource-level items. Never
    invented when Lighthouse didn't provide item-level detail."""
    for run in reversed(runs):
        items = run.normalized_audits.get(items_key) or []
        if items:
            top = max(items, key=lambda i: i.get(weight_key, 0) or 0)
            return top.get("resource")
    return None


class _IdAllocator:
    def __init__(self) -> None:
        self._n = 0

    def next(self) -> str:
        self._n += 1
        return f"E{self._n:02d}"


def extract_evidence(
    runs: list[PsiRun], stabilized: StabilizedMetric, settings: Settings | None = None
) -> list[Evidence]:
    settings = settings or get_settings()
    evidence: list[Evidence] = []
    ids = _IdAllocator()
    m = stabilized.median_metrics

    # --- Core Web Vitals -------------------------------------------------
    # These are outcome metrics: PageSpeed measured them directly ("direct"
    # evidence_strength), but a poor value alone never establishes WHY the
    # metric is poor. Root-cause candidates only attach to these when a
    # supporting audit (image savings, render-blocking, etc.) exists too -
    # see candidate_signals.py.
    lcp = m.get("lcp_ms")
    if lcp is not None:
        if lcp >= settings.LCP_POOR_MS:
            evidence.append(Evidence(
                id=ids.next(), audit_id="largest-contentful-paint",
                metric="lcp_ms", value=lcp, threshold=settings.LCP_POOR_MS, severity="critical",
                evidence_strength="direct",
                description=f"Median LCP is {lcp/1000:.1f}s across {stabilized.run_count} runs "
                            f"(poor threshold: {settings.LCP_POOR_MS/1000:.1f}s).",
                tags=["performance", "lcp"],
            ))
        elif lcp > settings.LCP_GOOD_MS:
            evidence.append(Evidence(
                id=ids.next(), audit_id="largest-contentful-paint",
                metric="lcp_ms", value=lcp, threshold=settings.LCP_GOOD_MS, severity="warning",
                evidence_strength="direct",
                description=f"Median LCP is {lcp/1000:.1f}s across {stabilized.run_count} runs - "
                            f"needs improvement (good threshold: {settings.LCP_GOOD_MS/1000:.1f}s).",
                tags=["performance", "lcp"],
            ))

    tbt = m.get("tbt_ms")
    if tbt is not None:
        if tbt >= settings.TBT_POOR_MS:
            evidence.append(Evidence(
                id=ids.next(), audit_id="total-blocking-time",
                metric="tbt_ms", value=tbt, threshold=settings.TBT_POOR_MS, severity="critical",
                evidence_strength="direct",
                description=f"Median Total Blocking Time is {round(tbt)}ms across {stabilized.run_count} runs "
                            f"(poor threshold: {settings.TBT_POOR_MS}ms) - main thread is busy during load.",
                tags=["performance", "tbt", "main-thread"],
            ))
        elif tbt > settings.TBT_GOOD_MS:
            evidence.append(Evidence(
                id=ids.next(), audit_id="total-blocking-time",
                metric="tbt_ms", value=tbt, threshold=settings.TBT_GOOD_MS, severity="warning",
                evidence_strength="direct",
                description=f"Median TBT is {round(tbt)}ms - needs improvement.",
                tags=["performance", "tbt", "main-thread"],
            ))

    cls = m.get("cls")
    if cls is not None:
        if cls >= settings.CLS_POOR:
            evidence.append(Evidence(
                id=ids.next(), audit_id="cumulative-layout-shift",
                metric="cls", value=cls, threshold=settings.CLS_POOR, severity="critical",
                evidence_strength="direct",
                description=f"Median CLS is {cls} across {stabilized.run_count} runs "
                            f"(poor threshold: {settings.CLS_POOR}).",
                tags=["performance", "cls", "layout-shift"],
            ))
        elif cls > settings.CLS_GOOD:
            evidence.append(Evidence(
                id=ids.next(), audit_id="cumulative-layout-shift",
                metric="cls", value=cls, threshold=settings.CLS_GOOD, severity="warning",
                evidence_strength="direct",
                description=f"Median CLS is {cls} - needs improvement.",
                tags=["performance", "cls", "layout-shift"],
            ))

    total_bytes = m.get("total_bytes")
    if total_bytes is not None and total_bytes > settings.BANDWIDTH_GOOD_BYTES:
        severity = "critical" if total_bytes >= settings.BANDWIDTH_POOR_BYTES else "warning"
        evidence.append(Evidence(
            id=ids.next(), audit_id="total-byte-weight",
            metric="total_bytes", value=total_bytes, threshold=settings.BANDWIDTH_GOOD_BYTES, severity=severity,
            evidence_strength="direct",
            description=f"Median total page weight is {total_bytes/1_000_000:.1f}MB across {stabilized.run_count} "
                        f"runs (good threshold: {settings.BANDWIDTH_GOOD_BYTES/1_000_000:.1f}MB) - heavy on mobile data.",
            tags=["performance", "bandwidth"],
        ))

    # --- Variability flag (from stabilization, not a "root cause" itself,
    # but relevant context the LLM should see) ----------------------------
    if stabilized.flagged:
        unstable = [k for k, v in stabilized.variability_metrics.items()
                    if v > settings.VARIABILITY_FLAG_RELATIVE_STDEV]
        evidence.append(Evidence(
            id=ids.next(), audit_id=None,
            metric="variability", value=", ".join(unstable), threshold=settings.VARIABILITY_FLAG_RELATIVE_STDEV,
            severity="info", evidence_strength="derived",
            description=f"High run-to-run variability detected in: {', '.join(unstable)}. "
                         f"Treat related metrics with caution.",
            tags=["stability"],
        ))

    # --- Resource/audit-level evidence, averaged over the same run window.
    # These are "derived" (the backend computed the average across N runs),
    # each carrying the single resource Lighthouse blamed most, when given.
    avg_unused_js = _mean_audit_value(runs, "unused_javascript_bytes")
    if avg_unused_js >= settings.UNUSED_JS_FLAG_BYTES:
        evidence.append(Evidence(
            id=ids.next(), audit_id="unused-javascript",
            metric="unused_javascript_bytes", value=round(avg_unused_js), threshold=settings.UNUSED_JS_FLAG_BYTES,
            severity="warning", evidence_strength="derived",
            resource=_top_resource(runs, "unused_javascript_items", "wasted_bytes"),
            description=f"Average {round(avg_unused_js/1000)}KB of unused JavaScript shipped per run "
                        f"(over {len(runs)} runs).",
            tags=["javascript", "unused-js"],
        ))

    avg_render_blocking = _mean_audit_value(runs, "render_blocking_savings_ms")
    if avg_render_blocking >= 250:
        evidence.append(Evidence(
            id=ids.next(), audit_id="render-blocking-resources",
            metric="render_blocking_savings_ms", value=round(avg_render_blocking), threshold=250,
            severity="warning", evidence_strength="derived",
            resource=_top_resource(runs, "render_blocking_items", "wasted_ms"),
            description=f"Render-blocking resources cost an average of {round(avg_render_blocking)}ms "
                        f"before first paint.",
            tags=["render-blocking"],
        ))

    avg_image_savings = _mean_audit_value(runs, "image_optimization_savings_bytes")
    if avg_image_savings >= settings.IMAGE_SAVINGS_FLAG_BYTES:
        evidence.append(Evidence(
            id=ids.next(), audit_id="uses-optimized-images",
            metric="image_optimization_savings_bytes", value=round(avg_image_savings),
            threshold=settings.IMAGE_SAVINGS_FLAG_BYTES, severity="warning", evidence_strength="derived",
            resource=_top_resource(runs, "image_optimization_items", "wasted_bytes"),
            description=f"Average {round(avg_image_savings/1000)}KB could be saved through image "
                        f"optimization/compression per run.",
            tags=["images"],
        ))

    avg_third_party = _mean_audit_value(runs, "third_party_blocking_ms")
    if avg_third_party >= settings.THIRD_PARTY_TBT_FLAG_MS:
        # Surface which entity dominates, for concreteness.
        entity_counter: Counter[str] = Counter()
        for r in runs:
            for e in r.normalized_audits.get("third_party_entities", []):
                if e.get("entity"):
                    entity_counter[e["entity"]] += float(e.get("blocking_time_ms") or 0)
        top_entity = entity_counter.most_common(1)[0][0] if entity_counter else "third-party scripts"
        evidence.append(Evidence(
            id=ids.next(), audit_id="third-party-summary",
            metric="third_party_blocking_ms", value=round(avg_third_party), threshold=settings.THIRD_PARTY_TBT_FLAG_MS,
            severity="warning", evidence_strength="derived",
            description=f"Third-party scripts (dominated by '{top_entity}') account for an average of "
                        f"{round(avg_third_party)}ms of main-thread blocking time per run.",
            tags=["third-party", "javascript"],
        ))

    # --- Layout shift sources (from the latest run, most concrete) -------
    latest = runs[-1] if runs else None
    if latest and latest.normalized_audits.get("layout_shift_sources") and cls and cls > settings.CLS_GOOD:
        sources = latest.normalized_audits["layout_shift_sources"]
        evidence.append(Evidence(
            id=ids.next(), audit_id="layout-shift-elements",
            metric="layout_shift_sources", value=", ".join(sources), severity="info", evidence_strength="direct",
            description=f"Elements contributing to layout shift in the latest run: {', '.join(sources)}.",
            tags=["cls", "layout-shift"],
        ))

    # --- Accessibility findings that appear in a majority of runs --------
    finding_counter: Counter[str] = Counter()
    finding_examples: dict[str, dict] = {}
    for r in runs:
        seen_ids = set()
        for finding in r.normalized_audits.get("accessibility_findings", []):
            fid = finding.get("id")
            if fid and fid not in seen_ids:
                finding_counter[fid] += 1
                finding_examples[fid] = finding
                seen_ids.add(fid)

    majority_threshold = max(1, len(runs) // 2)
    for fid, count in finding_counter.items():
        if count >= majority_threshold:
            finding = finding_examples[fid]
            nodes = [n for n in finding.get("affected_nodes", []) if n]
            evidence.append(Evidence(
                id=ids.next(), audit_id=fid,
                metric=f"a11y_{fid}", value=count, threshold=majority_threshold, severity="warning",
                evidence_strength="direct",
                description=f"Accessibility audit '{finding.get('title', fid)}' failed in {count}/{len(runs)} runs"
                            + (f" (e.g. {nodes[0]})" if nodes else "") + ".",
                tags=["accessibility", fid],
            ))

    return evidence
