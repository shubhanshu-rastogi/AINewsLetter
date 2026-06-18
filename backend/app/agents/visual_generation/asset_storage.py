"""Asset storage abstraction (local now, S3-ready later).

Local layout:
    {root}/visuals/newsletters/{newsletter_id}/{cover|carousel|cards}/<file>
    {root}/visuals/newsletters/{newsletter_id}/metadata.json
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("visuals.storage")


class AssetStorage(ABC):
    """Storage backend interface."""

    @abstractmethod
    def save_bytes(self, relative_path: str, data: bytes) -> str: ...

    @abstractmethod
    def write_json(self, relative_path: str, payload: dict[str, Any]) -> str: ...

    @abstractmethod
    def url_for(self, stored_path: str) -> str: ...

    @abstractmethod
    def exists(self, stored_path: str) -> bool: ...


class LocalAssetStorage(AssetStorage):
    def __init__(self, root: str | None = None, base_url: str | None = None) -> None:
        self.root = Path(root or settings.VISUAL_STORAGE_ROOT).resolve()
        self.base_url = (base_url or settings.VISUAL_BASE_URL).rstrip("/")

    def _abs(self, relative_path: str) -> Path:
        return self.root / relative_path

    def save_bytes(self, relative_path: str, data: bytes) -> str:
        path = self._abs(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.info("asset_saved", path=str(path), bytes=len(data))
        return str(path)

    def write_json(self, relative_path: str, payload: dict[str, Any]) -> str:
        path = self._abs(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str))
        return str(path)

    def url_for(self, stored_path: str) -> str:
        try:
            rel = Path(stored_path).resolve().relative_to(self.root)
        except ValueError:
            rel = Path(stored_path).name
        return f"{self.base_url}/{rel}"

    def exists(self, stored_path: str) -> bool:
        return Path(stored_path).exists()


def newsletter_dir(newsletter_id: str, subdir: str = "") -> str:
    base = f"visuals/newsletters/{newsletter_id}"
    return f"{base}/{subdir}" if subdir else base


def get_storage() -> AssetStorage:
    return LocalAssetStorage()
