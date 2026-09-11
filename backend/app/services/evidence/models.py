from typing import Literal

from pydantic import BaseModel

Severity = Literal["info", "warning", "critical"]


class Evidence(BaseModel):
    """One deterministic, threshold-backed observation. This is the only
    thing the rule engine and the LLM are allowed to reason from - never the
    raw PSI payload directly."""

    metric: str
    description: str
    value: float | str | None = None
    threshold: float | str | None = None
    severity: Severity
    tags: list[str] = []
