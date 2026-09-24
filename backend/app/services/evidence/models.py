from typing import Literal

from pydantic import BaseModel

Severity = Literal["info", "warning", "critical"]

# "direct"       - PageSpeed/Lighthouse explicitly reported this exact number
#                  (a metric value or an audit's own savings estimate).
# "derived"      - the backend calculated this from PageSpeed measurements
#                  (e.g. averaged across the stabilization run window).
# "insufficient" - the metric indicates a potential problem but does not by
#                  itself establish a specific root cause (e.g. LCP alone).
EvidenceStrength = Literal["direct", "derived", "insufficient"]


class Evidence(BaseModel):
    """One deterministic, threshold-backed observation. This is the only
    thing the rule engine and the LLM are allowed to reason from - never the
    raw PSI payload directly.

    Every evidence item has a stable `id` (assigned by the extractor) so the
    LLM can reference it by ID instead of restating it in free text, and the
    server can verify every reference actually exists before trusting it.
    """

    id: str = ""
    audit_id: str | None = None
    metric: str
    description: str
    value: float | str | None = None
    threshold: float | str | None = None
    resource: str | None = None
    severity: Severity
    evidence_strength: EvidenceStrength = "direct"
    tags: list[str] = []
