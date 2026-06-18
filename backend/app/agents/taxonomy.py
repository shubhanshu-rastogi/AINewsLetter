"""Shared keyword taxonomy for scoring, classification, and tagging.

Deterministic keyword maps keep the agents testable without LLM calls. The
optional LLM path (see categorization.llm) can refine these heuristics.
"""

from __future__ import annotations

from app.models.enums import NewsletterSection as NS

# Section -> trigger keywords (lowercase, substring match).
SECTION_KEYWORDS: dict[NS, list[str]] = {
    NS.AGENTIC_AI_ENGINEERING: [
        "agent", "agents", "agentic", "orchestration", "multi-agent", "multi agent",
        "guardrail", "tool use", "react", "autonomous", "agent design", "workflow",
    ],
    NS.AI_EVALUATION_QA_GATES: [
        "evaluation", "eval", "rubric", "quality gate", "ci/cd", "observability",
        "trace", "metrics", "pass rate", "llm-as-judge", "llm as judge", "monitoring",
    ],
    NS.AI_TESTING_QUALITY: [
        "testing", " qa ", "quality engineering", "playwright", "selenium",
        "test automation", "unit test", "integration test", "quality assurance",
        "test case", "sdet",
    ],
    NS.ENTERPRISE_AI_ADOPTION: [
        "enterprise", "governance", "adoption", "platform engineering", "case study",
        "architecture", "compliance", "roi", "production", "scale",
    ],
    NS.AI_TOOLS_WATCH: [
        "tool", "launch", "release", "startup", "framework", "library", "sdk",
        "product", "open source", "open-source",
    ],
    NS.RESEARCH_WATCH: [
        "research", "paper", "arxiv", "study", "novel", "state-of-the-art",
        "sota", "empirical", "preprint",
    ],
    NS.CODING_AGENT_BENCHMARK: [
        "swe-bench", "swebench", "coding agent", "code generation", "copilot",
        "codegen", "leaderboard", "pass@", "software engineering task", "benchmark",
    ],
    NS.WEEKLY_TREND_SIGNALS: [
        "trend", "viral", "weekly", "breaking", "roundup", "this week",
        "announcement", "news",
    ],
}

# Section -> human-readable primary category label.
SECTION_CATEGORY: dict[NS, str] = {
    NS.AGENTIC_AI_ENGINEERING: "Agentic AI Engineering",
    NS.AI_EVALUATION_QA_GATES: "AI Evaluation and QA Gates",
    NS.AI_TESTING_QUALITY: "AI Testing and Quality Engineering",
    NS.ENTERPRISE_AI_ADOPTION: "Enterprise AI Adoption",
    NS.AI_TOOLS_WATCH: "AI Tools",
    NS.RESEARCH_WATCH: "Software Engineering Research",
    NS.CODING_AGENT_BENCHMARK: "Coding Agents",
    NS.WEEKLY_TREND_SIGNALS: "Weekly AI Trends",
}

# Tag -> trigger keywords.
TAG_KEYWORDS: dict[str, list[str]] = {
    "agents": ["agent", "agentic"],
    "multi-agent": ["multi-agent", "multi agent"],
    "orchestration": ["orchestration", "orchestrator", "workflow"],
    "evaluation": ["evaluation", "eval", "rubric"],
    "prompt-engineering": ["prompt", "prompting"],
    "testing": ["testing", "test "],
    "playwright": ["playwright"],
    "benchmarks": ["benchmark", "swe-bench", "leaderboard"],
    "observability": ["observability", "trace", "monitoring"],
    "guardrails": ["guardrail", "safety"],
    "enterprise-ai": ["enterprise", "governance", "adoption"],
    "rag": ["rag", "retrieval-augmented", "retrieval augmented"],
    "llm-testing": ["llm test", "llm-as-judge", "model evaluation"],
    "quality-engineering": ["quality engineering", "quality assurance", " qa "],
}

# Technical depth signal words.
TECHNICAL_KEYWORDS = [
    "architecture", "implementation", "code", "api", "framework", "algorithm",
    "evaluation", "benchmark", "latency", "throughput", "design pattern",
    "deployment", "pipeline", "model", "dataset",
]

ENTERPRISE_KEYWORDS = SECTION_KEYWORDS[NS.ENTERPRISE_AI_ADOPTION]
QA_KEYWORDS = SECTION_KEYWORDS[NS.AI_TESTING_QUALITY] + SECTION_KEYWORDS[NS.AI_EVALUATION_QA_GATES]
TREND_KEYWORDS = SECTION_KEYWORDS[NS.WEEKLY_TREND_SIGNALS]

# Penalty signals.
CLICKBAIT_PATTERNS = [
    "you won't believe", "shocking", "mind-blowing", "this one trick",
    "what happened next", "gone wrong", "!!!", "?!?",
]
PROMO_PATTERNS = [
    "sponsored", "buy now", "discount", "sign up now", "limited time",
    "promo code", "affiliate", "advertisement",
]


def count_hits(text: str, keywords: list[str]) -> int:
    return sum(1 for kw in keywords if kw in text)
