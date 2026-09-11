from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_url_or_404
from app.db.session import get_db
from app.models.url import Url
from app.schemas.trend import MetricTrend, TrendsResponse
from app.services.trends import compute_trends

router = APIRouter(prefix="/api/urls", tags=["trends"])


@router.get("/{url_id}/trends", response_model=TrendsResponse)
def get_trends(url: Url = Depends(get_url_or_404), db: Session = Depends(get_db)) -> TrendsResponse:
    raw = compute_trends(db, url.url_id)
    return TrendsResponse(url_id=url.url_id, metrics=[MetricTrend(**m) for m in raw])
