import pytest

from app.services.psi.normalizer import PsiParsingError, normalize_psi_result


def _valid_raw():
    return {
        "lighthouseResult": {
            "categories": {"performance": {"score": 0.62}, "accessibility": {"score": 0.85}},
            "audits": {
                "largest-contentful-paint": {"numericValue": 3200.5},
                "cumulative-layout-shift": {"numericValue": 0.15},
                "total-blocking-time": {"numericValue": 310.0},
                "first-contentful-paint": {"numericValue": 1900.0},
                "speed-index": {"numericValue": 4200.0},
                "unused-javascript": {"details": {"overallSavingsBytes": 150000}},
                "render-blocking-resources": {"details": {"overallSavingsMs": 300}},
                "uses-optimized-images": {"details": {"overallSavingsBytes": 200000}},
                "third-party-summary": {"details": {"items": [
                    {"entity": "Ad Network", "blockingTime": 120.0, "transferSize": 90000}
                ]}},
                "layout-shift-elements": {"details": {"items": [{"node": "div#ad"}]}},
                "color-contrast": {"score": 0, "title": "Contrast issue", "details": {"items": [{"node": "span.byline"}]}},
            },
        }
    }


def test_normalize_valid_psi_result():
    normalized = normalize_psi_result(_valid_raw())

    assert normalized["category_scores"]["performance"] == 62.0
    assert normalized["category_scores"]["accessibility"] == 85.0
    assert normalized["core_web_vitals"]["lcp_ms"] == 3200.5
    assert normalized["core_web_vitals"]["cls"] == 0.15
    assert normalized["core_web_vitals"]["tbt_ms"] == 310.0
    assert normalized["normalized_audits"]["unused_javascript_bytes"] == 150000
    assert normalized["normalized_audits"]["render_blocking_savings_ms"] == 300
    assert normalized["normalized_audits"]["image_optimization_savings_bytes"] == 200000
    assert normalized["normalized_audits"]["third_party_blocking_ms"] == 120.0
    assert normalized["normalized_audits"]["layout_shift_sources"] == ["div#ad"]
    assert len(normalized["normalized_audits"]["accessibility_findings"]) == 1
    assert normalized["normalized_audits"]["accessibility_findings"][0]["id"] == "color-contrast"


def test_normalize_missing_lighthouse_result_raises():
    with pytest.raises(PsiParsingError):
        normalize_psi_result({"some": "garbage"})


def test_normalize_missing_categories_raises():
    with pytest.raises(PsiParsingError):
        normalize_psi_result({"lighthouseResult": {"audits": {}}})


def test_normalize_handles_missing_audits_gracefully():
    raw = {"lighthouseResult": {"categories": {"performance": {"score": 0.9}, "accessibility": {"score": 0.9}}, "audits": {}}}
    normalized = normalize_psi_result(raw)
    assert normalized["core_web_vitals"]["lcp_ms"] is None
    assert normalized["normalized_audits"]["unused_javascript_bytes"] == 0
    assert normalized["normalized_audits"]["accessibility_findings"] == []
