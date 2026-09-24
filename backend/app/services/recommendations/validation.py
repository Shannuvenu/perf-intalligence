"""
Hard server-side validation of LLM output.

The LLM is never trusted to determine whether a recommendation is
supported or how urgent it is.

Responsibilities of this module:

1. Verify candidate_id belongs to a deterministic candidate generated
   for THIS run.

2. Verify every evidence_ref exists in the evidence supplied for THIS run.

3. Verify every evidence_ref belongs to that candidate's own evidence set.

4. Reject duplicate recommendations for the same candidate_id.

5. Resolve server-owned fields from deterministic evidence:
   - root_cause
   - evidence
   - resources
   - affected_audits

6. Override LLM-reported priority-driving fields:
   - impact
   - ease_of_fix
   - confidence

The design principle is:

    PageSpeed evidence -> deterministic backend decision
    LLM -> explanation / wording only

The LLM must never be able to change priority simply by saying:
    impact = high
    ease_of_fix = easy
    confidence = 1.0
"""

import logging

from app.core.config import Settings, get_settings
from app.schemas.recommendation import (
    LlmRecommendationSet,
    RecommendationItem,
)
from app.services.evidence.models import Evidence
from app.services.recommendations.candidate_signals import (
    CANDIDATE_EASE_OF_FIX,
    CandidateSignal,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Evidence-strength -> deterministic confidence
# ---------------------------------------------------------------------------
#
# The weakest evidence referenced by a recommendation determines the
# confidence.
#
# IMPORTANT:
# This is NOT a cap anymore.
#
# The LLM's confidence is completely ignored.
#
# Example:
#   LLM says confidence = 0.10
#   evidence_strength = direct
#
# Result:
#   confidence = 1.0
#
# Example:
#   LLM says confidence = 1.0
#   evidence_strength = insufficient
#
# Result:
#   confidence = 0.4
#
# This guarantees that the same evidence always produces the same
# confidence regardless of what the LLM says.
# ---------------------------------------------------------------------------

_STRENGTH_CONFIDENCE = {
    "direct": 1.0,
    "derived": 0.85,
    "insufficient": 0.4,
}


# ---------------------------------------------------------------------------
# Deterministic impact
# ---------------------------------------------------------------------------

def _deterministic_impact(candidate: CandidateSignal) -> str:
    """
    Determine impact from the candidate's actual supporting evidence.

    The LLM's reported impact is ignored.

    Rules:
        critical evidence -> high
        warning evidence  -> medium
        everything else   -> low
    """

    severities = {
        evidence_item.severity
        for evidence_item in candidate.supporting_evidence
    }

    if "critical" in severities:
        return "high"

    if "warning" in severities:
        return "medium"

    return "low"


# ---------------------------------------------------------------------------
# Deterministic confidence
# ---------------------------------------------------------------------------

def _deterministic_confidence(
    candidate: CandidateSignal,
) -> float:
    """
    Determine confidence exclusively from evidence strength.

    The weakest supporting evidence wins.

    Example:

        direct + derived
        -> min(1.0, 0.85)
        -> 0.85

    Example:

        direct + insufficient
        -> min(1.0, 0.4)
        -> 0.4
    """

    if not candidate.supporting_evidence:
        return 0.0

    return min(
        _STRENGTH_CONFIDENCE.get(
            evidence_item.evidence_strength,
            0.7,
        )
        for evidence_item in candidate.supporting_evidence
    )


# ---------------------------------------------------------------------------
# Rejection logging
# ---------------------------------------------------------------------------

def _reject(
    candidate_id: str,
    reason: str,
) -> None:
    logger.warning(
        "LLM recommendation rejected: candidate_id=%s reason=%s",
        candidate_id,
        reason,
    )


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------

def validate_and_resolve(
    result: LlmRecommendationSet,
    evidence: list[Evidence],
    candidates: list[CandidateSignal],
    settings: Settings | None = None,
) -> tuple[list[RecommendationItem], str, str | None]:
    """
    Validate LLM recommendations against deterministic evidence.

    Returns:

        (
            validated_items,
            validation_status,
            insufficient_evidence_note,
        )

    validation_status is one of:

        "valid"
        "needs_review"

    A recommendation is accepted only when ALL of the following are true:

        1. candidate_id exists in deterministic candidates.
        2. every evidence_ref exists in supplied evidence.
        3. every evidence_ref belongs to that candidate.
        4. candidate has not already been recommended.

    Server-owned fields are then resolved deterministically.
    """

    settings = settings or get_settings()

    # ------------------------------------------------------------------
    # Build fast lookup tables.
    # ------------------------------------------------------------------

    evidence_by_id = {
        evidence_item.id: evidence_item
        for evidence_item in evidence
    }

    candidates_by_id = {
        candidate.candidate_id: candidate
        for candidate in candidates
    }

    # ------------------------------------------------------------------
    # Output state.
    # ------------------------------------------------------------------

    valid_items: list[RecommendationItem] = []

    seen_candidate_ids: set[str] = set()

    any_rejected = False

    # ------------------------------------------------------------------
    # Validate every LLM recommendation.
    # ------------------------------------------------------------------

    for item in result.recommendations:

        # ==============================================================
        # CHECK 1
        # candidate_id must have been generated by the deterministic
        # candidate generator for THIS run.
        # ==============================================================

        candidate = candidates_by_id.get(item.candidate_id)

        if candidate is None:
            _reject(
                item.candidate_id,
                "candidate was not generated from PageSpeed evidence for this run",
            )

            any_rejected = True
            continue

        # ==============================================================
        # CHECK 2
        # Only one recommendation per candidate_id.
        # ==============================================================

        if item.candidate_id in seen_candidate_ids:
            _reject(
                item.candidate_id,
                "duplicate recommendation for the same candidate_id",
            )

            any_rejected = True
            continue

        # ==============================================================
        # CHECK 3
        # Every evidence_ref must exist in THIS run's evidence.
        # ==============================================================

        candidate_ref_set = {
            evidence_item.id
            for evidence_item in candidate.supporting_evidence
        }

        bad_ref = next(
            (
                ref
                for ref in item.evidence_refs
                if ref not in evidence_by_id
            ),
            None,
        )

        if bad_ref is not None:
            _reject(
                item.candidate_id,
                f"evidence_ref {bad_ref} does not exist",
            )

            any_rejected = True
            continue

        # ==============================================================
        # CHECK 4
        # Evidence must belong to THIS candidate.
        #
        # This prevents:
        #
        # IMAGE_OPTIMIZATION
        #     -> borrowing LCP evidence
        #
        # THIRD_PARTY_BLOCKING
        #     -> borrowing unused JS evidence
        #
        # etc.
        # ==============================================================

        foreign_ref = next(
            (
                ref
                for ref in item.evidence_refs
                if ref not in candidate_ref_set
            ),
            None,
        )

        if foreign_ref is not None:
            _reject(
                item.candidate_id,
                f"evidence_ref {foreign_ref} does not belong to this candidate",
            )

            any_rejected = True
            continue

        # ==============================================================
        # Recommendation passed all validation checks.
        # Resolve everything from actual Evidence objects.
        # ==============================================================

        resolved = [
            evidence_by_id[ref]
            for ref in item.evidence_refs
        ]

        # --------------------------------------------------------------
        # Server-owned root cause
        # --------------------------------------------------------------

        item.root_cause = candidate.root_cause_hypothesis

        # --------------------------------------------------------------
        # Server-owned evidence descriptions
        # --------------------------------------------------------------

        item.evidence = [
            evidence_item.description
            for evidence_item in resolved
        ]

        # --------------------------------------------------------------
        # Server-owned resources
        # --------------------------------------------------------------

        item.resources = sorted(
            {
                evidence_item.resource
                for evidence_item in resolved
                if evidence_item.resource
            }
        )

        # --------------------------------------------------------------
        # Server-owned affected audits
        # --------------------------------------------------------------

        item.affected_audits = sorted(
            {
                evidence_item.audit_id or evidence_item.metric
                for evidence_item in resolved
            }
        )

        # ==============================================================
        # CRITICAL SAFETY RULE
        #
        # Do NOT trust:
        #
        #     item.impact
        #     item.ease_of_fix
        #     item.confidence
        #
        # These came from the LLM.
        #
        # Replace all three with deterministic backend values.
        # ==============================================================

        # --------------------------------------------------------------
        # Deterministic impact
        # --------------------------------------------------------------

        item.impact = _deterministic_impact(candidate)

        # --------------------------------------------------------------
        # Deterministic ease of fix
        # --------------------------------------------------------------
        #
        # This mapping belongs to the backend, not the LLM.
        # --------------------------------------------------------------

        item.ease_of_fix = CANDIDATE_EASE_OF_FIX.get(
            item.candidate_id,
            "medium",
        )

        # --------------------------------------------------------------
        # Deterministic confidence
        # --------------------------------------------------------------

        item.confidence = _deterministic_confidence(candidate)

        # --------------------------------------------------------------
        # Mark candidate as accepted.
        # --------------------------------------------------------------

        seen_candidate_ids.add(item.candidate_id)

        valid_items.append(item)

    # ------------------------------------------------------------------
    # No valid recommendations.
    # ------------------------------------------------------------------

    if not valid_items:

        note = result.insufficient_evidence_note

        if not note:
            if not candidates:
                note = (
                    "No candidate root-cause signals were generated "
                    "from the available PageSpeed evidence - metrics "
                    "may already be within healthy thresholds."
                )
            else:
                note = (
                    "No recommendation could be validated against "
                    "the available PageSpeed evidence."
                )

        # Zero recommendations is a successful pipeline result.
        #
        # If recommendations were rejected, flag needs_review so the
        # system can surface that the LLM repeatedly produced unsupported
        # output.
        #
        # This is NOT a pipeline error.
        status = (
            "needs_review"
            if any_rejected
            else "valid"
        )

        return [], status, note

    # ------------------------------------------------------------------
    # Evidence-driven review status.
    # ------------------------------------------------------------------
    #
    # Confidence is now deterministic, so this check is based entirely
    # on evidence strength.
    # ------------------------------------------------------------------

    low_confidence = any(
        item.confidence
        < settings.RECOMMENDATION_NEEDS_REVIEW_CONFIDENCE
        for item in valid_items
    )

    status = (
        "needs_review"
        if any_rejected or low_confidence
        else "valid"
    )

    return (
        valid_items,
        status,
        result.insufficient_evidence_note,
    )