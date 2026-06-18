"""Fact-checking API schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class CitationRead(ORMModel):
    id: uuid.UUID
    article_id: uuid.UUID
    title: str | None
    source_name: str | None
    source_url: str | None
    publication_date: datetime | None
    retrieval_timestamp: datetime | None


class VerifiedClaimRead(ORMModel):
    id: uuid.UUID
    claim_text: str
    claim_type: str | None
    verification_status: str | None
    support_score: float | None
    corroborating_sources: float | None


class FactCheckResultRead(ORMModel):
    article_id: uuid.UUID
    url_accessible: bool | None
    source_credibility_score: float | None
    claim_verification_score: float | None
    cross_source_score: float | None
    freshness_score: float | None
    evidence_score: float | None
    overall_confidence_score: float | None
    verification_status: str | None
    fact_check_notes: str | None
    verified_at: datetime | None


class EvidencePackageRead(ORMModel):
    article_id: uuid.UUID
    confidence_score: float | None
    verification_status: str | None
    supporting_sources: list[Any] | None
    verification_notes: str | None
    package: dict[str, Any] | None


class FactCheckStats(BaseModel):
    articles_verified: int
    articles_rejected: int
    articles_requiring_review: int
    average_confidence_score: float
    citations_created: int
    claims_extracted: int
    top_verified_sources: dict[str, int]
