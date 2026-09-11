"""
Deterministic mock "LLM" synthesizer - lets the whole app be demoed without
an OpenAI key. It performs the same synthesis job a real LLM call would (turn
candidate signals + evidence into worded, ranked recommendations) using
fixed templates keyed by root_cause_hypothesis, so behavior is reproducible.
"""
from app.schemas.recommendation import LlmRecommendationSet, RecommendationItem
from app.services.evidence.models import Evidence
from app.services.llm.base import LlmSynthesisProvider
from app.services.llm.prompts import PROMPT_VERSION
from app.services.recommendations.candidate_signals import CandidateSignal

_TEMPLATES: dict[str, dict] = {
    "Heavy third-party/ad-related execution": {
        "summary": "Third-party scripts (ad tech, analytics) are consuming a large share of main-thread "
                    "time, degrading TBT and delaying interactivity.",
        "suggested_fix": "Defer or lazy-load non-critical third-party tags until after first paint, load ad "
                          "slots asynchronously below the fold, and audit the ad/analytics stack for scripts "
                          "that can be removed or consolidated via a tag manager with load prioritization.",
        "impact": "high", "ease_of_fix": "medium",
    },
    "Image delivery/optimization": {
        "summary": "Images are shipped larger than necessary, adding payload weight and delaying LCP "
                    "when the LCP element is an image.",
        "suggested_fix": "Serve images via a responsive/optimized pipeline (WebP/AVIF, correct srcset sizes, "
                          "CDN-based auto-compression) and set explicit width/height to avoid re-layout.",
        "impact": "high", "ease_of_fix": "medium",
    },
    "Layout instability": {
        "summary": "Elements (ad slots, hero images) shift after initial render, contributing to CLS.",
        "suggested_fix": "Reserve space with explicit width/height or aspect-ratio CSS for ad slots and "
                          "images, and avoid injecting content above existing content after load.",
        "impact": "medium", "ease_of_fix": "easy",
    },
    "Render-blocking resources on the critical path": {
        "summary": "CSS/JS on the critical rendering path is delaying first paint.",
        "suggested_fix": "Inline critical CSS, defer non-critical stylesheets/scripts, and add "
                          "resource hints (preconnect/preload) for key origins.",
        "impact": "medium", "ease_of_fix": "medium",
    },
    "Unused/unoptimized JavaScript bundles": {
        "summary": "A significant amount of shipped JavaScript is unused on this page, adding parse/compile "
                    "and download cost.",
        "suggested_fix": "Code-split by route/component, tree-shake unused vendor code, and audit bundles "
                          "for legacy polyfills no longer needed for the target browser matrix.",
        "impact": "medium", "ease_of_fix": "hard",
    },
    "Accessibility violations (labels, alt text, contrast)": {
        "summary": "Recurring accessibility audit failures affect screen-reader and low-vision users.",
        "suggested_fix": "Add descriptive alt text to content/hero images, associate form inputs with "
                          "<label> elements, and adjust text/background color pairs to meet WCAG AA contrast.",
        "impact": "medium", "ease_of_fix": "easy",
    },
}

_SEVERITY_CONFIDENCE = {"critical": 0.9, "warning": 0.7, "info": 0.5}


def _confidence_for(evidence: list[Evidence], strength: float) -> float:
    if not evidence:
        return round(strength, 2)
    sev_conf = max(_SEVERITY_CONFIDENCE.get(e.severity, 0.5) for e in evidence)
    return round(min(1.0, (sev_conf + strength) / 2 + 0.05), 2)


class MockLlmProvider(LlmSynthesisProvider):
    model_name = "mock-llm-v1"

    async def synthesize(
        self, evidence: list[Evidence], candidates: list[CandidateSignal]
    ) -> LlmRecommendationSet:
        if not candidates:
            return LlmRecommendationSet(
                recommendations=[],
                insufficient_evidence_note="No candidate root-cause signals were generated from the "
                                            "supplied evidence - metrics may already be within healthy "
                                            "thresholds, or there isn't enough evidence yet.",
            )

        items: list[RecommendationItem] = []
        for candidate in candidates:
            template = _TEMPLATES.get(candidate.root_cause_hypothesis)
            if not template:
                continue  # unknown hypothesis id -> skip rather than invent wording
            evidence_strings = [e.description for e in candidate.supporting_evidence]
            items.append(RecommendationItem(
                root_cause=candidate.root_cause_hypothesis,
                summary=template["summary"],
                evidence=evidence_strings,
                affected_audits=[e.metric for e in candidate.supporting_evidence],
                impact=template["impact"],
                ease_of_fix=template["ease_of_fix"],
                confidence=_confidence_for(candidate.supporting_evidence, candidate.strength),
                suggested_fix=template["suggested_fix"],
            ))

        return LlmRecommendationSet(recommendations=items)
