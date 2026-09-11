"""
APScheduler wiring. Started/stopped from the FastAPI lifespan in app.main so
it only runs when the actual server process runs (not during tests or
one-off scripts like seed_demo).
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import get_settings
from app.scheduler.jobs import run_scheduled_audit_job

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler | None:
    global _scheduler
    settings = get_settings()
    if not settings.SCHEDULER_ENABLED:
        logger.info("Scheduler disabled via SCHEDULER_ENABLED=false")
        return None

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_scheduled_audit_job,
        "interval",
        hours=settings.RUN_INTERVAL_HOURS,
        id="scheduled_psi_audit",
        next_run_time=None,  # first run waits one full interval; trigger manually via API for immediate results
    )
    _scheduler.start()
    logger.info("Scheduler started: PSI audits every %d hour(s)", settings.RUN_INTERVAL_HOURS)
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
