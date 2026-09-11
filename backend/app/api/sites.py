from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_site_or_404
from app.db.session import get_db
from app.models.site import Site
from app.schemas.site import SiteCreate, SiteRead

router = APIRouter(prefix="/api/sites", tags=["sites"])


def _to_read(site: Site) -> SiteRead:
    return SiteRead(
        site_id=site.site_id,
        name=site.name,
        base_url=site.base_url,
        created_at=site.created_at,
        url_count=len(site.urls),
    )


@router.get("", response_model=list[SiteRead])
def list_sites(db: Session = Depends(get_db)) -> list[SiteRead]:
    sites = list(db.scalars(select(Site)))
    return [_to_read(s) for s in sites]


@router.post("", response_model=SiteRead, status_code=201)
def create_site(payload: SiteCreate, db: Session = Depends(get_db)) -> SiteRead:
    existing = db.scalar(select(Site).where(Site.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail=f"Site '{payload.name}' already exists")
    site = Site(name=payload.name, base_url=payload.base_url)
    db.add(site)
    db.commit()
    db.refresh(site)
    return _to_read(site)


@router.get("/{site_id}", response_model=SiteRead)
def get_site(site: Site = Depends(get_site_or_404)) -> SiteRead:
    return _to_read(site)
