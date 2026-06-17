"""Seed data for the 15 curated content sources.

Idempotent: each source is keyed by ``source_url`` and only inserted if absent.
``preferred``/``fallback`` collection methods are derived from the source type
via the strategy layer to keep them consistent.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.source_collection.source_strategy import methods_for_type
from app.core.logging import get_logger
from app.models.content_source import ContentSource
from app.models.enums import NewsletterSection as NS
from app.models.enums import SourceType as ST

logger = get_logger("collection.seed")

# priority, name, type, url, rss_url, category, best_use, cred, fresh, rel, section
SOURCES: list[dict[str, Any]] = [
    {
        "priority": 1, "source_name": "OpenAI Agents SDK / Agents Guide",
        "source_type": ST.DOCUMENTATION,
        "source_url": "https://platform.openai.com/docs/guides/agents", "rss_url": None,
        "category": "Agentic AI Engineering",
        "best_use": "Agent architecture, orchestration, guardrails, observability, human review, and agent evaluation.",
        "credibility_score": 0.97, "freshness_score": 0.4, "relevance_score": 0.95,
        "newsletter_section": NS.AGENTIC_AI_ENGINEERING,
    },
    {
        "priority": 2, "source_name": "Anthropic: Building Effective Agents",
        "source_type": ST.DOCUMENTATION,
        "source_url": "https://www.anthropic.com/engineering/building-effective-agents", "rss_url": None,
        "category": "Agent Design Patterns",
        "best_use": "Routing, parallelization, orchestrator-worker, evaluator-optimizer, and when not to use agents.",
        "credibility_score": 0.97, "freshness_score": 0.4, "relevance_score": 0.95,
        "newsletter_section": NS.AGENTIC_AI_ENGINEERING,
    },
    {
        "priority": 3, "source_name": "Google Agent Development Kit",
        "source_type": ST.DOCUMENTATION,
        "source_url": "https://adk.dev/", "rss_url": None,
        "category": "Multi-Agent Frameworks",
        "best_use": "Multi-agent system design, production agents, debugging, deployment, and enterprise-scale implementation.",
        "credibility_score": 0.93, "freshness_score": 0.4, "relevance_score": 0.92,
        "newsletter_section": NS.AGENTIC_AI_ENGINEERING,
    },
    {
        "priority": 4, "source_name": "Microsoft Foundry: Observability in Generative AI",
        "source_type": ST.DOCUMENTATION,
        "source_url": "https://learn.microsoft.com/en-us/azure/foundry/concepts/observability", "rss_url": None,
        "category": "AI Observability / QA Gates",
        "best_use": "Traces, evaluations, CI/CD quality gates, logs, model outputs, safety, quality, and operational health.",
        "credibility_score": 0.93, "freshness_score": 0.4, "relevance_score": 0.9,
        "newsletter_section": NS.AI_EVALUATION_QA_GATES,
    },
    {
        "priority": 5, "source_name": "Google Cloud Gen AI Evaluation Service",
        "source_type": ST.DOCUMENTATION,
        "source_url": "https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/evaluation-overview", "rss_url": None,
        "category": "AI Evaluation / Agent Testing",
        "best_use": "LLM evaluation, agent evaluation, rubric metrics, custom metrics, response quality, traces, and pass-rate style testing.",
        "credibility_score": 0.93, "freshness_score": 0.4, "relevance_score": 0.9,
        "newsletter_section": NS.AI_EVALUATION_QA_GATES,
    },
    {
        "priority": 6, "source_name": "InfoQ AI, ML & Data Engineering",
        "source_type": ST.RSS,
        "source_url": "https://www.infoq.com/ai-ml-data-eng/",
        "rss_url": "https://feed.infoq.com/ai-ml-data-eng/",
        "category": "Enterprise AI / Architecture",
        "best_use": "Enterprise AI adoption, architecture, governance, platform engineering, agentic systems, testing, DevOps, and case studies.",
        "credibility_score": 0.88, "freshness_score": 0.9, "relevance_score": 0.88,
        "newsletter_section": NS.ENTERPRISE_AI_ADOPTION,
    },
    {
        "priority": 7, "source_name": "Thoughtworks Technology Radar",
        "source_type": ST.WEBSITE,
        "source_url": "https://www.thoughtworks.com/radar", "rss_url": None,
        "category": "Enterprise Tech Trends",
        "best_use": "Leadership commentary on AI tools, testing practices, platforms, and techniques worth adopting, trialing, assessing, or avoiding.",
        "credibility_score": 0.9, "freshness_score": 0.3, "relevance_score": 0.85,
        "newsletter_section": NS.ENTERPRISE_AI_ADOPTION,
    },
    {
        "priority": 8, "source_name": "Ministry of Testing Insights",
        "source_type": ST.BLOG,
        "source_url": "https://www.ministryoftesting.com/insights", "rss_url": None,
        "category": "QA / Testing / Quality Engineering",
        "best_use": "AI in testing, quality engineering, tooling, automation, quality attributes, and leadership.",
        "credibility_score": 0.85, "freshness_score": 0.7, "relevance_score": 0.9,
        "newsletter_section": NS.AI_TESTING_QUALITY,
    },
    {
        "priority": 9, "source_name": "TestGuild Blog",
        "source_type": ST.BLOG,
        "source_url": "https://testguild.com/blog/",
        "rss_url": "https://testguild.com/feed/",
        "category": "Test Automation / QA Tools",
        "best_use": "Practical QA automation, AI testing tools, Playwright, API testing, mobile testing, automation strategy, and practitioner insights.",
        "credibility_score": 0.82, "freshness_score": 0.85, "relevance_score": 0.9,
        "newsletter_section": NS.AI_TESTING_QUALITY,
    },
    {
        "priority": 10, "source_name": "arXiv Software Engineering Recent Papers",
        "source_type": ST.RESEARCH,
        "source_url": "https://arxiv.org/list/cs.SE/recent", "rss_url": None,
        "category": "Research / Future Trends",
        "best_use": "AI-assisted testing, agent-authored tests, coding agents, software quality, software verification, and AI in SDLC.",
        "credibility_score": 0.92, "freshness_score": 0.95, "relevance_score": 0.88,
        "newsletter_section": NS.RESEARCH_WATCH,
    },
    {
        "priority": 11, "source_name": "SWE-bench",
        "source_type": ST.BENCHMARK,
        "source_url": "https://www.swebench.com/", "rss_url": None,
        "category": "Coding Agent Benchmarks",
        "best_use": "Tracking how AI coding agents perform on real software engineering tasks.",
        "credibility_score": 0.9, "freshness_score": 0.6, "relevance_score": 0.9,
        "newsletter_section": NS.CODING_AGENT_BENCHMARK,
    },
    {
        "priority": 12, "source_name": "Latent Space",
        "source_type": ST.NEWSLETTER,
        "source_url": "https://www.latent.space/",
        "rss_url": "https://www.latent.space/feed",
        "category": "AI Engineering / Viral Commentary",
        "best_use": "High-signal AI engineering narratives around agents, models, infrastructure, and AI systems.",
        "credibility_score": 0.85, "freshness_score": 0.9, "relevance_score": 0.85,
        "newsletter_section": NS.AI_TOOLS_WATCH,
    },
    {
        "priority": 13, "source_name": "DeepLearning.AI: The Batch",
        "source_type": ST.NEWSLETTER,
        "source_url": "https://www.deeplearning.ai/the-batch",
        "rss_url": "https://www.deeplearning.ai/the-batch/rss.xml",
        "category": "AI News / Executive Summary",
        "best_use": "Weekly AI news, business impact, research updates, and broad AI trends.",
        "credibility_score": 0.9, "freshness_score": 0.9, "relevance_score": 0.85,
        "newsletter_section": NS.WEEKLY_TREND_SIGNALS,
    },
    {
        "priority": 14, "source_name": "TLDR AI",
        "source_type": ST.TREND_SIGNAL,
        "source_url": "https://tldr.tech/ai",
        "rss_url": "https://tldr.tech/api/rss/ai",
        "category": "Fast AI Trend Scanning",
        "best_use": "Daily scanning for fast-moving AI stories, interesting AI breakthroughs, and trending topics.",
        "credibility_score": 0.78, "freshness_score": 0.95, "relevance_score": 0.8,
        "newsletter_section": NS.WEEKLY_TREND_SIGNALS,
    },
    {
        "priority": 15, "source_name": "Ben's Bites",
        "source_type": ST.NEWSLETTER,
        "source_url": "https://www.bensbites.com/", "rss_url": None,
        "category": "AI Startups / Tools / Builder Trends",
        "best_use": "AI startups, tools, builder trends, and 'tools worth watching' sections.",
        "credibility_score": 0.78, "freshness_score": 0.9, "relevance_score": 0.8,
        "newsletter_section": NS.AI_TOOLS_WATCH,
    },
]


async def seed_sources(session: AsyncSession) -> int:
    """Insert any missing sources. Returns the number created."""
    created = 0
    for spec in SOURCES:
        exists = await session.scalar(
            select(ContentSource).where(ContentSource.source_url == spec["source_url"])
        )
        if exists is not None:
            continue
        preferred, fallback = methods_for_type(spec["source_type"])
        session.add(
            ContentSource(
                is_active=True,
                preferred_collection_method=preferred,
                fallback_collection_method=fallback,
                **spec,
            )
        )
        created += 1
    await session.flush()
    logger.info("sources_seeded", created=created, total=len(SOURCES))
    return created
