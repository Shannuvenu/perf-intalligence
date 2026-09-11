from datetime import datetime
from typing import Literal

from pydantic import BaseModel

TrendDirection = Literal["improving", "stable", "regressing", "insufficient_data"]


class TrendPoint(BaseModel):
    timestamp: datetime
    value: float | None


class MetricTrend(BaseModel):
    metric: str
    direction: TrendDirection
    points: list[TrendPoint]


class TrendsResponse(BaseModel):
    url_id: int
    metrics: list[MetricTrend]
