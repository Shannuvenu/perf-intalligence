"""
Provider-agnostic PSI client. Everything else in the app (API routes,
scheduler, seed_demo) talks to `get_psi_provider()` and never imports
mock_provider / real_provider directly - that's the single switch point for
PSI_PROVIDER.
"""
from app.core.config import Settings, get_settings
from app.services.psi.base import PsiProvider
from app.services.psi.mock_provider import MockPsiProvider
from app.services.psi.real_provider import RealPsiProvider


def get_psi_provider(settings: Settings | None = None) -> PsiProvider:
    settings = settings or get_settings()
    if settings.PSI_PROVIDER == "mock":
        return MockPsiProvider()
    return RealPsiProvider(
        api_key=settings.PSI_API_KEY,
        base_url=settings.PSI_API_BASE_URL,
        timeout_seconds=settings.PSI_TIMEOUT_SECONDS,
    )
