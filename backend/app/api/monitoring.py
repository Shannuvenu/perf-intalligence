from typing import Any

import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import get_settings

router = APIRouter(
    prefix="/api/monitoring",
    tags=["monitoring"],
)


@router.get("/urls")
async def get_monitoring_urls() -> dict[str, Any]:
    """
    Fetch the enabled monitoring URLs from the Google Apps Script
    Web App endpoint.

    Google Apps Script reads the Config sheet and returns JSON.
    Perf Intelligence exposes that data through this backend endpoint
    so the frontend does not need to communicate with Google directly.
    """

    settings = get_settings()
    apps_script_url = settings.APPS_SCRIPT_MONITORING_URL.strip()

    if not apps_script_url:
        raise HTTPException(
            status_code=503,
            detail="Google Apps Script monitoring URL is not configured.",
        )

    try:
        async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            response = await client.get(apps_script_url)

    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach Google Apps Script: {exc}",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=(
                "Google Apps Script returned HTTP "
                f"{response.status_code}."
            ),
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Google Apps Script returned invalid JSON.",
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=502,
            detail="Google Apps Script returned an unexpected response.",
        )

    if data.get("success") is not True:
        raise HTTPException(
            status_code=502,
            detail=str(
                data.get(
                    "error",
                    "Google Apps Script reported an error.",
                )
            ),
        )

    urls = data.get("urls", [])

    if not isinstance(urls, list):
        raise HTTPException(
            status_code=502,
            detail="Google Apps Script returned invalid URL data.",
        )

    return {
        "success": True,
        "count": len(urls),
        "urls": urls,
    }