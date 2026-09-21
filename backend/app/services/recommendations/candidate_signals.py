"""
Rule-based root-cause candidate generation (product spec section 10).

This is NOT the final recommendation list - it's a deterministic first pass
that groups related Evidence into named hypotheses with a strength score.
The LLM (or the mock synthesizer) takes these candidates + the raw evidence
and produces the final ranked, worded recommendations. This keeps root-cause
naming grounded in rules we control, while still letting the LLM do the
synthesis/writing/ranking work it's actually good at.
"""
from pydantic import BaseModel

from app.services.evidence.models import Evidence


class CandidateSignal(BaseModel):
    root_cause_hypothesis: str
    supporting_evidence: list[Evidence]
    strength: float  # 0-1, sum of matched-evidence weight, for LLM ranking hints only


_SEVERITY_WEIGHT = {"critical": 1.0, "warning": 0.6, "info": 0.2}


def _weight(evidence: list[Evidence]) -> float:
    if not evidence:
        return 0.0
    return round(min(1.0, sum(_SEVERITY_WEIGHT.get(e.severity, 0.3) for e in evidence) / len(evidence) *
                      min(1.0, len(evidence) / 2)), 3)


def generate_candidate_signals(evidence: list[Evidence]) -> list[CandidateSignal]:
    by_metric = {e.metric: e for e in evidence}
    by_tag: dict[str, list[Evidence]] = {}
    for e in evidence:
        for tag in e.tags:
            by_tag.setdefault(tag, []).append(e)

    candidates: list[CandidateSignal] = []

    # 1. Heavy third-party / ad-related execution
    tp_evidence = [e for e in (by_metric.get("third_party_blocking_ms"), by_metric.get("tbt_ms"))
                   if e is not None] + by_tag.get("unused-js", [])
    if by_metric.get("third_party_blocking_ms"):
        candidates.append(CandidateSignal(
            root_cause_hypothesis="Heavy third-party/ad-related execution",
            supporting_evidence=tp_evidence,
            strength=_weight(tp_evidence),
        ))

    # 2. Image delivery/optimization
    img_evidence = [e for e in (by_metric.get("image_optimization_savings_bytes"), by_metric.get("lcp_ms"))
                     if e is not None]
    if by_metric.get("image_optimization_savings_bytes"):
        candidates.append(CandidateSignal(
            root_cause_hypothesis="Image delivery/optimization",
            supporting_evidence=img_evidence,
            strength=_weight(img_evidence),
        ))

    # 3. Layout instability
    layout_evidence = [e for e in (by_metric.get("cls"), by_metric.get("layout_shift_sources")) if e is not None]
    if by_metric.get("cls") is not None and by_metric["cls"].severity in ("warning", "critical"):
        candidates.append(CandidateSignal(
            root_cause_hypothesis="Layout instability",
            supporting_evidence=layout_evidence,
            strength=_weight(layout_evidence),
        ))

    # 4. Render-blocking resources / unoptimized critical path
    rb_evidence = [e for e in (by_metric.get("render_blocking_savings_ms"), by_metric.get("fcp_ms")) if e is not None]
    if by_metric.get("render_blocking_savings_ms"):
        candidates.append(CandidateSignal(
            root_cause_hypothesis="Render-blocking resources on the critical path",
            supporting_evidence=rb_evidence,
            strength=_weight(rb_evidence),
        ))

    # 5. Excess/unminified JavaScript
    js_evidence = [e for e in (by_metric.get("unused_javascript_bytes"), by_metric.get("tbt_ms")) if e is not None]
    if by_metric.get("unused_javascript_bytes"):
        candidates.append(CandidateSignal(
            root_cause_hypothesis="Unused/unoptimized JavaScript bundles",
            supporting_evidence=js_evidence,
            strength=_weight(js_evidence),
        ))


    # 7. Excessive total page weight (bandwidth)
    bw_evidence = [e for e in (by_metric.get("total_bytes"), by_metric.get("image_optimization_savings_bytes"))
                   if e is not None]
    if by_metric.get("total_bytes"):
        candidates.append(CandidateSignal(
            root_cause_hypothesis="Excessive total page weight",
            supporting_evidence=bw_evidence,
            strength=_weight(bw_evidence),
        ))

    return [c for c in candidates if c.supporting_evidence]
