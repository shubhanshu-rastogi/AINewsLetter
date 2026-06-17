"""Standard API response envelopes and shared schema helpers."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base for read schemas mapped from ORM instances."""

    model_config = ConfigDict(from_attributes=True)


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T | None = None
    message: str | None = None


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Stable machine-readable error code.")
    message: str = Field(..., description="Human-readable error message.")
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    success: bool = False
    error: ErrorDetail


class PageMeta(BaseModel):
    total: int
    page: int
    page_size: int
    pages: int


class PageResponse(BaseModel, Generic[T]):
    """Paginated list envelope."""

    items: list[T]
    meta: PageMeta
