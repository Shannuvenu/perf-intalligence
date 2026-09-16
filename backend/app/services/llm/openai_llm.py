"""
Real OpenAI-backed synthesis provider. Uses JSON-mode chat completions and
validates the response against LlmRecommendationSet before it's ever trusted
- an invalid/malformed model response raises LlmProviderError, which the
caller (recommendation_service) turns into validation_status="invalid"
rather than crashing the request.
"""
import json

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.schemas.recommendation import LlmRecommendationSet
from app.services.evidence.models import Evidence
from app.services.llm.base import LlmProviderError, LlmSynthesisProvider
from app.services.llm.prompts import SYSTEM_PROMPT, build_user_payload
from app.services.recommendations.candidate_signals import CandidateSignal

_JSON_SCHEMA_HINT = """Respond with a JSON object of exactly this shape:
{
  "recommendations": [
    {
      "root_cause": "string",
      "summary": "string",
      "problem_explanation": "string - what is happening and why, several sentences",
      "user_impact": "string - what the reader/business loses",
      "fix_steps": ["ordered concrete action", "..."],
      "evidence": ["string", "..."],
      "affected_audits": ["string", "..."],
      "impact": "high" | "medium" | "low",
      "ease_of_fix": "easy" | "medium" | "hard",
      "confidence": 0.0-1.0,
      "suggested_fix": "string"
    }
  ],
  "insufficient_evidence_note": "string or null"
}"""


class OpenAiLlmProvider(LlmSynthesisProvider):
    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise LlmProviderError(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set. Set it in .env or switch "
                "LLM_PROVIDER back to 'mock'."
            )
        self.model_name = model
        self._client = AsyncOpenAI(api_key=api_key)

    async def synthesize(
        self, evidence: list[Evidence], candidates: list[CandidateSignal]
    ) -> LlmRecommendationSet:
        user_payload = build_user_payload(
            evidence=[e.model_dump() for e in evidence],
            candidates=[c.model_dump() for c in candidates],
        )

        try:
            response = await self._client.chat.completions.create(
                model=self.model_name,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + _JSON_SCHEMA_HINT},
                    {"role": "user", "content": user_payload},
                ],
                temperature=0.2,
            )
        except Exception as exc:  # openai SDK raises several exception types; normalize them
            raise LlmProviderError(f"OpenAI API call failed: {exc}") from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise LlmProviderError("OpenAI response contained no content.")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LlmProviderError(f"OpenAI response was not valid JSON: {exc}") from exc

        try:
            return LlmRecommendationSet.model_validate(parsed)
        except ValidationError as exc:
            raise LlmProviderError(f"OpenAI response failed schema validation: {exc}") from exc
