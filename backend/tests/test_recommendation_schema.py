import pytest
from pydantic import ValidationError

from app.schemas.recommendation import LlmRecommendationSet, RecommendationItem


def _valid_item(**overrides):
    base = dict(
        root_cause="Heavy third-party/ad-related execution",
        summary="Third-party ad scripts are blocking the main thread for a significant duration.",
        evidence=["Median TBT is 620ms across 5 runs (poor threshold: 600ms)."],
        affected_audits=["tbt_ms", "third_party_blocking_ms"],
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


def test_recommendation_rejects_empty_evidence_list():
    with pytest.raises(ValidationError):
        RecommendationItem(**_valid_item(evidence=[]))


def test_recommendation_rejects_blank_only_evidence_entries():
    with pytest.raises(ValidationError):
        RecommendationItem(**_valid_item(evidence=["   ", ""]))


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
            "recommendations": [{"root_cause": "X"}],  # missing every other required field
        })
