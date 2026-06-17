"""Article, tag, and category schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ArticleStatus
from app.schemas.common import ORMModel


# --- Category ---
class CategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None


class CategoryCreate(CategoryBase):
    pass


class CategoryRead(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None


# --- Tag ---
class TagCreate(BaseModel):
    tag_name: str = Field(..., min_length=1, max_length=100)


class TagRead(ORMModel):
    id: uuid.UUID
    article_id: uuid.UUID
    tag_name: str


# --- Article ---
class ArticleBase(BaseModel):
    source_id: uuid.UUID
    category_id: uuid.UUID | None = None
    title: str = Field(..., min_length=1, max_length=1024)
    url: str = Field(..., min_length=1, max_length=2048)
    author: str | None = Field(default=None, max_length=255)
    published_date: datetime | None = None
    raw_content: str | None = None
    summary: str | None = None
    status: ArticleStatus = ArticleStatus.NEW


class ArticleCreate(ArticleBase):
    pass


class ArticleUpdate(BaseModel):
    category_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=1024)
    summary: str | None = None
    status: ArticleStatus | None = None


class ArticleRead(ORMModel):
    id: uuid.UUID
    source_id: uuid.UUID
    category_id: uuid.UUID | None
    title: str
    url: str
    author: str | None
    published_date: datetime | None
    summary: str | None
    status: ArticleStatus
    created_at: datetime
    updated_at: datetime
