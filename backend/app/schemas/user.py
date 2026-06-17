"""User schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class UserBase(BaseModel):
    email: EmailStr
    name: str | None = Field(default=None, max_length=255)
    role: UserRole = UserRole.VIEWER


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    role: UserRole | None = None


class UserRead(ORMModel):
    id: uuid.UUID
    email: EmailStr
    name: str | None
    role: UserRole
    created_at: datetime
    updated_at: datetime
