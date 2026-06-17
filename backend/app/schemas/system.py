"""System setting schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class SettingUpsert(BaseModel):
    key: str = Field(..., min_length=1, max_length=255)
    value: str | None = None


class SettingRead(ORMModel):
    id: uuid.UUID
    key: str
    value: str | None
