"""
Deterministic mock "LLM" synthesizer - lets the whole app be demoed without
an OpenAI key. It performs the same synthesis job a real LLM call would (turn
candidate signals + evidence into worded, ranked recommendations) using
fixed templates keyed by root_cause_hypothesis, so behavior is reproducible.

Each template deliberately answers four separate questions, because a
one-line label ("Image delivery/optimization") is not an explanation:
  summary             -> what the issue is, in one line
  problem_explanation -> WHAT is actually happening and WHY it happens
  user_impact         -> what the reader/business actually loses because of it
  fix_steps           -> ordered, concrete actions a developer can pick up
"""
from app.schemas.recommendation import LlmRecommendationSet, RecommendationItem
from app.services.evidence.models import Evidence
from app.services.llm.base import LlmSynthesisProvider
from app.services.recommendations.candidate_signals import CandidateSignal

_TEMPLATES: dict[str, dict] = {
    "Heavy third-party/ad-related execution": {
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
    "Image delivery/optimization": {
        "summary": "Images are shipped larger than necessary, adding payload weight and delaying LCP "
                    "when the LCP element is an image.",
        "problem_explanation": (
            "The page is downloading images at a far higher resolution and file size than the layout "
            "actually displays them at - for example a 2000px-wide hero file rendered into a 380px-wide "
            "phone screen. The browser must download the entire file before it can paint it, so an "
            "oversized hero image directly delays Largest Contentful Paint; on a news article the hero "
            "image usually IS the LCP element, which is why this shows up as a performance problem rather "
            "than just a bandwidth one. Compounding it, the images are typically being served in older "
            "formats (JPEG/PNG) instead of modern WebP or AVIF, which reach the same visual quality in "
            "roughly 25-35% fewer bytes."
        ),
        "user_impact": (
            "Readers on mobile data - the majority of Indian news traffic - watch a blank or half-rendered "
            "article while the hero image downloads. Slower LCP measurably raises bounce rate, so readers "
            "leave before the article renders. The wasted bytes also cost the reader real money on a metered "
            "connection, and cost the publisher real money in CDN egress."
        ),
        "fix_steps": [
            "Identify the LCP element on this page (usually the article hero image) and confirm its actual rendered size versus the file size served.",
            "Generate responsive variants and serve them with srcset/sizes so a phone never downloads a desktop-sized file.",
            "Convert to WebP or AVIF with a JPEG fallback, ideally automatically at the CDN rather than manually per article.",
            "Set explicit width and height (or aspect-ratio CSS) on every image so reserving space also fixes layout shift.",
            "Preload the hero image so the browser starts fetching it immediately instead of waiting to discover it in the HTML.",
            "Lazy-load every image below the fold so they do not compete for bandwidth with the hero.",
        ],
        "suggested_fix": "Serve images via a responsive/optimized pipeline (WebP/AVIF, correct srcset sizes, "
                          "CDN-based auto-compression) and set explicit width/height to avoid re-layout.",
        "impact": "high", "ease_of_fix": "medium",
    },
    "Layout instability": {
        "summary": "Elements (ad slots, hero images) shift after initial render, contributing to CLS.",
        "problem_explanation": (
            "Ad slots and images are being inserted into the page without their dimensions reserved in "
            "advance. The browser lays out the page with those elements at zero height, paints it, and then "
            "- when the ad or image finally arrives - re-runs layout and pushes everything below it further "
            "down. Cumulative Layout Shift measures exactly this: content that was already visible moving "
            "unexpectedly. It is not a loading-speed problem, which is why a page can score well on LCP and "
            "still fail CLS. Ad slots are the usual culprit on news sites because the slot's final height "
            "depends on which creative the ad server returns, so nothing reserves space by default."
        ),
        "user_impact": (
            "A reader is mid-sentence, or reaching to tap a link, and the content jumps under their finger - "
            "frequently causing an accidental tap on the ad that just loaded. Accidental ad clicks look like "
            "engagement in reporting but are experienced as a trick by the reader, and they are a recurring "
            "source of complaints and uninstalls on mobile."
        ),
        "fix_steps": [
            "Reserve a fixed min-height on every ad slot container, sized to the most common creative for that slot.",
            "Add explicit width and height attributes (or aspect-ratio CSS) to every image and embed.",
            "Never inject banners, notification bars or consent prompts above content that is already rendered - overlay them instead.",
            "Preload web fonts and use font-display: optional or swap with a metric-matched fallback so text does not reflow when the font arrives.",
            "Re-test after each change: CLS is cumulative, so several small shifts add up to one failing score.",
        ],
        "suggested_fix": "Reserve space with explicit width/height or aspect-ratio CSS for ad slots and "
                          "images, and avoid injecting content above existing content after load.",
        "impact": "medium", "ease_of_fix": "easy",
    },
    "Render-blocking resources on the critical path": {
        "summary": "CSS/JS on the critical rendering path is delaying first paint.",
        "problem_explanation": (
            "Stylesheets and scripts referenced in the document head block the browser from painting "
            "anything at all until they have been downloaded and parsed. The browser cannot safely show a "
            "single pixel until it knows the CSS rules, otherwise content would flash unstyled and then "
            "rearrange. So every millisecond spent fetching a blocking resource is a millisecond the reader "
            "spends on a blank white screen - which is what First Contentful Paint measures. The usual cause "
            "is one large site-wide stylesheet plus several synchronous scripts loaded in the head, where "
            "only a small fraction of that CSS is needed to render what is initially on screen."
        ),
        "user_impact": (
            "The reader taps a headline and gets a white screen before any text appears. This is the moment "
            "most abandonments happen, because the reader has no feedback that anything is loading - on a "
            "slow connection many will hit back and go to a competitor's article instead."
        ),
        "fix_steps": [
            "Extract the CSS actually needed for above-the-fold content and inline it directly in the head.",
            "Load the remaining stylesheet asynchronously so it no longer blocks first paint.",
            "Add defer (or async where order does not matter) to scripts in the head that are not needed for initial render.",
            "Add preconnect hints for the origins serving fonts, images and ads so the connection handshake happens in parallel.",
            "Re-measure FCP after each change - this area gives the fastest visible wins of any item on this list.",
        ],
        "suggested_fix": "Inline critical CSS, defer non-critical stylesheets/scripts, and add "
                          "resource hints (preconnect/preload) for key origins.",
        "impact": "medium", "ease_of_fix": "medium",
    },
    "Unused/unoptimized JavaScript bundles": {
        "summary": "A significant amount of shipped JavaScript is unused on this page, adding parse/compile "
                    "and download cost.",
        "problem_explanation": (
            "A large share of the JavaScript delivered to this page is never executed on this page. The cost "
            "is paid three times over: the bytes are downloaded, the parser reads them, and the JavaScript "
            "engine compiles them - the last two both on the main thread, before the page can become "
            "interactive. This normally happens when one bundle is built to serve every page type (so an "
            "article page also ships the homepage carousel and the live-blog code), or when polyfills for "
            "browsers the site no longer supports are still included in the build."
        ),
        "user_impact": (
            "Slower time-to-interactive on exactly the devices that can least afford it - mid-range Android "
            "phones, where parse and compile are several times slower than on a developer's laptop. The "
            "reader waits longer before they can scroll or tap, and burns data on code that never runs."
        ),
        "fix_steps": [
            "Run a coverage trace on this page to see which bundles are loaded but largely unexecuted.",
            "Code-split by route so an article page ships article code only, not homepage or live-blog code.",
            "Drop legacy polyfills for browsers outside the current support matrix, and confirm that matrix with analytics rather than assumption.",
            "Tree-shake and audit heavy dependencies - a date or utility library pulled in for one function is a common find.",
            "Add a bundle-size check to CI so this does not regress silently with the next feature.",
        ],
        "suggested_fix": "Code-split by route/component, tree-shake unused vendor code, and audit bundles "
                          "for legacy polyfills no longer needed for the target browser matrix.",
        "impact": "medium", "ease_of_fix": "hard",
    },
    "Accessibility violations (labels, alt text, contrast)": {
        "summary": "Recurring accessibility audit failures affect screen-reader and low-vision users.",
        "problem_explanation": (
            "Three distinct classes of failure are recurring across runs. Images are missing alt attributes, "
            "so a screen reader either announces nothing or reads out the raw filename - for a news article "
            "the hero image often carries real editorial meaning that is then lost entirely. Form inputs "
            "(newsletter signup, search) have no associated label element, so a screen-reader user hears an "
            "unlabelled text box with no indication of what to type. And text/background colour pairs fall "
            "below the WCAG AA contrast ratio of 4.5:1, typically on bylines, timestamps and captions where "
            "a light grey was chosen for visual hierarchy. Because these repeat across multiple runs rather "
            "than appearing once, they are template-level issues, not one bad article."
        ),
        "user_impact": (
            "Readers using screen readers cannot navigate the article properly. Readers with low vision - and "
            "any reader outdoors in bright sunlight, which is a large share of mobile news reading - cannot "
            "read low-contrast bylines and captions at all. For a publisher this is both an audience-reach "
            "problem and a compliance exposure, since accessibility standards increasingly carry legal weight."
        ),
        "fix_steps": [
            "Add descriptive alt text to content and hero images in the CMS, and make the field mandatory at upload so the fix stays fixed.",
            "Associate every form input with a visible <label> element, or an aria-label where a visible label would break the design.",
            "Raise text colours that fall below 4.5:1 contrast - bylines, timestamps and captions are the usual offenders.",
            "Fix these in the shared page template rather than per article, since the audit failures repeat across runs.",
            "Add an automated accessibility check to CI so new templates are caught before publication.",
        ],
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
                problem_explanation=template["problem_explanation"],
                user_impact=template["user_impact"],
                fix_steps=template["fix_steps"],
                evidence=evidence_strings,
                affected_audits=[e.metric for e in candidate.supporting_evidence],
                impact=template["impact"],
                ease_of_fix=template["ease_of_fix"],
                confidence=_confidence_for(candidate.supporting_evidence, candidate.strength),
                suggested_fix=template["suggested_fix"],
            ))

        return LlmRecommendationSet(recommendations=items)