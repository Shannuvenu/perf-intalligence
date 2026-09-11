"""
Deterministic-shape / realistically-noisy mock PSI provider.

Produces a raw JSON payload that is structurally faithful to a real
Lighthouse/PSI v5 result (same audit ids, same nesting) but hand-built so the
whole app works with zero external API keys. Each call introduces small
random jitter on top of a per-site/per-page-type baseline, the same way real
PSI runs are noisy between runs - this is what makes the stabilization layer
(median across N runs) meaningful to demo.
"""
import random
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.services.psi.base import PsiProvider, PsiProviderError

# Baseline profiles: (lcp_ms, cls, tbt_ms, fcp_ms, speed_index_ms, perf_score, a11y_score)
_PROFILES: dict[str, dict[str, tuple]] = {
    "deccanherald": {
        "homepage": (3600, 0.18, 450, 2100, 4800, 0.55, 0.82),
        "article": (3100, 0.12, 280, 1900, 4100, 0.65, 0.85),
    },
    "prajavani": {
        "homepage": (3800, 0.22, 500, 2300, 5100, 0.50, 0.78),
        "article": (3300, 0.15, 320, 2000, 4400, 0.60, 0.80),
    },
}


def _page_type(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return "homepage" if path == "" else "article"


def _site_key(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "deccanherald" in host:
        return "deccanherald"
    if "prajavani" in host:
        return "prajavani"
    return "deccanherald"  # fallback baseline for unknown demo URLs


def _jitter(value: float, pct: float, rng: random.Random) -> float:
    return max(0.0, value * (1 + rng.uniform(-pct, pct)))


class MockPsiProvider(PsiProvider):
    async def run_psi(self, url: str, strategy: str) -> dict[str, Any]:
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            raise PsiProviderError(f"Invalid URL supplied to mock PSI provider: {url!r}")

        rng = random.Random()  # unseeded -> realistic run-to-run noise, like real PSI
        site = _site_key(url)
        page_type = _page_type(url)
        lcp, cls, tbt, fcp, si, perf, a11y = _PROFILES[site][page_type]

        lcp = _jitter(lcp, 0.18, rng)
        cls = round(_jitter(cls, 0.30, rng), 3)
        tbt = _jitter(tbt, 0.25, rng)
        fcp = _jitter(fcp, 0.15, rng)
        si = _jitter(si, 0.15, rng)
        perf = min(1.0, max(0.0, _jitter(perf, 0.10, rng)))
        a11y = min(1.0, max(0.0, _jitter(a11y, 0.05, rng)))

        third_party_blocking_ms = _jitter(180 if page_type == "homepage" else 60, 0.4, rng)
        unused_js_bytes = int(_jitter(180_000 if page_type == "homepage" else 90_000, 0.35, rng))
        image_savings_bytes = int(_jitter(220_000 if page_type == "article" else 130_000, 0.35, rng))
        render_blocking_ms = int(_jitter(320, 0.4, rng))

        a11y_issues = []
        if a11y < 0.85:
            a11y_issues.append(
                {"id": "color-contrast", "title": "Background/foreground colors do not have sufficient contrast ratio",
                 "score": 0, "items": [{"node": "div.article-meta span.byline"}]}
            )
        if a11y < 0.80:
            a11y_issues.append(
                {"id": "image-alt", "title": "Image elements do not have [alt] attributes",
                 "score": 0, "items": [{"node": "img.lazyload.hero-image"}, {"node": "img.related-thumb"}]}
            )
        if a11y < 0.82:
            a11y_issues.append(
                {"id": "label", "title": "Form elements do not have associated labels",
                 "score": 0, "items": [{"node": "input#newsletter-email"}]}
            )

        return {
            "id": url,
            "analysisUTCTimestamp": datetime.now(timezone.utc).isoformat(),
            "lighthouseResult": {
                "requestedUrl": url,
                "finalUrl": url,
                "categories": {
                    "performance": {"score": round(perf, 2)},
                    "accessibility": {"score": round(a11y, 2)},
                },
                "audits": {
                    "largest-contentful-paint": {"numericValue": round(lcp, 1), "displayValue": f"{lcp/1000:.1f} s"},
                    "cumulative-layout-shift": {"numericValue": cls, "displayValue": str(cls)},
                    "total-blocking-time": {"numericValue": round(tbt, 1), "displayValue": f"{round(tbt)} ms"},
                    "first-contentful-paint": {"numericValue": round(fcp, 1), "displayValue": f"{fcp/1000:.1f} s"},
                    "speed-index": {"numericValue": round(si, 1), "displayValue": f"{si/1000:.1f} s"},
                    "unused-javascript": {
                        "score": 0.5 if unused_js_bytes > 100_000 else 1,
                        "details": {"overallSavingsBytes": unused_js_bytes,
                                     "items": [{"url": f"{url.rstrip('/')}/static/vendor-ads.js", "wastedBytes": unused_js_bytes}]},
                    },
                    "render-blocking-resources": {
                        "score": 0.5 if render_blocking_ms > 250 else 1,
                        "details": {"overallSavingsMs": render_blocking_ms,
                                     "items": [{"url": f"{url.rstrip('/')}/static/main.css", "wastedMs": render_blocking_ms}]},
                    },
                    "uses-optimized-images": {
                        "score": 0.5 if image_savings_bytes > 100_000 else 1,
                        "details": {"overallSavingsBytes": image_savings_bytes,
                                     "items": [{"url": f"{url.rstrip('/')}/media/hero.jpg", "wastedBytes": image_savings_bytes}]},
                    },
                    "third-party-summary": {
                        "score": 0.5 if third_party_blocking_ms > 150 else 1,
                        "details": {"items": [
                            {"entity": "Ad Network / Programmatic Ads", "blockingTime": round(third_party_blocking_ms, 1),
                             "mainThreadTime": round(third_party_blocking_ms * 1.6, 1), "transferSize": 210_000},
                            {"entity": "Analytics", "blockingTime": round(third_party_blocking_ms * 0.15, 1),
                             "mainThreadTime": round(third_party_blocking_ms * 0.2, 1), "transferSize": 45_000},
                        ]},
                    },
                    "layout-shift-elements": {
                        "score": 0.5 if cls > 0.1 else 1,
                        "details": {"items": [
                            {"node": "div#ad-slot-top", "score": round(cls * 0.6, 3)},
                            {"node": "img.hero-image", "score": round(cls * 0.4, 3)},
                        ]},
                    },
                    "mainthread-work-breakdown": {
                        "details": {"items": [
                            {"category": "Script Evaluation", "duration": round(tbt * 1.3, 1)},
                            {"category": "Style & Layout", "duration": round(tbt * 0.5, 1)},
                        ]}
                    },
                    **{issue["id"]: {"score": issue["score"], "title": issue["title"], "details": {"items": issue["items"]}}
                       for issue in a11y_issues},
                },
            },
        }
