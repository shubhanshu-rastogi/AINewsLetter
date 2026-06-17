"""Strongly-typed LangGraph workflow state.

A single ``WorkflowState`` flows through the graph. It is a ``TypedDict``
(``total=False``) so nodes may return partial updates that LangGraph merges into
the checkpointed state. Internal control fields (``editorial_passed``,
``failed``, ``regeneration_count``) are not part of the public contract but are
used for routing.
"""

from __future__ import annotations

from typing import Any, TypedDict


class WorkflowState(TypedDict, total=False):
    # Identity
    workflow_run_id: str
    newsletter_id: str | None
    issue_number: int | None

    # Pipeline data
    collected_article_ids: list[str]
    selected_article_ids: list[str]
    category_map: dict[str, list[str]]
    fact_check_results: list[dict[str, Any]]
    newsletter_draft: dict[str, Any] | None
    linkedin_draft: dict[str, Any] | None
    visual_ids: list[str]

    # Human review
    review_session_id: str | None
    feedback_items: list[dict[str, Any]]
    approval_status: str | None  # pending | approved | rejected | feedback_required
    publish_status: str | None  # pending | published | rejected | skipped

    # Bookkeeping
    errors: list[str]
    current_step: str
    created_at: str
    updated_at: str

    # Internal control flags (not part of the public contract)
    editorial_passed: bool
    failed: bool
    regeneration_count: int


# Canonical node names (single source of truth for graph wiring + routing).
class Nodes:
    START = "start_workflow_node"
    SOURCE_COLLECTION = "source_collection_node"
    RELEVANCE_FILTER = "relevance_filter_node"
    CATEGORIZATION = "categorization_node"
    FACT_CHECK = "fact_check_node"
    NEWSLETTER_WRITER = "newsletter_writer_node"
    LINKEDIN_WRITER = "linkedin_writer_node"
    VISUAL_GENERATION = "visual_generation_node"
    EDITORIAL_REVIEW = "editorial_review_node"
    HUMAN_REVIEW = "human_review_node"
    FEEDBACK_PROCESSOR = "feedback_processor_node"
    DRAFT_REGENERATION = "draft_regeneration_node"
    APPROVAL_ROUTER = "approval_router_node"
    PUBLISHER = "publisher_node"
    COMPLETION = "completion_node"
    ERROR_HANDLER = "error_handler_node"


# Approval status values used for routing.
class Approval:
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    FEEDBACK_REQUIRED = "feedback_required"
