"""Health and readiness response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str = "ok"
    app: str
    version: str
    environment: str


class DependencyStatus(BaseModel):
    name: str
    healthy: bool


class ReadinessStatus(BaseModel):
    ready: bool
    dependencies: list[DependencyStatus]
