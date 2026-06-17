"""Workflow orchestration API endpoints.

Mounted at ``/api/workflows`` (outside the versioned ``/api/v1`` prefix to match
the workflow API contract).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.workflow import (
    ReviewRequest,
    WorkflowStartResponse,
    WorkflowStateResponse,
    WorkflowStatusResponse,
)
from app.workflows.service import WorkflowService, get_workflow_service

router = APIRouter(tags=["workflows"])


@router.post(
    "/newsletter/start",
    response_model=WorkflowStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_newsletter_workflow(
    service: WorkflowService = Depends(get_workflow_service),
) -> WorkflowStartResponse:
    result = await service.start_newsletter_workflow()
    state = result["state"]
    return WorkflowStartResponse(
        workflow_run_id=result["workflow_run_id"],
        newsletter_id=result["newsletter_id"],
        issue_number=result["issue_number"],
        current_step=state.get("current_step"),
        approval_status=state.get("approval_status"),
        publish_status=state.get("publish_status"),
        paused=result["paused"],
    )


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
