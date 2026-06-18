"""Publishing + subscriber API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


# --- publishing --- #
class PublishRequest(BaseModel):
    channels: list[str] | None = None  # e.g. ["BEEHIIV", "LINKEDIN"]; None = all


class PublishResponse(BaseModel):
    newsletter_id: str
    overall: str
    publish_status: str
    channels: dict[str, Any]


class PublicationRecordRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    channel: str
    publication_status: str
    publish_state: str | None
    external_publication_id: str | None
    publication_date: datetime | None
    retry_count: int
    error_message: str | None
    last_retry_at: datetime | None
    channel_metadata: dict[str, Any] | None
    created_at: datetime


class AnalyticsRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID
    channel: str
    publication_date: datetime | None
    open_count: int
    click_count: int
    impressions: int
    engagement: float
    subscriber_count: int
    growth_metrics: dict[str, Any] | None
    is_placeholder: bool | None


class EmailPackageResponse(BaseModel):
    subject: str
    preview_text: str
    html: str
    text: str
    subscribe_url: str


# --- subscribers --- #
class SubscribeRequest(BaseModel):
    email: EmailStr
    name: str | None = None
    source: str = "api"


class UnsubscribeRequest(BaseModel):
    email: EmailStr


class SubscriberRead(ORMModel):
    id: uuid.UUID
    email: EmailStr
    name: str | None
    status: str
    source: str | None
    unsubscribed_at: datetime | None
    created_at: datetime


class SubscriberStats(BaseModel):
    total: int
    active: int
    unsubscribed: int
    bounced: int
    by_status: dict[str, int] = Field(default_factory=dict)
