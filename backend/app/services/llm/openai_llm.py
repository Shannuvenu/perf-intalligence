"""
Groq-backed LLM synthesis provider.

Uses Groq's OpenAI-compatible API with strict Structured Outputs.

The response is constrained to the same shape expected by
LlmRecommendationSet and then validated by Pydantic.
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

    The class name remains OpenAiLlmProvider so existing imports
    throughout the application continue to work.
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

    @staticmethod
    def _build_json_schema() -> dict:
        """
        JSON Schema for Groq Structured Outputs.

        This mirrors LlmRecommendationSet / RecommendationItem.

        Groq strict mode requires:
        - every property to be required
        - additionalProperties=false
        - optional values represented using null
        """

        recommendation_item = {
            "type": "object",
            "properties": {
                "root_cause": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 200,
                },
                "summary": {
                    "type": "string",
                    "minLength": 10,
                    "maxLength": 1000,
                },
                "problem_explanation": {
                    "type": ["string", "null"],
                    "maxLength": 3000,
                },
                "user_impact": {
                    "type": ["string", "null"],
                    "maxLength": 2000,
                },
                "fix_steps": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                },
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                    "minItems": 1,
                },
                "affected_audits": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
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
                    "type": "string",
                    "minLength": 10,
                    "maxLength": 2000,
                },
                "priority": {
                    "type": ["string", "null"],
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
                "priority",
            ],
            "additionalProperties": False,
        }

        return {
            "type": "object",
            "properties": {
                "recommendations": {
                    "type": "array",
                    "items": recommendation_item,
                },
                "insufficient_evidence_note": {
                    "type": ["string", "null"],
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

IMPORTANT RULES:

1. Return only the structured recommendation response.
2. Never invent a problem that is not supported by the supplied evidence.
3. Every recommendation must be directly supported by evidence.
4. Every recommendation must contain every field.
5. fix_steps must contain ONLY strings.
6. evidence must contain ONLY strings.
7. affected_audits must contain ONLY strings.
8. problem_explanation may be a string or null.
9. user_impact may be a string or null.
10. priority may be a string or null.
11. insufficient_evidence_note may be a string or null.
12. confidence must be between 0.0 and 1.0.
13. impact must be exactly one of: high, medium, low.
14. ease_of_fix must be exactly one of: easy, medium, hard.
15. Do not add fields that are not defined by the schema.
16. Do not return Markdown.
17. Keep the recommendations evidence-backed and actionable.
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
            return LlmRecommendationSet.model_validate(parsed)

        except ValidationError as exc:
            raise LlmProviderError(
                f"Groq response failed schema validation: {exc}"
            ) from exc