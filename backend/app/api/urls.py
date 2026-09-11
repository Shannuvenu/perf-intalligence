from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_site_or_404, get_url_or_404
from app.db.session import get_db
from app.models.site import Site
from app.models.url import Url
from app.schemas.url import UrlCreate, UrlRead

router = APIRouter(prefix="/api/sites", tags=["urls"])

# Separate router (different prefix) for direct /api/urls/{url_id} lookups -
# the frontend's URL detail page needs this without knowing the parent site.
url_router = APIRouter(prefix="/api/urls", tags=["urls"])


@url_router.get("/{url_id}", response_model=UrlRead)
def get_url(url: Url = Depends(get_url_or_404)) -> UrlRead:
    return UrlRead.model_validate(url)


@router.get("/{site_id}/urls", response_model=list[UrlRead])
def list_urls(site: Site = Depends(get_site_or_404), db: Session = Depends(get_db)) -> list[UrlRead]:
    urls = list(db.scalars(select(Url).where(Url.site_id == site.site_id)))
    return [UrlRead.model_validate(u) for u in urls]


@router.post("/{site_id}/urls", response_model=UrlRead, status_code=201)
def create_url(payload: UrlCreate, site: Site = Depends(get_site_or_404), db: Session = Depends(get_db)) -> UrlRead:
    url = Url(site_id=site.site_id, url=payload.url, url_category=payload.url_category, enabled=payload.enabled)
    db.add(url)
    db.commit()
    db.refresh(url)
    return UrlRead.model_validate(url)
