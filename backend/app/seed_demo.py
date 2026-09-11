"""
Seed demo data for both Deccan Herald and Prajavani so the whole app is
demonstrable with zero external API keys.

Usage:
    python -m app.seed_demo
"""
import asyncio
import logging

from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.site import Site
from app.models.url import Url
from app.services.psi.ingestion import run_psi_for_url
from app.services.recommendations.service import NoStabilizedDataError, generate_recommendations
from app.services.stabilization.service import InsufficientRunsError, stabilize_url

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_demo")

SITES = [
    {"name": "Deccan Herald", "base_url": "https://www.deccanherald.com/"},
    {"name": "Prajavani", "base_url": "https://www.prajavani.net/"},
]

# (category, path) pairs per site, appended to base_url
URL_SPECS = [
    ("homepage", ""),
    ("article", "district/bengaluru-urban/sample-article-city-infrastructure-report-2026"),
]

RUNS_PER_URL = 6


async def seed() -> None:
    # For local `python -m app.seed_demo` convenience, make sure tables exist
    # (in Docker, migrations should already have created them - this is a no-op then).
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        for site_spec in SITES:
            site = db.query(Site).filter(Site.name == site_spec["name"]).first()
            if site is None:
                site = Site(name=site_spec["name"], base_url=site_spec["base_url"])
                db.add(site)
                db.commit()
                db.refresh(site)
                logger.info("Created site: %s", site.name)
            else:
                logger.info("Site already exists: %s", site.name)

            for category, path in URL_SPECS:
                full_url = site_spec["base_url"].rstrip("/") + "/" + path if path else site_spec["base_url"]
                url = db.query(Url).filter(Url.site_id == site.site_id, Url.url == full_url).first()
                if url is None:
                    url = Url(site_id=site.site_id, url=full_url, url_category=category, enabled=True)
                    db.add(url)
                    db.commit()
                    db.refresh(url)
                    logger.info("  Created URL [%s]: %s", category, full_url)
                else:
                    logger.info("  URL already exists [%s]: %s", category, full_url)

                for i in range(RUNS_PER_URL):
                    run = await run_psi_for_url(db, url)
                    logger.info("    Run %d/%d -> status=%s perf=%s a11y=%s",
                                i + 1, RUNS_PER_URL, run.run_status,
                                run.category_scores.get("performance"), run.category_scores.get("accessibility"))

                try:
                    stabilize_url(db, url.url_id)
                    logger.info("    Stabilized url_id=%s", url.url_id)
                except InsufficientRunsError as exc:
                    logger.warning("    Could not stabilize url_id=%s: %s", url.url_id, exc)
                    continue

                try:
                    rec = await generate_recommendations(db, url.url_id)
                    logger.info("    Generated %d recommendation(s), validation=%s",
                                len(rec.root_cause_groups), rec.validation_status)
                except NoStabilizedDataError as exc:
                    logger.warning("    Could not generate recommendations for url_id=%s: %s", url.url_id, exc)

        logger.info("Demo seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(seed())
