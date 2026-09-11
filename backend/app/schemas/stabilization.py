from datetime import datetime

from pydantic import BaseModel, ConfigDict


class StabilizedMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url_id: int
    window_start: datetime
    window_end: datetime
    run_count: int
    median_metrics: dict
    variability_metrics: dict
    flagged: bool
    created_at: datetime


class StabilizeRequest(BaseModel):
    window_runs: int | None = None  # override STABILIZATION_WINDOW_RUNS if provided
