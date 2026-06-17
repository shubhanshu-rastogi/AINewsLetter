"""Publication record schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.enums import PublicationChannel, PublicationStatus
from app.schemas.common import ORMModel


class PublicationCreate(BaseModel):
    newsletter_id: uuid.UUID
    channel: PublicationChannel
    publication_status: PublicationStatus = PublicationStatus.PENDING
    publication_date: datetime | None = None


class PublicationUpdate(BaseModel):
    publication_status: PublicationStatus | None = None
    publication_date: datetime | None = None


class PublicationRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    channel: PublicationChannel
    publication_status: PublicationStatus
    publication_date: datetime | None
    created_at: datetime
