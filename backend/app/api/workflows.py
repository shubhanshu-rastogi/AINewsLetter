"""Workflow orchestration API endpoints.

Mounted at ``/api/workflows`` (outside the versioned ``/api/v1`` prefix to match
the workflow API contract). Protected by the reviewer dependency.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_reviewer
from app.schemas.workflow import (
    ReviewRequest,
    WorkflowRunListItem,
    WorkflowStartResponse,
    WorkflowStateResponse,
    WorkflowStatusResponse,
)
from app.workflows.service import WorkflowService, get_workflow_service

router = APIRouter(tags=["workflows"], dependencies=[Depends(require_reviewer)])


@router.get("", response_model=list[WorkflowRunListItem])
async def list_workflow_runs(
    service: WorkflowService = Depends(get_workflow_service),
) -> list[WorkflowRunListItem]:
    runs = await service.list_runs()
    return [WorkflowRunListItem(**r) for r in runs]


@router.post(
    "/newsletter/start",
    response_model=WorkflowStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_newsletter_workflow(
    service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowStartResponse:
    """Trigger a run in the background; poll ``/{id}/status`` for live progress."""
    result = await service.start_newsletter_workflow_background()
    return WorkflowStartResponse(**result)


@router.get("/{workflow_run_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_run_id: str,
    service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowStatusResponse:
    result = await service.get_status(workflow_run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    return WorkflowStatusResponse(**result)


@router.post("/{workflow_run_id}/review", response_model=WorkflowStatusResponse)
async def submit_review(
    workflow_run_id: str,
    payload: ReviewRequest,
    service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowStatusResponse:
    result = await service.submit_review(
        workflow_run_id,
        payload.approval_status.value,
        [item.model_dump() for item in payload.feedback_items],
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    return WorkflowStatusResponse(**result)


@router.get("/{workflow_run_id}/state", response_model=WorkflowStateResponse)
async def get_workflow_state(
    workflow_run_id: str,
    service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowStateResponse:
    state = await service.get_state(workflow_run_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    return WorkflowStateResponse(workflow_run_id=workflow_run_id, state=state)
