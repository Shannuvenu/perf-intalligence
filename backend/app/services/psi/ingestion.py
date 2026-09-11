"""
PSI ingestion service: orchestrates provider -> raw storage -> normalization
-> PsiRun persistence. This is the only place that should call a PsiProvider
directly. API route handlers and the scheduler both call `run_psi_for_url()`
- neither contains this logic itself (see architecture principle in the spec).
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.psi_run import PsiRun
from app.models.url import Url
from app.services.psi.base import PsiProviderError
from app.services.psi.client import get_psi_provider
from app.services.psi.normalizer import PsiParsingError, normalize_psi_result
from app.services.storage import get_raw_storage


async def run_psi_for_url(db: Session, url: Url, strategy: str | None = None) -> PsiRun:
    """Execute one PSI run for `url`, persist it (success or failure), and
    return the created PsiRun row. Never raises - failures are stored as a
    failed run so callers (API/scheduler) can treat this uniformly."""
    settings = get_settings()
    strategy = strategy or settings.PSI_STRATEGY
    provider = get_psi_provider(settings)
    now = datetime.now(timezone.utc)

    try:
        raw = await provider.run_psi(url.url, strategy)
        normalized = normalize_psi_result(raw)

        storage_key = None
        try:
            storage = get_raw_storage(settings)
            storage_key = storage.write_raw(
                site_name=url.site.name if url.site else "unknown-site",
                url_id=url.url_id,
                run_timestamp=now,
                payload=raw,
            )
        except Exception:
            # Raw storage is best-effort for the MVP - losing the raw archive
            # must not lose the normalized metrics we already extracted.
            storage_key = None

        run = PsiRun(
            url_id=url.url_id,
            run_timestamp=now,
            strategy=strategy,
            raw_storage_key=storage_key,
            category_scores=normalized["category_scores"],
            core_web_vitals=normalized["core_web_vitals"],
            normalized_audits=normalized["normalized_audits"],
            run_status="success",
            error_message=None,
        )
    except (PsiProviderError, PsiParsingError) as exc:
        run = PsiRun(
            url_id=url.url_id,
            run_timestamp=now,
            strategy=strategy,
            raw_storage_key=None,
            category_scores={},
            core_web_vitals={},
            normalized_audits={},
            run_status="failed",
            error_message=str(exc),
        )

    db.add(run)
    db.commit()
    db.refresh(run)
    return run
