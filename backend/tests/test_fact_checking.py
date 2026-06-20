"""Fact-checking agent tests (external requests + LLM mocked)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.agents.fact_checking import (
    citation_builder,
    confidence_engine,
    cross_source_validator,
    source_verifier,
)
from app.agents.fact_checking.evidence_packager import build_package
from app.agents.fact_checking.fact_check_agent import FactCheckAgent
from app.core.config import settings
from app.models.citation import Citation
from app.models.collected_article import CollectedArticle
from app.models.enums import (
    ArticleStatus,
    ClaimType,
    ClaimVerification,
    CollectionMethod,
    SourceType,
    TrustTier,
    VerificationStatus,
)
from app.models.evidence_package import EvidencePackage
from app.models.fact_check_result import FactCheckResult
from app.models.verified_claim import VerifiedClaim


def _source(source_type=SourceType.DOCUMENTATION, name="Docs", url="https://ex.com"):
    from app.models.content_source import ContentSource

    return ContentSource(
        id=uuid.uuid4(),
        source_name=name,
        source_type=source_type,
        source_url=url,
        priority=1,
        credibility_score=0.9,
        freshness_score=0.8,
        relevance_score=0.9,
        preferred_collection_method=CollectionMethod.DOCUMENTATION,
    )


def _article(
    title="Agents guide", content="", *, url="https://ex.com/a", published=None, source=None
) -> CollectedArticle:
    src = source or _source()
    art = CollectedArticle(
        id=uuid.uuid4(),
        source_id=src.id,
        title=title,
        url=url,
        raw_content=content,
        summary=content,
        published_date=published,
    )
    art.source = src
    return art


# --- source verification --- #
def test_source_credibility_scoring() -> None:
    high = _article(url="https://platform.openai.com/docs/guides/agents")
    tier, score = source_verifier.verify_source(high)
    assert tier == TrustTier.HIGH and score == 95.0

    doc = _article(url="https://unknown.example/x", source=_source(SourceType.DOCUMENTATION))
    assert source_verifier.verify_source(doc) == (TrustTier.HIGH, 90.0)

    blog = _article(url="https://unknown.example/y", source=_source(SourceType.WEBSITE))
    tier, score = source_verifier.verify_source(blog)
    assert tier == TrustTier.MEDIUM


async def test_url_verification(monkeypatch) -> None:
    monkeypatch.setattr(settings, "FACT_CHECK_VERIFY_URLS", True)

    async def ok_head(url):
        return True, 200

    monkeypatch.setattr(source_verifier, "_http_head", ok_head)
    check = await source_verifier.verify_url("https://ex.com")
    assert check.accessible is True and check.status_code == 200

    async def boom(url):
        raise RuntimeError("down")

    monkeypatch.setattr(source_verifier, "_http_head", boom)
    check = await source_verifier.verify_url("https://ex.com")
    assert check.accessible is False
    monkeypatch.setattr(settings, "FACT_CHECK_VERIFY_URLS", False)


async def test_url_verification_skipped_when_disabled() -> None:
    # FACT_CHECK_VERIFY_URLS is False in tests -> no network, marked accessible+skipped.
    check = await source_verifier.verify_url("https://ex.com")
    assert check.skipped is True
    assert check.accessible is True


def test_date_verification() -> None:
    now = datetime.now(timezone.utc)
    assert source_verifier.verify_date(None) is False
    assert source_verifier.verify_date(now - timedelta(days=2)) is True
    assert source_verifier.verify_date(now + timedelta(days=5)) is False


# --- claim extraction --- #
def test_claim_extraction() -> None:
    text = (
        "The model achieves 95% accuracy on SWE-bench. "
        "OpenAI launches a new agent SDK today. "
        "This is a detailed factual statement about agent orchestration design patterns."
    )
    claims = cross_source_validator.extract_claims(text)
    types = {c.claim_type for c in claims}
    assert any(c.claim_type == ClaimType.STATISTIC for c in claims)
    assert ClaimType.BENCHMARK in types or ClaimType.STATISTIC in types
    assert len(claims) >= 2


# --- cross-source validation --- #
def test_cross_source_validation_high_trust_supported() -> None:
    art = _article(content="Agents achieve strong results")
    claim = cross_source_validator.Claim("Agents achieve strong benchmark results", ClaimType.BENCHMARK)
    result = cross_source_validator.validate_claim(claim, art, TrustTier.HIGH, [])
    assert result.status == ClaimVerification.SUPPORTED


def test_cross_source_validation_unverified_low_trust() -> None:
    art = _article(content="x", source=_source(SourceType.WEBSITE))
    claim = cross_source_validator.Claim("Some unique unverifiable assertion xyzzy", ClaimType.FACT)
    result = cross_source_validator.validate_claim(claim, art, TrustTier.LOW, [])
    assert result.status == ClaimVerification.UNVERIFIED


def test_cross_source_corroboration_and_contradiction() -> None:
    src_a = _source(name="A", url="https://a.com")
    src_b = _source(name="B", url="https://b.com")
    art = _article(
        title="OpenAI launches agent orchestration framework",
        content="agent orchestration framework launch",
        source=src_a,
    )
    other = _article(
        title="OpenAI agent orchestration framework now available",
        content="agent orchestration framework launch confirmed",
        url="https://b.com/x",
        source=src_b,
    )
    claim = cross_source_validator.Claim("OpenAI agent orchestration framework launch", ClaimType.PRODUCT_LAUNCH)
    res = cross_source_validator.validate_claim(claim, art, TrustTier.MEDIUM, [other])
    assert res.corroborating_sources >= 1

    contra = _article(
        title="OpenAI agent orchestration framework not real, false claim",
        content="agent orchestration framework launch is false debunk",
        url="https://b.com/y",
        source=src_b,
    )
    res2 = cross_source_validator.validate_claim(claim, art, TrustTier.MEDIUM, [contra])
    assert res2.status == ClaimVerification.CONTRADICTED


# --- citations --- #
def test_citation_generation() -> None:
    art = _article(title="Agents", published=datetime.now(timezone.utc))
    other = _article(title="Other", url="https://b.com/o", source=_source(name="B", url="https://b.com"))
    cites = citation_builder.build_citations(art, [other])
    assert len(cites) == 2
    assert cites[0]["source_url"] == art.url
    assert cites[0]["retrieval_timestamp"] is not None
    assert cites[0]["source_name"] == "Docs"


# --- confidence --- #
def test_confidence_thresholds() -> None:
    assert confidence_engine.status_for(95) == VerificationStatus.VERIFIED
    assert confidence_engine.status_for(80) == VerificationStatus.REVIEW_REQUIRED
    assert confidence_engine.status_for(60) == VerificationStatus.LOW_CONFIDENCE
    assert confidence_engine.status_for(40) == VerificationStatus.REJECTED


def test_confidence_calculation() -> None:
    claim = cross_source_validator.ClaimResult("c", ClaimType.FACT, ClaimVerification.SUPPORTED, 90, 2)
    result = confidence_engine.compute_confidence(
        source_credibility=95,
        claim_results=[claim],
        url_accessible=True,
        freshness=100,
        citations_count=3,
    )
    assert 0 <= result.overall_confidence_score <= 100
    assert result.overall_confidence_score >= 70
    for v in (result.source_credibility_score, result.evidence_score, result.cross_source_score):
        assert 0 <= v <= 100


# --- evidence package --- #
def test_evidence_packaging() -> None:
    art = _article(title="Agents")
    claim = cross_source_validator.ClaimResult("c", ClaimType.FACT, ClaimVerification.SUPPORTED, 90, 1)
    conf = confidence_engine.compute_confidence(
        source_credibility=90,
        claim_results=[claim],
        url_accessible=True,
        freshness=80,
        citations_count=2,
    )
    pkg = build_package(art, [claim], [{"source_url": art.url}], ["B"], conf, "notes")
    assert pkg["article_id"] == str(art.id)
    assert pkg["claims"][0]["status"] == "supported"
    assert pkg["verification_status"] == conf.verification_status.value


# --- agent + DB persistence --- #
async def _seed_article(
    session_factory,
    *,
    source_type=SourceType.DOCUMENTATION,
    content="The agent achieves 95% accuracy on SWE-bench benchmark. "
    "OpenAI launches a new orchestration framework today.",
    title="Agent orchestration framework launch",
    days_old=0,
    selected=True,
) -> str:
    from app.models.content_source import ContentSource

    async with session_factory() as s:
        src = ContentSource(
            source_name="Docs",
            source_type=source_type,
            source_url="https://ex.com",
            priority=1,
            credibility_score=0.9,
            freshness_score=0.8,
            relevance_score=0.9,
            preferred_collection_method=CollectionMethod.DOCUMENTATION,
            category="Agentic AI Engineering",
        )
        s.add(src)
        await s.flush()
        art = CollectedArticle(
            source_id=src.id,
            title=title,
            url="https://ex.com/story",
            raw_content=content,
            summary=content,
            status=ArticleStatus.PROCESSED,
            is_selected=selected,
            published_date=datetime.now(timezone.utc) - timedelta(days=days_old),
            source_category="Agentic AI Engineering",
        )
        s.add(art)
        await s.commit()
        return str(art.id)


async def test_fact_check_agent_persists(session_factory) -> None:
    await _seed_article(session_factory)
    agent = FactCheckAgent(session_factory)
    result = await agent.run()

    assert len(result["fact_check_results"]) == 1
    summary = result["fact_check_results"][0]
    assert summary["verification_status"] in {s.value for s in VerificationStatus}

    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(FactCheckResult)) == 1
        assert await s.scalar(select(func.count()).select_from(EvidencePackage)) == 1
        assert await s.scalar(select(func.count()).select_from(Citation)) >= 1
        assert await s.scalar(select(func.count()).select_from(VerifiedClaim)) >= 1
        art = (await s.execute(select(CollectedArticle))).scalar_one()
    assert art.verification_status is not None
    assert art.overall_confidence_score is not None
    assert art.verified_at is not None


async def test_fact_check_rejects_low_confidence(session_factory) -> None:
    # Weak source + no claims + stale -> REJECTED and removed.
    await _seed_article(
        session_factory,
        source_type=SourceType.WEBSITE,
        content="",
        title="Daily roundup",
        days_old=40,
    )
    agent = FactCheckAgent(session_factory)
    result = await agent.run()
    assert result["fact_check_results"][0]["verification_status"] == VerificationStatus.REJECTED.value
    assert result["selected_article_ids"] == []  # rejected removed
    assert len(result["rejected"]) == 1


async def test_fact_check_empty(session_factory) -> None:
    agent = FactCheckAgent(session_factory)
    result = await agent.run([])
    assert result["fact_check_results"] == []
    assert result["selected_article_ids"] == []


async def test_idempotent_reverify(session_factory) -> None:
    aid = await _seed_article(session_factory)
    agent = FactCheckAgent(session_factory)
    await agent.run([aid])
    await agent.run([aid])  # re-run should not duplicate child rows
    async with session_factory() as s:
        assert await s.scalar(select(func.count()).select_from(FactCheckResult)) == 1
        assert await s.scalar(select(func.count()).select_from(EvidencePackage)) == 1


# --- LLM extraction hook (mocked) --- #
async def test_llm_claim_extraction(session_factory, monkeypatch) -> None:
    from app.agents.fact_checking import fact_check_agent as fca

    async def fake_llm(article):
        return ["Extra LLM-extracted claim about agents"]

    monkeypatch.setattr(fca, "llm_extract_claims", fake_llm)
    monkeypatch.setattr(settings, "ENABLE_LLM_FACTCHECK", True)
    try:
        agent = FactCheckAgent(session_factory)
        art = _article(content="The agent achieves 90% accuracy.")
        claims = await agent.extract_claims(art)
    finally:
        monkeypatch.setattr(settings, "ENABLE_LLM_FACTCHECK", False)
    assert any("Extra LLM-extracted" in c.text for c in claims)
