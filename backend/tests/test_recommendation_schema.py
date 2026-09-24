import pytest
from pydantic import ValidationError

from app.schemas.recommendation import LlmRecommendationSet, RecommendationItem
from app.services.recommendations.candidate_signals import THIRD_PARTY_BLOCKING


def _valid_item(**overrides):
    base = dict(
        candidate_id=THIRD_PARTY_BLOCKING,
        summary="Third-party ad scripts are blocking the main thread for a significant duration.",
        evidence_refs=["E01", "E02"],
        impact="high",
        ease_of_fix="medium",
        confidence=0.82,
        suggested_fix="Defer non-critical third-party tags until after first paint.",
    )
    base.update(overrides)
    return base


def test_valid_recommendation_item_parses():
    item = RecommendationItem(**_valid_item())
    assert item.priority is None  # not assigned yet - priority engine's job
    assert item.impact == "high"
    # Server-resolved fields default empty until validation.py fills them.
    assert item.evidence == []
    assert item.root_cause == ""


def test_recommendation_rejects_unknown_candidate_id():
    with pytest.raises(ValidationError):
        RecommendationItem(**_valid_item(candidate_id="ADS_ARE_BAD"))


def test_recommendation_rejects_empty_evidence_refs():
    with pytest.raises(ValidationError):
        RecommendationItem(**_valid_item(evidence_refs=[]))


def test_recommendation_rejects_blank_only_evidence_refs():
    with pytest.raises(ValidationError):
        RecommendationItem(**_valid_item(evidence_refs=["   ", ""]))


def test_recommendation_rejects_invalid_impact_value():
    with pytest.raises(ValidationError):
        RecommendationItem(**_valid_item(impact="catastrophic"))


def test_recommendation_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        RecommendationItem(**_valid_item(confidence=1.5))
    with pytest.raises(ValidationError):
        RecommendationItem(**_valid_item(confidence=-0.1))


def test_recommendation_rejects_too_short_suggested_fix():
    with pytest.raises(ValidationError):
        RecommendationItem(**_valid_item(suggested_fix="fix it"))


def test_llm_recommendation_set_allows_empty_with_note():
    result = LlmRecommendationSet(
        recommendations=[], insufficient_evidence_note="Not enough evidence to make a confident call."
    )
    assert result.recommendations == []


def test_llm_recommendation_set_rejects_malformed_nested_item():
    with pytest.raises(ValidationError):
        LlmRecommendationSet.model_validate({
            "recommendations": [{"candidate_id": THIRD_PARTY_BLOCKING}],  # missing every other required field
        })
