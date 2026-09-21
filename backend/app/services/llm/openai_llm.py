"""
Gemini-backed LLM synthesis provider.

This provider uses Google's Gemini API through its OpenAI-compatible
endpoint, allowing the existing OpenAI Python SDK integration to remain
unchanged.

The model response is parsed as JSON and validated against
LlmRecommendationSet before it is trusted.
"""

import json

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.schemas.recommendation import LlmRecommendationSet
from app.services.evidence.models import Evidence
from app.services.llm.base import LlmProviderError, LlmSynthesisProvider
from app.services.llm.prompts import SYSTEM_PROMPT, build_user_payload
from app.services.recommendations.candidate_signals import CandidateSignal


# Gemini OpenAI-compatible API endpoint.
GEMINI_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/openai/"
)


_JSON_SCHEMA_HINT = """
Respond with a JSON object of exactly this shape:

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
}
"""


class OpenAiLlmProvider(LlmSynthesisProvider):
    """
    Gemini provider using the OpenAI-compatible API.

    The class name is intentionally kept as OpenAiLlmProvider so existing
    imports in the project continue to work without additional changes.
    """

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise LlmProviderError(
                "LLM_PROVIDER=gemini but GEMINI_API_KEY is not set. "
                "Set GEMINI_API_KEY in .env or switch "
                "LLM_PROVIDER back to 'mock'."
            )

        self.model_name = model

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=GEMINI_BASE_URL,
        )

    async def synthesize(
        self,
        evidence: list[Evidence],
        candidates: list[CandidateSignal],
    ) -> LlmRecommendationSet:

        user_payload = build_user_payload(
            evidence=[e.model_dump() for e in evidence],
            candidates=[c.model_dump() for c in candidates],
        )

        try:
            response = await self._client.chat.completions.create(
                model=self.model_name,

                # Gemini 3.8 Flash supports reasoning_effort through
                # Google's OpenAI-compatible API.
                reasoning_effort="low",

                # Ask Gemini for JSON because the response is validated
                # against LlmRecommendationSet below.
                response_format={"type": "json_object"},

                messages=[
                    {
                        "role": "system",
                        "content": (
                            SYSTEM_PROMPT
                            + "\n\n"
                            + _JSON_SCHEMA_HINT
                        ),
                    },
                    {
                        "role": "user",
                        "content": user_payload,
                    },
                ],
            )

        except Exception as exc:
            raise LlmProviderError(
                f"Gemini API call failed: {exc}"
            ) from exc

        # Safely extract the model response.
        content = (
            response.choices[0].message.content
            if response.choices
            else None
        )

        if not content:
            raise LlmProviderError(
                "Gemini response contained no content."
            )

        # Parse Gemini's JSON response.
        try:
            parsed = json.loads(content)

        except json.JSONDecodeError as exc:
            raise LlmProviderError(
                f"Gemini response was not valid JSON: {exc}"
            ) from exc

        # Validate the JSON against the application's schema.
        try:
            return LlmRecommendationSet.model_validate(parsed)

        except ValidationError as exc:
            raise LlmProviderError(
                f"Gemini response failed schema validation: {exc}"
            ) from exc