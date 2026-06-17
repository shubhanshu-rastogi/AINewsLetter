"""Agent run and workflow run schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import ExecutionStatus
from app.schemas.common import ORMModel


class AgentRunRead(ORMModel):
    id: uuid.UUID
    workflow_run_id: uuid.UUID | None
    agent_name: str
    execution_status: ExecutionStatus
    started_at: datetime | None
    finished_at: datetime | None
    execution_time: float | None
    error_message: str | None


class WorkflowRunRead(ORMModel):
    id: uuid.UUID
    newsletter_id: uuid.UUID | None
    workflow_name: str
    workflow_status: ExecutionStatus
    started_at: datetime | None
    finished_at: datetime | None


class AgentRunCreate(BaseModel):
    workflow_run_id: uuid.UUID | None = None
    agent_name: str = Field(..., min_length=1, max_length=100)
    execution_status: ExecutionStatus = ExecutionStatus.PENDING


class WorkflowRunCreate(BaseModel):
    newsletter_id: uuid.UUID | None = None
    workflow_name: str = Field(..., min_length=1, max_length=100)
    workflow_status: ExecutionStatus = ExecutionStatus.PENDING
