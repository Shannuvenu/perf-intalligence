from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_url_or_404
from app.db.session import get_db
from app.models.llm_recommendation import LlmRecommendation
from app.models.url import Url
from app.schemas.recommendation import RecommendationRead
from app.services.recommendations.service import NoStabilizedDataError, generate_recommendations

router = APIRouter(prefix="/api/urls", tags=["recommendations"])


def _to_read(rec: LlmRecommendation) -> RecommendationRead:
    return RecommendationRead(
        recommendation_id=rec.recommendation_id,
        url_id=rec.url_id,
        generated_at=rec.generated_at.isoformat(),
        root_cause_groups=rec.root_cause_groups,
        priority_rank=rec.priority_rank,
        source_run_ids=rec.source_run_ids,
        model_name=rec.model_name,
        prompt_version=rec.prompt_version,
        validation_status=rec.validation_status,
        insufficient_evidence_note=rec.insufficient_evidence_note,
    )


@router.post("/{url_id}/analyze", response_model=RecommendationRead)
async def trigger_analyze(url: Url = Depends(get_url_or_404), db: Session = Depends(get_db)) -> RecommendationRead:
    try:
        rec = await generate_recommendations(db, url.url_id)
    except NoStabilizedDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _to_read(rec)


@router.get("/{url_id}/recommendations", response_model=list[RecommendationRead])
def list_recommendations(
    url: Url = Depends(get_url_or_404), db: Session = Depends(get_db), limit: int = 20
) -> list[RecommendationRead]:
    stmt = (
        select(LlmRecommendation)
        .where(LlmRecommendation.url_id == url.url_id)
        .order_by(LlmRecommendation.generated_at.desc())
        .limit(limit)
    )
    recs = list(db.scalars(stmt))
    return [_to_read(r) for r in recs]
