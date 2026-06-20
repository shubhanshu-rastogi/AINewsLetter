"""Deterministic section content builders.

Content is assembled directly from the verified article data + citations
(no fabrication), with editorial scaffolding (impact framing, takeaways).
Optional LLM polish can rewrite the prose later.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from app.agents.newsletter_writer.brand import BrandVoice
from app.models.collected_article import CollectedArticle
from app.models.enums import NewsletterSection as NS
from app.models.enums import VerificationStatus

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _citation(article: CollectedArticle) -> dict:
    return {
        "source_name": article.source.source_name if article.source else None,
        "source_url": article.url,
        "publication_date": article.published_date.isoformat() if article.published_date else None,
        "title": article.title,
    }


def _first_sentences(text: str | None, n: int = 2) -> str:
    if not text:
        return ""
    sentences = _SENTENCE_RE.split(text.strip())
    return " ".join(sentences[:n]).strip()


def _topic(article: CollectedArticle) -> str:
    # Keep original casing so proper nouns/acronyms (e.g. "OpenAI") read correctly
    # when embedded mid-sentence.
    return (article.title or "this development").strip().rstrip(".") or "this development"


def _needs_review(article: CollectedArticle) -> bool:
    return article.verification_status == VerificationStatus.REVIEW_REQUIRED.value


def _testing_angle(section: NS | None) -> str:
    return (
        {
            NS.AGENTIC_AI_ENGINEERING: "agent behavior testing and guardrail validation",
            NS.AI_EVALUATION_QA_GATES: "evaluation harnesses and CI quality gates",
            NS.AI_TESTING_QUALITY: "test automation and quality engineering practices",
            NS.ENTERPRISE_AI_ADOPTION: "governance checks and acceptance criteria",
            NS.CODING_AGENT_BENCHMARK: "benchmark-driven regression testing",
            NS.RESEARCH_WATCH: "reproducibility and empirical validation",
            NS.AI_TOOLS_WATCH: "tool evaluation and integration testing",
        }.get(section, "quality gates and verification")
        if section
        else "quality gates and verification"
    )


def story(article: CollectedArticle) -> dict:
    topic = _topic(article)
    section = article.newsletter_section
    return {
        "headline": (article.title or "Untitled").strip(),
        "what_happened": _first_sentences(article.summary or article.raw_content, 2)
        or "Details are summarized from the linked source.",
        "why_it_matters": f"This matters because {topic} affects how teams build, "
        "evaluate, and ship AI-enabled software.",
        "business_impact": f"Leaders should weigh how {topic} affects delivery "
        "timelines, tooling budgets, and capability planning.",
        "engineering_impact": f"Engineering teams may need to adapt architecture, "
        f"integration patterns, and tooling to account for {topic}.",
        "testing_implications": f"QA and test teams should plan for {_testing_angle(section)}.",
        "key_takeaway": f"Track {topic}; run a small pilot before broad adoption.",
        "confidence": article.overall_confidence_score,
        "needs_review": _needs_review(article),
        "citation": _citation(article),
    }


def tool(article: CollectedArticle) -> dict:
    topic = _topic(article)
    return {
        "name": (article.title or "Tool").strip(),
        "what_it_does": _first_sentences(article.summary or article.raw_content, 2)
        or "See the linked source for details.",
        "who_should_care": "Test engineers, SDETs, and platform teams evaluating AI tooling.",
        "use_cases": [
            f"Apply {topic} within existing CI/CD and test pipelines",
            "Prototype on a low-risk workflow before scaling",
        ],
        "pros": ["Addresses a concrete engineering need", "Backed by a credible source"],
        "limitations": ["Maturity and integration cost should be validated in a pilot"],
        "needs_review": _needs_review(article),
        "citation": _citation(article),
    }


def testing_insight(article: CollectedArticle) -> dict:
    return {
        "title": (article.title or "Testing insight").strip(),
        "insight": _first_sentences(article.summary or article.raw_content, 3)
        or "A deep-dive on quality engineering implications.",
        "recommendation": "Codify this into your test strategy and evaluation gates.",
        "needs_review": _needs_review(article),
        "citation": _citation(article),
    }


def enterprise_insight(article: CollectedArticle) -> dict:
    return {
        "use_case": (article.title or "Enterprise use case").strip(),
        "summary": _first_sentences(article.summary or article.raw_content, 2),
        "challenges": "Integration, governance, and change management remain the hard parts.",
        "lessons_learned": "Start narrow, measure outcomes, and expand on evidence.",
        "recommendations": "Establish ownership, success metrics, and quality gates early.",
        "needs_review": _needs_review(article),
        "citation": _citation(article),
    }


def research_insight(article: CollectedArticle) -> dict:
    return {
        "paper": (article.title or "Research paper").strip(),
        "problem": "The work addresses a gap in AI for software/quality engineering.",
        "key_findings": _first_sentences(article.summary or article.raw_content, 3),
        "practical_implications": "Watch for tooling that operationalizes these findings.",
        "needs_review": _needs_review(article),
        "citation": _citation(article),
    }


def benchmark_insight(article: CollectedArticle) -> dict:
    return {
        "title": (article.title or "Benchmark update").strip(),
        "what_improved": _first_sentences(article.summary or article.raw_content, 2),
        "limitations": "Benchmarks rarely capture real-world repository complexity.",
        "learnings": "Use benchmark deltas as signals, not guarantees of production readiness.",
        "needs_review": _needs_review(article),
        "citation": _citation(article),
    }


def trend(article: CollectedArticle) -> dict:
    topic = _topic(article)
    return {
        "signal": (article.title or "Trend").strip(),
        "evidence": _first_sentences(article.summary or article.raw_content, 1) or "Observed across recent coverage.",
        "why_it_matters": f"{topic.capitalize()} is shaping near-term AI engineering priorities.",
        "prediction": "Expect this to influence tooling and team practices next quarter.",
        "needs_review": _needs_review(article),
        "citation": _citation(article),
    }


def executive_summary(stories: Sequence[dict], brand: BrandVoice) -> str:
    if not stories:
        return (
            f"This week's {brand.name} is light on verified stories; "
            "we focused on the highest-confidence developments available."
        )
    leads = "; ".join(s["headline"] for s in stories[:3])
    summary = (
        f"This week in {brand.name}: {leads}. "
        "We unpack what happened, why it matters, and the engineering and testing "
        "implications for teams shipping AI-enabled software."
    )
    return _truncate_words(summary, 150)


def final_takeaways(content: dict) -> list[str]:
    takeaways: list[str] = []
    for s in content.get("top_stories", [])[:2]:
        takeaways.append(s["key_takeaway"])
    if content.get("testing"):
        takeaways.append("Fold this week's testing insight into your quality gates.")
    if content.get("benchmark"):
        takeaways.append("Treat benchmark gains as signals, not production guarantees.")
    if content.get("trends"):
        takeaways.append("Watch the trend signals; pilot before committing.")
    return takeaways[:5]


def _truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]).rstrip(",;") + "."
