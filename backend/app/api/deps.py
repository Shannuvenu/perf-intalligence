from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.site import Site
from app.models.url import Url


def get_site_or_404(site_id: int, db: Session = Depends(get_db)) -> Site:
    site = db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail=f"Site {site_id} not found")
    return site


def get_url_or_404(url_id: int, db: Session = Depends(get_db)) -> Url:
    url = db.get(Url, url_id)
    if url is None:
        raise HTTPException(status_code=404, detail=f"URL {url_id} not found")
    return url
