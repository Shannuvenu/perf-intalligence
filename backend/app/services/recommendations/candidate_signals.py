"""
Rule-based root-cause candidate generation (product spec section 4/10).

This is NOT the final recommendation list - it's a deterministic first pass
that groups related Evidence into a fixed, closed set of named candidates
(each with a stable `candidate_id`) with a strength score.

The LLM (or the mock synthesizer) can ONLY pick from this list and MUST
reference evidence by the ids attached here - it is never allowed to invent
a new root cause or attach evidence that isn't in `supporting_evidence`.

Server-side validation (recommendations/validation.py) enforces that after
the LLM responds.

Critically: a candidate is only ever created when its OWN supporting audit
evidence exists.

For example:
    IMAGE_OPTIMIZATION
        -> image_optimization_savings_bytes only

    RENDER_BLOCKING
        -> render_blocking_savings_ms only

    UNUSED_JAVASCRIPT
        -> unused_javascript_bytes only

    THIRD_PARTY_BLOCKING
        -> third_party_blocking_ms only

    PAGE_WEIGHT
        -> total_bytes only

Outcome metrics such as LCP, FCP and TBT are intentionally NOT attached
to root-cause candidates because they describe outcomes, not necessarily
the root cause.

This prevents the LLM from using an outcome metric as evidence for a
specific root-cause claim.
"""

from pydantic import BaseModel

from app.services.evidence.models import Evidence


# ---------------------------------------------------------------------------
# Fixed, closed set of candidate IDs.
# ---------------------------------------------------------------------------

THIRD_PARTY_BLOCKING = "THIRD_PARTY_BLOCKING"
IMAGE_OPTIMIZATION = "IMAGE_OPTIMIZATION"
LAYOUT_SHIFT = "LAYOUT_SHIFT"
RENDER_BLOCKING = "RENDER_BLOCKING"
UNUSED_JAVASCRIPT = "UNUSED_JAVASCRIPT"
PAGE_WEIGHT = "PAGE_WEIGHT"
ACCESSIBILITY = "ACCESSIBILITY"


KNOWN_CANDIDATE_IDS = {
    THIRD_PARTY_BLOCKING,
    IMAGE_OPTIMIZATION,
    LAYOUT_SHIFT,
    RENDER_BLOCKING,
    UNUSED_JAVASCRIPT,
    PAGE_WEIGHT,
    ACCESSIBILITY,
}


# ---------------------------------------------------------------------------
# Human-readable candidate titles.
# ---------------------------------------------------------------------------

CANDIDATE_TITLES = {
    THIRD_PARTY_BLOCKING: "Heavy third-party/ad-related execution",
    IMAGE_OPTIMIZATION: "Image delivery/optimization",
    LAYOUT_SHIFT: "Layout instability",
    RENDER_BLOCKING: "Render-blocking resources on the critical path",
    UNUSED_JAVASCRIPT: "Unused/unoptimized JavaScript bundles",
    PAGE_WEIGHT: "Excessive total page weight",
    ACCESSIBILITY: "Accessibility violations (labels, alt text, contrast)",
}


# ---------------------------------------------------------------------------
# Backend-owned ease-of-fix classification.
#
# This is deliberately NOT controlled by the LLM.
#
# The LLM may describe the fix, but it must not decide how easy a candidate
# is when that value can influence final priority.
# ---------------------------------------------------------------------------

CANDIDATE_EASE_OF_FIX = {
    THIRD_PARTY_BLOCKING: "medium",
    IMAGE_OPTIMIZATION: "medium",
    LAYOUT_SHIFT: "easy",
    RENDER_BLOCKING: "medium",
    UNUSED_JAVASCRIPT: "hard",
    PAGE_WEIGHT: "medium",
    ACCESSIBILITY: "easy",
}


class CandidateSignal(BaseModel):
    candidate_id: str

    # Kept as `root_cause_hypothesis` for backward compatibility with the
    # rest of the codebase and the mock LLM's template lookup.
    #
    # This is NOT a free-form LLM-generated label.
    root_cause_hypothesis: str

    # IMPORTANT:
    # Only evidence that directly belongs to this candidate is allowed here.
    supporting_evidence: list[Evidence]

    # 0-1, sum of matched-evidence weight.
    # This is a deterministic signal for candidate strength.
    strength: float

    @property
    def evidence_refs(self) -> list[str]:
        return [e.id for e in self.supporting_evidence]


# ---------------------------------------------------------------------------
# Evidence severity weights.
# ---------------------------------------------------------------------------

_SEVERITY_WEIGHT = {
    "critical": 1.0,
    "warning": 0.6,
    "info": 0.2,
}


def _weight(evidence: list[Evidence]) -> float:
    """
    Calculate deterministic candidate strength.

    Strength is based only on the candidate's own evidence.
    """

    if not evidence:
        return 0.0

    return round(
        min(
            1.0,
            (
                sum(
                    _SEVERITY_WEIGHT.get(e.severity, 0.3)
                    for e in evidence
                )
                / len(evidence)
            )
            * min(1.0, len(evidence) / 2),
        ),
        3,
    )


def _make(
    candidate_id: str,
    evidence: list[Evidence],
) -> CandidateSignal:
    """
    Build a deterministic CandidateSignal.

    No evidence is added here automatically.
    The caller must explicitly provide the candidate's own evidence.
    """

    return CandidateSignal(
        candidate_id=candidate_id,
        root_cause_hypothesis=CANDIDATE_TITLES[candidate_id],
        supporting_evidence=evidence,
        strength=_weight(evidence),
    )


