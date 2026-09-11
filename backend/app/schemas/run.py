from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class CoreWebVitals(BaseModel):
    lcp_ms: float | None = None
    cls: float | None = None
    tbt_ms: float | None = None
    fcp_ms: float | None = None
    speed_index_ms: float | None = None


class CategoryScores(BaseModel):
    performance: float | None = None
    accessibility: float | None = None


class RunTriggerResponse(BaseModel):
    run_id: int
    run_status: Literal["success", "failed", "running"]
    message: str


class PsiRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: int
    url_id: int
    run_timestamp: datetime
    strategy: str
    category_scores: dict[str, Any]
    core_web_vitals: dict[str, Any]
    run_status: str
    error_message: str | None = None
    created_at: datetime

class FullAnalysisResponse(BaseModel):
    runs_completed: int
    successful_runs: int
    stabilized: bool
    analyzed: bool
    message: str