"""WorkflowRun model - one execution of the LangGraph pipeline.

``newsletter_id`` is an added nullable FK (SET NULL) linking a run to the
issue it produced, for auditability.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base
from app.db.types import str_enum
from app.models.enums import ExecutionStatus
from app.models.mixins import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.agent_run import AgentRun
    from app.models.newsletter import Newsletter


class WorkflowRun(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    newsletter_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("newsletters.id", ondelete="SET NULL"),
        index=True,
    )

    workflow_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    workflow_status: Mapped[ExecutionStatus] = mapped_column(
        str_enum(ExecutionStatus, "workflow_status"),
        default=ExecutionStatus.PENDING,
        nullable=False,
        index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    newsletter: Mapped[Newsletter | None] = relationship(back_populates="workflow_runs")
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="workflow_run",
        lazy="selectin",
    )
