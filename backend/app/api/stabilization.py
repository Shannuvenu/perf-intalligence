from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_url_or_404
from app.db.session import get_db
from app.models.url import Url
from app.schemas.stabilization import StabilizeRequest, StabilizedMetricRead
from app.services.stabilization.service import InsufficientRunsError, latest_stabilized, stabilize_url

router = APIRouter(prefix="/api/urls", tags=["stabilization"])


@router.post("/{url_id}/stabilize", response_model=StabilizedMetricRead)
def trigger_stabilize(
    payload: StabilizeRequest, url: Url = Depends(get_url_or_404), db: Session = Depends(get_db)
) -> StabilizedMetricRead:
    try:
        result = stabilize_url(db, url.url_id, window_runs=payload.window_runs)
    except InsufficientRunsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return StabilizedMetricRead.model_validate(result)


@router.get("/{url_id}/stabilized", response_model=StabilizedMetricRead)
def get_stabilized(url: Url = Depends(get_url_or_404), db: Session = Depends(get_db)) -> StabilizedMetricRead:
    result = latest_stabilized(db, url.url_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No stabilized metrics yet for url_id={url.url_id}")
    return StabilizedMetricRead.model_validate(result)
