"""LinkedIn announcement, carousel outline, and email subject generation."""

from __future__ import annotations

from app.agents.newsletter_writer.brand import BrandVoice

LINKEDIN_MAX_CHARS = 1200


def announcement_post(content: dict, brand: BrandVoice) -> str:
    cover = content.get("cover", {})
    issue = cover.get("issue_number")
    stories = content.get("top_stories", [])
    hook = f"This week in {brand.name} (Issue {issue}):"
    insights = [f"- {s['headline']}" for s in stories[:3]]
    cta = "Full breakdown - what happened, why it matters, and the testing implications - in this week's issue. Subscribe to follow along."
    body = "\n".join([hook, "", *insights, "", cta])
    if len(body) > LINKEDIN_MAX_CHARS:
        body = body[: LINKEDIN_MAX_CHARS - 1].rstrip() + "…"
    return body


def carousel_outline(content: dict, brand: BrandVoice) -> list[dict]:
    cover = content.get("cover", {})
    stories = content.get("top_stories", [])
    tools = content.get("tools", [])

    def bullets(items, key, n=3):
        return [i[key] for i in items[:n]] or ["See this week's issue"]

    slides = [
        {"slide": 1, "title": brand.name, "bullets": [brand.tagline, f"Issue {cover.get('issue_number')}"]},
        {"slide": 2, "title": "Top Stories", "bullets": bullets(stories, "headline")},
        {"slide": 3, "title": "AI Tools Worth Watching", "bullets": bullets(tools, "name")},
        {
            "slide": 4,
            "title": "Testing & Quality",
            "bullets": [(content.get("testing") or {}).get("title", "Quality engineering insight")],
        },
        {
            "slide": 5,
            "title": "Enterprise AI Adoption",
            "bullets": [(content.get("enterprise") or {}).get("use_case", "Enterprise insight")],
        },
        {
            "slide": 6,
            "title": "Research Watch",
            "bullets": [(content.get("research") or {}).get("paper", "Research insight")],
        },
        {
            "slide": 7,
            "title": "Coding Agent Benchmarks",
            "bullets": [(content.get("benchmark") or {}).get("title", "Benchmark insight")],
        },
        {
            "slide": 8,
            "title": "Trend Signals",
            "bullets": [t["signal"] for t in content.get("trends", [])[:3]] or ["Emerging signals"],
        },
        {
            "slide": 9,
            "title": "Final Takeaways",
            "bullets": content.get("final_takeaways", [])[:3] or ["Pilot before adoption"],
        },
        {
            "slide": 10,
            "title": "Read & Subscribe",
            "bullets": ["Full issue link in comments", "Follow for weekly AI + QE insights"],
        },
    ]
    return slides


def email_subject_lines(content: dict, brand: BrandVoice) -> list[str]:
    cover = content.get("cover", {})
    issue = cover.get("issue_number")
    stories = content.get("top_stories", [])
    lead = stories[0]["headline"] if stories else "This week in AI engineering"
    return [
        f"{brand.name}: Issue {issue}",
        f"This week: {lead}",
        f"AI & QE Weekly #{issue}: what changed and why it matters",
        "Agentic AI, evaluation, and testing - your weekly briefing",
        f"{lead} (and what it means for your team)",
        "5-minute read: this week's AI engineering signals",
        "What QA and engineering leaders should know this week",
        "Verified AI news, no hype - this week's issue",
        f"Issue {issue}: tools, research, and benchmark watch",
        "Your weekly AI + Quality Engineering digest is here",
    ]
