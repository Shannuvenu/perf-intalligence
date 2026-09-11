from abc import ABC, abstractmethod

from app.schemas.recommendation import LlmRecommendationSet
from app.services.evidence.models import Evidence
from app.services.recommendations.candidate_signals import CandidateSignal


class LlmProviderError(Exception):
    """Raised when the LLM call fails or its output can't be parsed at all
    (network error, invalid JSON, empty response)."""


class LlmSynthesisProvider(ABC):
    model_name: str

    @abstractmethod
    async def synthesize(
        self, evidence: list[Evidence], candidates: list[CandidateSignal]
    ) -> LlmRecommendationSet:
        raise NotImplementedError
