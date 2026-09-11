"""
Raw PSI storage abstraction.

MVP ships a single concrete backend: LocalRawStorage (STORAGE_MODE=local),
writing raw PSI JSON to storage/raw/{site}/{date}/{url_id}_{timestamp}.json.

To add S3 later WITHOUT touching PSI ingestion code:
  1. Implement a class S3RawStorage(RawStorage) in this file (or a new
     storage/s3.py) implementing write_raw()/read_raw() using boto3.
  2. Add STORAGE_MODE="s3" to app/core/config.py's Literal and to .env.example.
  3. Extend get_raw_storage() below with an `elif settings.STORAGE_MODE == "s3":`
     branch that returns S3RawStorage(bucket=..., prefix=...).
No caller (the PSI ingestion service) imports LocalRawStorage directly - they
only call get_raw_storage(), so nothing else needs to change.
"""
import json
import re
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings


def _slugify(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-") or "site"


class RawStorage(ABC):
    @abstractmethod
    def write_raw(self, site_name: str, url_id: int, run_timestamp: datetime, payload: dict[str, Any]) -> str:
        """Persist the raw payload and return a storage_key that read_raw() can resolve later."""

    @abstractmethod
    def read_raw(self, storage_key: str) -> dict[str, Any]:
        ...


class LocalRawStorage(RawStorage):
    def __init__(self, root: str) -> None:
        self._root = Path(root)

    def write_raw(self, site_name: str, url_id: int, run_timestamp: datetime, payload: dict[str, Any]) -> str:
        date_dir = run_timestamp.strftime("%Y-%m-%d")
        directory = self._root / _slugify(site_name) / date_dir
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{url_id}_{run_timestamp.strftime('%H%M%S%f')}.json"
        path = directory / filename
        path.write_text(json.dumps(payload), encoding="utf-8")
        # Storage key is a relative path so it stays portable across machines/containers.
        return str(path.relative_to(self._root.parent)) if self._root.parent in path.parents else str(path)

    def read_raw(self, storage_key: str) -> dict[str, Any]:
        path = Path(storage_key)
        if not path.is_absolute():
            path = self._root.parent / storage_key
        return json.loads(path.read_text(encoding="utf-8"))


def get_raw_storage(settings: Settings | None = None) -> RawStorage:
    settings = settings or get_settings()
    if settings.STORAGE_MODE == "local":
        return LocalRawStorage(root=settings.STORAGE_LOCAL_ROOT)
    raise NotImplementedError(
        f"STORAGE_MODE={settings.STORAGE_MODE!r} is not implemented yet. "
        "See the module docstring in app/services/storage.py for how to add S3."
    )
