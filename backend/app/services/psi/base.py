"""
Abstract PSI provider interface. Concrete implementations:
  - mock_provider.MockPsiProvider   -> deterministic demo data, no network
  - real_provider.RealPsiProvider   -> calls the actual Google PSI API

Both return the SAME raw JSON shape (a trimmed-down but structurally faithful
Lighthouse result), so everything downstream (normalizer, evidence
extraction, stabilization) is provider-agnostic.
"""
from abc import ABC, abstractmethod
from typing import Any


class PsiProviderError(Exception):
    """Raised for any provider-level failure (HTTP error, timeout, malformed
    response, invalid URL, rate limit). The message is safe to store in
    psi_runs.error_message."""


class PsiProvider(ABC):
    @abstractmethod
    async def run_psi(self, url: str, strategy: str) -> dict[str, Any]:
        """Return a raw Lighthouse-shaped JSON dict for the given URL, or
        raise PsiProviderError."""
        raise NotImplementedError
