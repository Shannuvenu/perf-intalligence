"""
Real Google PageSpeed Insights v5 client.

Requests both the performance and accessibility Lighthouse categories, and
maps every failure mode called out in the product spec (HTTP errors, PSI API
errors, timeouts, invalid URLs, rate limiting, malformed JSON) to a single
PsiProviderError with a message safe to persist in psi_runs.error_message.
"""
from typing import Any

import httpx

from app.services.psi.base import PsiProvider, PsiProviderError


class RealPsiProvider(PsiProvider):
    def __init__(self, api_key: str, base_url: str, timeout_seconds: int) -> None:
        if not api_key:
            raise PsiProviderError(
                "PSI_PROVIDER=real but PSI_API_KEY is not set. Set it in .env or switch "
                "PSI_PROVIDER back to 'mock'."
            )
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout_seconds

    async def run_psi(self, url: str, strategy: str) -> dict[str, Any]:
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            raise PsiProviderError(f"Invalid URL supplied to PSI: {url!r}")

        params = {
            "url": url,
            "key": self._api_key,
            "strategy": strategy,
            "category": ["performance", "accessibility"],
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self._base_url, params=params)
        except httpx.TimeoutException as exc:
            raise PsiProviderError(f"PSI request timed out after {self._timeout}s for {url}") from exc
        except httpx.RequestError as exc:
            raise PsiProviderError(f"PSI request failed for {url}: {exc}") from exc

        if response.status_code == 429:
            raise PsiProviderError("PSI API rate limit exceeded (HTTP 429). Back off and retry later.")
        if response.status_code == 400:
            raise PsiProviderError(f"PSI API rejected the request (HTTP 400) for {url} - likely an invalid URL.")
        if response.status_code >= 500:
            raise PsiProviderError(f"PSI API server error (HTTP {response.status_code}) for {url}.")
        if response.status_code != 200:
            raise PsiProviderError(f"PSI API returned unexpected HTTP {response.status_code} for {url}.")

        try:
            data = response.json()
        except ValueError as exc:
            raise PsiProviderError(f"PSI API returned malformed (non-JSON) response for {url}") from exc

        if "error" in data:
            message = data["error"].get("message", "unknown PSI API error")
            raise PsiProviderError(f"PSI API error for {url}: {message}")

        if "lighthouseResult" not in data:
            raise PsiProviderError(f"PSI API response for {url} is missing 'lighthouseResult' - malformed response.")

        return data
