"""
Transparent priority engine (product spec section 13).

Priority is computed by US from three inputs the LLM already had to state
per-recommendation - impact, ease_of_fix, confidence - never a raw score the
model invents. That keeps "why is this P1?" answerable in one sentence.

    score = 0.5*impact + 0.3*ease + 0.2*confidence      (weights in config.py)

  impact:      high=1.0   medium=0.6   low=0.3
  ease_of_fix: easy=1.0   medium=0.6   hard=0.3   (easier fix -> higher priority)
  confidence:  the model's own 0-1 confidence, used as-is

  score >= 0.75  -> P0 (Critical)
  score >= 0.55  -> P1 (High)
  score >= 0.35  -> P2 (Medium)
  else           -> P3 (Low)
"""
from app.core.config import Settings, get_settings
from app.schemas.recommendation import RecommendationItem

_IMPACT_WEIGHT = {"high": 1.0, "medium": 0.6, "low": 0.3}
_EASE_WEIGHT = {"easy": 1.0, "medium": 0.6, "hard": 0.3}


def compute_priority_score(item: RecommendationItem, settings: Settings | None = None) -> float:
    settings = settings or get_settings()
    score = (
        settings.PRIORITY_IMPACT_WEIGHT * _IMPACT_WEIGHT[item.impact]
        + settings.PRIORITY_EASE_WEIGHT * _EASE_WEIGHT[item.ease_of_fix]
        + settings.PRIORITY_CONFIDENCE_WEIGHT * item.confidence
    )
    return round(score, 4)


def score_to_rank(score: float) -> str:
    if score >= 0.75:
        return "P0"
    if score >= 0.55:
        return "P1"
    if score >= 0.35:
        return "P2"
    return "P3"


def assign_priorities(items: list[RecommendationItem], settings: Settings | None = None) -> list[RecommendationItem]:
    """Mutates and returns items with `.priority` set, sorted most urgent first."""
    settings = settings or get_settings()
    scored = [(compute_priority_score(item, settings), item) for item in items]
    for score, item in scored:
        item.priority = score_to_rank(score)
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored]


def overall_priority_rank(items: list[RecommendationItem]) -> str:
    """The single most urgent rank across a recommendation set (for the
    llm_recommendations.priority_rank summary column)."""
    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    if not items:
        return "P3"
    return min((item.priority or "P3" for item in items), key=lambda r: order.get(r, 3))
