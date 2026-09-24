"""
Groq-backed LLM synthesis provider.

Uses Groq's OpenAI-compatible API with strict Structured Outputs. The
response is constrained to reference evidence only by id (evidence_refs) and
to pick candidate_id only from the fixed, closed set the rule engine can
ever produce (see candidate_signals.KNOWN_CANDIDATE_IDS) - never free-form
evidence text. Every field is then re-validated by Pydantic, and every
evidence_ref/candidate_id is re-checked against what was actually supplied
for THIS run by recommendations/validation.py before anything reaches a user.
"""

import json

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.schemas.recommendation import LlmRecommendationSet
from app.services.evidence.models import Evidence
from app.services.llm.base import LlmProviderError, LlmSynthesisProvider
from app.services.llm.prompts import SYSTEM_PROMPT, build_user_payload
from app.services.recommendations.candidate_signals import KNOWN_CANDIDATE_IDS, CandidateSignal

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

        This mirrors LlmRecommendationSet / RecommendationItem's
        LLM-provided fields only - `root_cause`, `evidence`, `resources` and
        `affected_audits` are resolved server-side after validation and are
        deliberately NOT part of what the model is asked to produce, so
        there is no free-text field left for it to fabricate evidence in.

        Groq strict mode requires:
        - every property to be required
        - additionalProperties=false
        - optional values represented using null
        """

        recommendation_item = {
            "type": "object",
            "properties": {
                "candidate_id": {
                    "type": "string",
                    "enum": sorted(KNOWN_CANDIDATE_IDS),
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
                "evidence_refs": {
                    "type": "array",
                    "items": {
                        "type": "string",
                    },
                    "minItems": 1,
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
            },
            "required": [
                "candidate_id",
                "summary",
                "problem_explanation",
                "user_impact",
                "fix_steps",
                "evidence_refs",
                "impact",
                "ease_of_fix",
                "confidence",
                "suggested_fix",
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
        page_metrics: dict | None = None,
    ) -> LlmRecommendationSet:

        user_payload = build_user_payload(
            page_metrics=page_metrics or {},
            evidence=[e.model_dump() for e in evidence],
            candidates=[
                {
                    "candidate_id": c.candidate_id,
                    "title": c.root_cause_hypothesis,
                    "evidence_refs": c.evidence_refs,
                }
                for c in candidates
            ],
        )

        system_prompt = f"""
{SYSTEM_PROMPT}

IMPORTANT RULES:

1. Return only the structured recommendation response.
2. Never invent a candidate_id that is not in supported_candidates for this run.
3. Every recommendation must reference evidence_refs that belong to that exact candidate.
4. Every recommendation must contain every field.
5. fix_steps must contain ONLY strings.
6. evidence_refs must contain ONLY evidence id strings (e.g. "E01") taken from the supplied evidence.
7. problem_explanation may be a string or null.
8. user_impact may be a string or null.
9. insufficient_evidence_note may be a string or null.
10. confidence must be between 0.0 and 1.0.
11. impact must be exactly one of: high, medium, low.
12. ease_of_fix must be exactly one of: easy, medium, hard.
13. Do not add fields that are not defined by the schema.
14. Do not return Markdown.
15. At most one recommendation per candidate_id - never duplicate a candidate.
16. If supported_candidates is empty, return recommendations: [] with a clear insufficient_evidence_note.
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
