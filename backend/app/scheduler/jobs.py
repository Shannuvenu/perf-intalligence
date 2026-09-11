"""
Scheduled job body (product spec section 18): for every enabled URL, run
PSI, store the result, refresh stabilization, and - only if
AUTO_LLM_ANALYSIS=true - generate recommendations. Default is false so a
freshly-cloned repo doesn't burn OpenAI credits automatically.
"""
import logging

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.url import Url
from app.services.psi.ingestion import run_psi_for_url
from app.services.recommendations.service import NoStabilizedDataError, generate_recommendations
from app.services.stabilization.service import InsufficientRunsError, stabilize_url

logger = logging.getLogger(__name__)


async def run_scheduled_audit_job() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        urls = list(db.scalars(select(Url).where(Url.enabled.is_(True))))
        logger.info("Scheduled audit job: running PSI for %d enabled URL(s)", len(urls))

        for url in urls:
            run = await run_psi_for_url(db, url)
            if run.run_status != "success":
                logger.warning("Scheduled PSI run failed for url_id=%s: %s", url.url_id, run.error_message)
                continue

            try:
                stabilize_url(db, url.url_id)
            except InsufficientRunsError as exc:
                logger.info("Skipping stabilization for url_id=%s: %s", url.url_id, exc)
                continue

            if settings.AUTO_LLM_ANALYSIS:
                try:
                    await generate_recommendations(db, url.url_id, settings)
                except NoStabilizedDataError as exc:
                    logger.info("Skipping recommendations for url_id=%s: %s", url.url_id, exc)
    finally:
        db.close()
