"""AgentRun model - one agent execution within a workflow run.

``workflow_run_id`` is an added nullable FK (SET NULL) so individual agent
executions can be grouped under their parent workflow run for tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import ExecutionStatus
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.workflow_run import WorkflowRun


class AgentRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"

    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        index=True,
    )

    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    execution_status: Mapped[ExecutionStatus] = mapped_column(
        str_enum(ExecutionStatus, "agent_execution_status"),
        default=ExecutionStatus.PENDING,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_time: Mapped[float | None] = mapped_column(Float)  # seconds
    error_message: Mapped[str | None] = mapped_column(Text)

    workflow_run: Mapped["WorkflowRun | None"] = relationship(back_populates="agent_runs")
