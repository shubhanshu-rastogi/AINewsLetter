"""Visual generation API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class VisualRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    visual_kind: str | None
    title: str | None
    description: str | None
    generation_method: str | None
    file_path: str | None
    file_format: str | None
    width: int | None
    height: int | None
    slide_number: int | None
    version: int
    status: str | None
    created_at: datetime


class VisualPreview(BaseModel):
    visual_id: str
    visual_kind: str | None
    file_path: str | None
    preview_url: str | None
    width: int | None
    height: int | None
    version: int
    created_at: datetime


class GenerateResponse(BaseModel):
    newsletter_id: str
    visual_ids: list[str]
    total: int
    carousel_slides: int
    metadata_path: str


class RegenerateResponse(BaseModel):
    visual_id: str
    version: int
    file_path: str


class VisualMetadataResponse(BaseModel):
    newsletter_id: str
    visuals: list[dict[str, Any]]
