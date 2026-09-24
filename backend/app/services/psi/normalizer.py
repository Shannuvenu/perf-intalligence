"""
Converts a raw PSI/Lighthouse JSON payload (from either provider) into the
normalized shape stored on PsiRun: category_scores, core_web_vitals, and
normalized_audits. Everything downstream (stabilization, evidence
extraction) reads only this normalized shape, never the raw JSON again.

Resource-level detail (which URL, how many bytes/ms) is preserved wherever
Lighthouse provides it, so evidence extracted later can point at an actual
resource instead of a bare aggregate number.
"""
from typing import Any


class PsiParsingError(Exception):
    """Raised when a raw PSI payload can't be normalized (malformed response)."""


def _audit_numeric(audits: dict, audit_id: str) -> float | None:
    audit = audits.get(audit_id)
    if not audit:
        return None
    value = audit.get("numericValue")
    return float(value) if value is not None else None


def normalize_psi_result(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        lh = raw["lighthouseResult"]
        categories = lh["categories"]
        audits = lh.get("audits", {})
    except (KeyError, TypeError) as exc:
        raise PsiParsingError(f"Malformed PSI payload: missing expected keys ({exc})") from exc

    def score_pct(cat_id: str) -> float | None:
        cat = categories.get(cat_id)
        if not cat or cat.get("score") is None:
            return None
        return round(float(cat["score"]) * 100, 1)

    category_scores = {
        "performance": score_pct("performance"),
        "accessibility": score_pct("accessibility"),
    }

    core_web_vitals = {
        "lcp_ms": _audit_numeric(audits, "largest-contentful-paint"),
        "cls": _audit_numeric(audits, "cumulative-layout-shift"),
        "tbt_ms": _audit_numeric(audits, "total-blocking-time"),
        "fcp_ms": _audit_numeric(audits, "first-contentful-paint"),
        "speed_index_ms": _audit_numeric(audits, "speed-index"),
        "total_bytes": _audit_numeric(audits, "total-byte-weight"),
    }

    def details_items(audit_id: str) -> list[dict]:
        audit = audits.get(audit_id) or {}
        return (audit.get("details") or {}).get("items", [])

    def overall_savings_bytes(audit_id: str) -> int:
        audit = audits.get(audit_id) or {}
        return int((audit.get("details") or {}).get("overallSavingsBytes", 0) or 0)

    def overall_savings_ms(audit_id: str) -> int:
        audit = audits.get(audit_id) or {}
        return int((audit.get("details") or {}).get("overallSavingsMs", 0) or 0)

    def resource_items_bytes(audit_id: str) -> list[dict]:
        """Preserve per-resource wasted-bytes detail, when Lighthouse gives it,
        so evidence can point at an actual URL instead of just a total."""
        items = []
        for item in details_items(audit_id):
            url = item.get("url")
            wasted = item.get("wastedBytes")
            if url and wasted is not None:
                items.append({"resource": url, "wasted_bytes": int(wasted)})
        return sorted(items, key=lambda i: i["wasted_bytes"], reverse=True)

    def resource_items_ms(audit_id: str) -> list[dict]:
        items = []
        for item in details_items(audit_id):
            url = item.get("url")
            wasted = item.get("wastedMs")
            if url and wasted is not None:
                items.append({"resource": url, "wasted_ms": int(wasted)})
        return sorted(items, key=lambda i: i["wasted_ms"], reverse=True)

    third_party_items = details_items("third-party-summary")
    third_party_blocking_ms = sum(float(i.get("blockingTime", 0) or 0) for i in third_party_items)

    a11y_findings = []
    for audit_id in ("color-contrast", "image-alt", "label"):
        audit = audits.get(audit_id)
        if audit and audit.get("score") == 0:
            a11y_findings.append(
                {
                    "id": audit_id,
                    "title": audit.get("title", audit_id),
                    "affected_nodes": [item.get("node") for item in (audit.get("details") or {}).get("items", [])],
                }
            )

    normalized_audits = {
        "unused_javascript_bytes": overall_savings_bytes("unused-javascript"),
        "render_blocking_savings_ms": overall_savings_ms("render-blocking-resources"),
        "image_optimization_savings_bytes": overall_savings_bytes("uses-optimized-images"),
        "third_party_blocking_ms": round(third_party_blocking_ms, 1),
        "third_party_entities": [
            {"entity": i.get("entity"), "blocking_time_ms": i.get("blockingTime"), "transfer_size_bytes": i.get("transferSize")}
            for i in third_party_items
        ],
        "layout_shift_sources": [i.get("node") for i in details_items("layout-shift-elements")],
        "main_thread_breakdown": details_items("mainthread-work-breakdown"),
        "accessibility_findings": a11y_findings,
        # Resource-level detail (product spec section 1/14): who exactly is
        # responsible for the aggregate savings figure above, when Lighthouse
        # reports it. Never invented when Lighthouse doesn't provide items.
        "unused_javascript_items": resource_items_bytes("unused-javascript"),
        "render_blocking_items": resource_items_ms("render-blocking-resources"),
        "image_optimization_items": resource_items_bytes("uses-optimized-images"),
    }

    return {
        "category_scores": category_scores,
        "core_web_vitals": core_web_vitals,
        "normalized_audits": normalized_audits,
    }