def generate_candidate_signals(
    evidence: list[Evidence],
) -> list[CandidateSignal]:
    """
    Convert deterministic Evidence objects into a closed set of
    root-cause candidates.

    IMPORTANT ARCHITECTURAL RULE:

        One candidate -> only its own root-cause evidence.

    Outcome metrics such as:

        lcp_ms
        fcp_ms
        tbt_ms

    are intentionally excluded from unrelated root-cause candidates.

    This prevents evidence leakage such as:

        IMAGE_OPTIMIZATION
            + image evidence
            + LCP evidence       <-- NOT ALLOWED

        THIRD_PARTY_BLOCKING
            + third-party evidence
            + TBT evidence       <-- NOT ALLOWED

        UNUSED_JAVASCRIPT
            + unused-JS evidence
            + TBT evidence       <-- NOT ALLOWED

        PAGE_WEIGHT
            + total-byte evidence
            + image evidence     <-- NOT ALLOWED
    """

    by_metric = {
        e.metric: e
        for e in evidence
    }

    by_tag: dict[str, list[Evidence]] = {}

    for e in evidence:
        for tag in e.tags:
            by_tag.setdefault(tag, []).append(e)

    candidates: list[CandidateSignal] = []

    # -----------------------------------------------------------------------
    # 1. Heavy third-party / ad-related execution
    #
    # ONLY actual third-party blocking evidence can create/support this
    # candidate.
    #
    # TBT alone cannot prove third-party blocking because TBT can also be
    # caused by first-party JavaScript.
    # -----------------------------------------------------------------------

    third_party_evidence = by_metric.get(
        "third_party_blocking_ms"
    )

    if third_party_evidence:
        candidates.append(
            _make(
                THIRD_PARTY_BLOCKING,
                [
                    third_party_evidence,
                ],
            )
        )

    # -----------------------------------------------------------------------
    # 2. Image delivery / optimization
    #
    # ONLY image optimization audit evidence.
    #
    # LCP is intentionally NOT attached here.
    # A poor LCP does not prove that images caused the LCP problem.
    # -----------------------------------------------------------------------

    image_evidence = by_metric.get(
        "image_optimization_savings_bytes"
    )

    if image_evidence:
        candidates.append(
            _make(
                IMAGE_OPTIMIZATION,
                [
                    image_evidence,
                ],
            )
        )

    # -----------------------------------------------------------------------
    # 3. Layout instability
    #
    # CLS directly measures layout instability, so CLS is valid evidence
    # for this candidate.
    #
    # Actual layout-shift source evidence may also be attached.
    # -----------------------------------------------------------------------

    cls_evidence = by_metric.get("cls")

    if (
        cls_evidence is not None
        and cls_evidence.severity in ("warning", "critical")
    ):
        layout_evidence = [
            e
            for e in (
                cls_evidence,
                by_metric.get("layout_shift_sources"),
            )
            if e is not None
        ]

        candidates.append(
            _make(
                LAYOUT_SHIFT,
                layout_evidence,
            )
        )

    # -----------------------------------------------------------------------
    # 4. Render-blocking resources
    #
    # ONLY actual render-blocking audit evidence.
    #
    # FCP is intentionally NOT attached because poor FCP does not itself
    # establish render-blocking resources as the cause.
    # -----------------------------------------------------------------------

    render_blocking_evidence = by_metric.get(
        "render_blocking_savings_ms"
    )

    if render_blocking_evidence:
        candidates.append(
            _make(
                RENDER_BLOCKING,
                [
                    render_blocking_evidence,
                ],
            )
        )

    # -----------------------------------------------------------------------
    # 5. Unused JavaScript
    #
    # ONLY unused JavaScript evidence.
    #
    # TBT is intentionally NOT attached because TBT does not establish that
    # unused JavaScript is the cause.
    # -----------------------------------------------------------------------

    unused_js_evidence = by_metric.get(
        "unused_javascript_bytes"
    )

    if unused_js_evidence:
        candidates.append(
            _make(
                UNUSED_JAVASCRIPT,
                [
                    unused_js_evidence,
                ],
            )
        )

    # -----------------------------------------------------------------------
    # 6. Excessive total page weight
    #
    # ONLY total-byte-weight evidence.
    #
    # Image savings are intentionally NOT attached because image optimization
    # and total page weight are separate findings.
    # -----------------------------------------------------------------------

    total_bytes_evidence = by_metric.get(
        "total_bytes"
    )

    if total_bytes_evidence:
        candidates.append(
            _make(
                PAGE_WEIGHT,
                [
                    total_bytes_evidence,
                ],
            )
        )

    # -----------------------------------------------------------------------
    # 7. Accessibility
    #
    # Accessibility evidence is already explicitly tagged by the extractor.
    # Keep all accessibility-tagged evidence together.
    # -----------------------------------------------------------------------

    a11y_evidence = by_tag.get(
        "accessibility",
        [],
    )

    if a11y_evidence:
        candidates.append(
            _make(
                ACCESSIBILITY,
                a11y_evidence,
            )
        )

    # -----------------------------------------------------------------------
    # Final safety guard:
    # never return an empty candidate.
    # -----------------------------------------------------------------------

    return [
        candidate
        for candidate in candidates
        if candidate.supporting_evidence
    ]