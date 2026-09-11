from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_url_or_404
from app.core.config import get_settings
from app.db.session import get_db
from app.models.psi_run import PsiRun
from app.models.url import Url
from app.schemas.run import FullAnalysisResponse, PsiRunRead, RunTriggerResponse
from app.services.psi.ingestion import run_psi_for_url
from app.services.recommendations.service import NoStabilizedDataError, generate_recommendations
from app.services.stabilization.service import InsufficientRunsError, stabilize_url

router = APIRouter(prefix="/api/urls", tags=["runs"])


@router.post("/{url_id}/run", response_model=RunTriggerResponse)
async def trigger_run(url: Url = Depends(get_url_or_404), db: Session = Depends(get_db)) -> RunTriggerResponse:
    run = await run_psi_for_url(db, url)
    message = "PSI run completed successfully." if run.run_status == "success" else f"PSI run failed: {run.error_message}"
    return RunTriggerResponse(run_id=run.run_id, run_status=run.run_status, message=message)


@router.post("/{url_id}/run-full-analysis", response_model=FullAnalysisResponse)
async def run_full_analysis(url: Url = Depends(get_url_or_404), db: Session = Depends(get_db)) -> FullAnalysisResponse:
    """One-click pipeline: run PSI enough times to stabilize, then stabilize, then analyze."""
    settings = get_settings()
    num_runs = settings.STABILIZATION_WINDOW_RUNS
    successful = 0
    for _ in range(num_runs):
        run = await run_psi_for_url(db, url)
        if run.run_status == "success":
            successful += 1

    try:
        stabilize_url(db, url.url_id)
    except InsufficientRunsError as exc:
        return FullAnalysisResponse(
            runs_completed=num_runs, successful_runs=successful,
            stabilized=False, analyzed=False, message=str(exc),
        )

    try:
        await generate_recommendations(db, url.url_id)
    except NoStabilizedDataError as exc:
        return FullAnalysisResponse(
            runs_completed=num_runs, successful_runs=successful,
            stabilized=True, analyzed=False, message=str(exc),
        )

    return FullAnalysisResponse(
        runs_completed=num_runs, successful_runs=successful,
        stabilized=True, analyzed=True, message="Full analysis completed.",
    )


@router.get("/{url_id}/runs", response_model=list[PsiRunRead])
def list_runs(url: Url = Depends(get_url_or_404), db: Session = Depends(get_db), limit: int = 50) -> list[PsiRunRead]:
    stmt = (
        select(PsiRun)
        .where(PsiRun.url_id == url.url_id)
        .order_by(PsiRun.run_timestamp.desc())
        .limit(limit)
    )
    runs = list(db.scalars(stmt))
    return [PsiRunRead.model_validate(r) for r in runs]