"""
Deterministic mock "LLM" synthesizer - lets the whole app be demoed without
a Groq key. It performs the same synthesis job a real LLM call would (turn
supported candidates + evidence into worded, ranked recommendations) using
fixed templates keyed by candidate_id, so behavior is reproducible and, like
the real provider, it can ONLY ever reference the evidence ids actually
attached to each candidate.
"""
from app.schemas.recommendation import LlmRecommendationSet, RecommendationItem
from app.services.evidence.models import Evidence
from app.services.llm.base import LlmSynthesisProvider
from app.services.recommendations.candidate_signals import (
    ACCESSIBILITY,
    IMAGE_OPTIMIZATION,
    LAYOUT_SHIFT,
    PAGE_WEIGHT,
    RENDER_BLOCKING,
    THIRD_PARTY_BLOCKING,
    UNUSED_JAVASCRIPT,
    CandidateSignal,
)

_TEMPLATES: dict[str, dict] = {
    THIRD_PARTY_BLOCKING: {
        "summary": "Third-party scripts (ad tech, analytics) are consuming a large share of main-thread "
                    "time, degrading TBT and delaying interactivity.",
        "problem_explanation": (
            "Ad-tech and analytics scripts are being loaded during initial page load and executed on the "
            "browser's single main thread. A browser has exactly one main thread for running JavaScript, "
            "calculating layout and painting pixels. While a third-party script parses and executes, that "
            "thread is occupied - it cannot respond to a tap, cannot run the site's own JavaScript, and "
            "cannot paint an update. Total Blocking Time measures precisely this: the total time the main "
            "thread was blocked long enough that the page would feel unresponsive. The site's own code may "
            "be perfectly fast; it is simply queued behind vendor code the team does not control. Ad scripts "
            "make this worse because they often load further scripts of their own at runtime, so the real "
            "cost is larger than the initial request suggests."
        ),
        "user_impact": (
            "The page looks loaded but is frozen. A reader taps the menu, a headline, or tries to scroll, "
            "and nothing responds for a noticeable beat. On ad-supported news sites this is the single most "
            "common source of 'the site is slow' complaints - and because it happens after content is "
            "visible, readers blame the publisher, not the ad vendor."
        ),
        "fix_steps": [
            "Audit every third-party tag currently loading on this page and list which team or contract owns each one.",
            "Move non-critical tags (analytics, A/B testing, heatmaps) to load after the page is interactive, using async or defer.",
            "Load below-the-fold ad slots lazily - only request them as the reader scrolls near them.",
            "Consolidate duplicate vendors: news sites commonly run two or three analytics tools that measure the same thing.",
            "Set a performance budget for third-party blocking time and fail the build when a new tag pushes past it.",
        ],
        "suggested_fix": "Defer or lazy-load non-critical third-party tags until after first paint, load ad "
                          "slots asynchronously below the fold, and audit the ad/analytics stack for scripts "
                          "that can be removed or consolidated via a tag manager with load prioritization.",
        "impact": "high", "ease_of_fix": "medium",
    },
    IMAGE_OPTIMIZATION: {
        "summary": "PageSpeed identified image optimization savings, adding payload weight beyond what the "
                    "layout actually needs.",
        "problem_explanation": (
            "PageSpeed's image-optimization audit reports that the page is downloading images at a higher "
            "resolution and/or file size than necessary, or in an older format than modern alternatives. The "
            "browser must download the full file before it can paint it, so this is a candidate contributor "
            "to paint timing when the affected image is on the critical path - review whether the specific "
            "resource flagged is the page's LCP element before assuming that connection."
        ),
        "user_impact": (
            "Readers on mobile data download more bytes than the displayed image size requires, which can "
            "delay when the surrounding content becomes visible and costs the reader real data."
        ),
        "fix_steps": [
            "Confirm the actual rendered size versus the file size served for the flagged resource.",
            "Generate responsive variants and serve them with srcset/sizes so a phone never downloads a desktop-sized file.",
            "Convert to WebP or AVIF with a fallback, ideally automatically at the CDN rather than manually per image.",
            "Set explicit width and height (or aspect-ratio CSS) on the image so reserving space also helps layout stability.",
        ],
        "suggested_fix": "Serve this resource via a responsive/optimized pipeline (WebP/AVIF, correct srcset "
                          "sizes, CDN-based auto-compression) and set explicit width/height.",
        "impact": "high", "ease_of_fix": "medium",
    },
    LAYOUT_SHIFT: {
        "summary": "Elements shift after initial render, contributing to CLS.",
        "problem_explanation": (
            "PageSpeed reports layout shift for the specific elements listed in the evidence. These are "
            "typically inserted without their final dimensions reserved in advance, so the browser lays out "
            "the page with them at zero (or wrong) height, then re-runs layout once the real content arrives "
            "- pushing everything below it. Cumulative Layout Shift measures exactly this: content that was "
            "already visible moving unexpectedly."
        ),
        "user_impact": (
            "A reader is mid-sentence, or reaching to tap a link, and the content jumps under their finger - "
            "frequently causing an accidental tap on whatever loaded into that space."
        ),
        "fix_steps": [
            "Reserve a fixed min-height on the flagged element(s), sized to the most common content for that slot.",
            "Add explicit width and height attributes (or aspect-ratio CSS) to the flagged images/embeds.",
            "Never inject banners, notification bars or consent prompts above content that is already rendered - overlay them instead.",
            "Re-test after each change: CLS is cumulative, so several small shifts add up to one failing score.",
        ],
        "suggested_fix": "Reserve space with explicit width/height or aspect-ratio CSS for the flagged "
                          "elements, and avoid injecting content above existing content after load.",
        "impact": "medium", "ease_of_fix": "easy",
    },
    RENDER_BLOCKING: {
        "summary": "CSS/JS on the critical rendering path is delaying first paint.",
        "problem_explanation": (
            "PageSpeed's render-blocking-resources audit identifies specific stylesheets/scripts that block "
            "the browser from painting anything until they are downloaded and parsed. The browser cannot "
            "safely show a single pixel until it knows the CSS rules, so every millisecond spent fetching a "
            "blocking resource is a millisecond the reader spends on a blank screen."
        ),
        "user_impact": (
            "The reader taps a headline and gets a white screen before any text appears - a common point of "
            "abandonment on a slow connection."
        ),
        "fix_steps": [
            "Review the specific flagged resource(s) and extract the CSS actually needed for above-the-fold content, inlining it in the head.",
            "Load the remaining stylesheet asynchronously so it no longer blocks first paint.",
            "Add defer (or async where order does not matter) to scripts in the head that are not needed for initial render.",
            "Re-measure FCP after each change.",
        ],
        "suggested_fix": "Review whether the flagged resource(s) can be reduced, split, deferred, or "
                          "otherwise removed from the critical rendering path; inline only the CSS needed "
                          "for the initial viewport.",
        "impact": "medium", "ease_of_fix": "medium",
    },
    UNUSED_JAVASCRIPT: {
        "summary": "A significant amount of shipped JavaScript is unused on this page, adding parse/compile "
                    "and download cost.",
        "problem_explanation": (
            "PageSpeed's unused-javascript audit reports that a large share of the JavaScript delivered to "
            "this page is never executed on it. The cost is paid three times over: the bytes are downloaded, "
            "the parser reads them, and the JavaScript engine compiles them - the last two both on the main "
            "thread, before the page can become interactive."
        ),
        "user_impact": (
            "Slower time-to-interactive on exactly the devices that can least afford it - mid-range Android "
            "phones, where parse and compile are several times slower than on a developer's laptop."
        ),
        "fix_steps": [
            "Run a coverage trace on this page to confirm which parts of the flagged bundle are unexecuted.",
            "Code-split by route so an article page ships article code only, not homepage or live-blog code.",
            "Drop legacy polyfills for browsers outside the current support matrix.",
            "Add a bundle-size check to CI so this does not regress silently.",
        ],
        "suggested_fix": "Code-split by route/component, tree-shake unused vendor code in the flagged "
                          "bundle, and audit for legacy polyfills no longer needed.",
        "impact": "medium", "ease_of_fix": "hard",
    },
    ACCESSIBILITY: {
        "summary": "Recurring accessibility audit failures affect screen-reader and low-vision users.",
        "problem_explanation": (
            "The referenced accessibility audit(s) failed in a majority of runs, which means this is a "
            "template-level issue rather than one bad page load. Depending on the specific audit, this "
            "typically means images missing alt text, form inputs missing an associated label, or "
            "text/background colour pairs falling below the WCAG AA contrast ratio."
        ),
        "user_impact": (
            "Readers using screen readers or with low vision cannot use this page as intended - both an "
            "audience-reach problem and a compliance exposure."
        ),
        "fix_steps": [
            "Open the specific failing audit and its affected node(s) in the evidence to see exactly what's failing.",
            "Fix the underlying template rather than the individual page, since the failure repeats across runs.",
            "Add an automated accessibility check to CI so regressions are caught before publication.",
        ],
        "suggested_fix": "Address the specific failing accessibility audit (alt text, label association, or "
                          "contrast, depending on which one was flagged) at the shared template level.",
        "impact": "medium", "ease_of_fix": "easy",
    },
    PAGE_WEIGHT: {
        "summary": "The page transfers more total data than mobile readers on limited plans can comfortably "
                    "afford, slowing every stage of load.",
        "problem_explanation": (
            "PageSpeed's total-byte-weight measurement exceeds the configured budget. This is a cumulative "
            "problem rather than one bad file - images, unused JavaScript and third-party scripts each add "
            "their share. Because every other metric (LCP, FCP, TBT) is downstream of how much data has to "
            "arrive first, high total page weight tends to show up as a contributing factor across several "
            "other findings, not just as its own isolated issue."
        ),
        "user_impact": (
            "Readers on capped or slow mobile data plans pay more, in money and time, to load this page than "
            "a leaner competitor's page."
        ),
        "fix_steps": [
            "Break down the byte budget by resource type (images, JS, fonts, third-party) to find the single largest contributor first.",
            "Apply the image optimization and unused-JS fixes elsewhere in this list if they are also present - they are usually the two biggest levers on total weight.",
            "Set a page-weight budget and add a CI check that fails the build if a new page exceeds it.",
        ],
        "suggested_fix": "Set a page-weight budget, enforce it in CI, and prioritize whichever other flagged "
                          "findings (images/JS) are the largest contributors to total page weight.",
        "impact": "medium", "ease_of_fix": "medium",
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
        self,
        evidence: list[Evidence],
        candidates: list[CandidateSignal],
        page_metrics: dict | None = None,
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
            template = _TEMPLATES.get(candidate.candidate_id)
            if not template:
                continue  # unknown candidate id -> skip rather than invent wording
            items.append(RecommendationItem(
                candidate_id=candidate.candidate_id,
                summary=template["summary"],
                problem_explanation=template["problem_explanation"],
                user_impact=template["user_impact"],
                fix_steps=template["fix_steps"],
                evidence_refs=candidate.evidence_refs,
                impact=template["impact"],
                ease_of_fix=template["ease_of_fix"],
                confidence=_confidence_for(candidate.supporting_evidence, candidate.strength),
                suggested_fix=template["suggested_fix"],
            ))

        return LlmRecommendationSet(recommendations=items)
