"""
Groq-backed LLM synthesis provider.

Uses Groq's OpenAI-compatible API with strict Structured Outputs.

The model response is constrained to the application's JSON schema
before it is validated by Pydantic.
"""

import json

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.schemas.recommendation import LlmRecommendationSet
from app.services.evidence.models import Evidence
from app.services.llm.base import LlmProviderError, LlmSynthesisProvider
from app.services.llm.prompts import SYSTEM_PROMPT, build_user_payload
from app.services.recommendations.candidate_signals import CandidateSignal


GROQ_BASE_URL = "https://api.groq.com/openai/v1"


class OpenAiLlmProvider(LlmSynthesisProvider):
    """
    Groq provider using the OpenAI-compatible API.

    The class name is intentionally kept as OpenAiLlmProvider so
    existing imports continue to work.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = GROQ_BASE_URL,
    ) -> None:
        if not api_key:
            raise LlmProviderError(
                "LLM_PROVIDER=groq but GROQ_API_KEY is not set. "
                "Set GROQ_API_KEY in .env or switch "
                "LLM_PROVIDER back to 'mock'."
            )

        self.model_name = model

        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def _build_json_schema(self) -> dict:
        """
        Build the strict JSON schema used by Groq Structured Outputs.

        Every field is required because strict mode requires all
        properties to appear in the required list.
        """

        return {
            "type": "object",
            "properties": {
                "recommendations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "root_cause": {
                                "type": "string"
                            },
                            "summary": {
                                "type": "string"
                            },
                            "problem_explanation": {
                                "type": "string"
                            },
                            "user_impact": {
                                "type": "string"
                            },
                            "fix_steps": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "evidence": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "affected_audits": {
                                "type": "array",
                                "items": {
                                    "type": "string"
                                }
                            },
                            "impact": {
                                "type": "string",
                                "enum": [
                                    "high",
                                    "medium",
                                    "low",
                                ],
                            },
                            "ease_of_fix": {
                                "type": "string",
                                "enum": [
                                    "easy",
                                    "medium",
                                    "hard",
                                ],
                            },
                            "confidence": {
                                "type": "number",
                                "minimum": 0.0,
                                "maximum": 1.0,
                            },
                            "suggested_fix": {
                                "type": "string"
                            },
                        },
                        "required": [
                            "root_cause",
                            "summary",
                            "problem_explanation",
                            "user_impact",
                            "fix_steps",
                            "evidence",
                            "affected_audits",
                            "impact",
                            "ease_of_fix",
                            "confidence",
                            "suggested_fix",
                        ],
                        "additionalProperties": False,
                    },
                },
                "insufficient_evidence_note": {
                    "type": [
                        "string",
                        "null",
                    ]
                },
            },
            "required": [
                "recommendations",
                "insufficient_evidence_note",
            ],
            "additionalProperties": False,
        }

    async def synthesize(
        self,
        evidence: list[Evidence],
        candidates: list[CandidateSignal],
    ) -> LlmRecommendationSet:

        user_payload = build_user_payload(
            evidence=[
                e.model_dump()
                for e in evidence
            ],
            candidates=[
                c.model_dump()
                for c in candidates
            ],
        )

        system_prompt = f"""
{SYSTEM_PROMPT}

IMPORTANT OUTPUT RULES:

- Return recommendations ONLY from the supplied evidence.
- Never invent a PageSpeed problem.
- Every recommendation must have concrete evidence.
- Every recommendation must contain every required field.
- fix_steps MUST be an array of strings.
- evidence MUST be an array of strings.
- affected_audits MUST be an array of strings.
- confidence MUST be between 0.0 and 1.0.
- impact MUST be high, medium, or low.
- ease_of_fix MUST be easy, medium, or hard.
- If there is insufficient evidence, use the
  insufficient_evidence_note field.
- Do not put explanations outside the structured response.
"""

        try:
            response = await self._client.chat.completions.create(
                model=self.model_name,

                reasoning_effort="low",


                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "llm_recommendation_set",
                        "strict": True,
                        "schema": self._build_json_schema(),
                    },
                },

                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_payload,
                    },
                ],
            )

        except Exception as exc:
            raise LlmProviderError(
                f"Groq API call failed: {exc}"
            ) from exc

        if not response.choices:
            raise LlmProviderError(
                "Groq response contained no choices."
            )

        content = response.choices[0].message.content

        if not content:
            raise LlmProviderError(
                "Groq response contained no content."
            )

        try:
            parsed = json.loads(content)

        except json.JSONDecodeError as exc:
            raise LlmProviderError(
                f"Groq response was not valid JSON: {exc}"
            ) from exc

        try:
            return LlmRecommendationSet.model_validate(
                parsed
            )

        except ValidationError as exc:
            raise LlmProviderError(
                f"Groq response failed schema validation: {exc}"
            ) from exc