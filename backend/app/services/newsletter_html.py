"""Render a stored newsletter draft as a self-contained HTML web page.

Produces a shareable, light-themed page from the structured ``NewsletterDraft``
content (no external assets, all styles inline). Used by
``GET /api/newsletters/{id}/html`` so every issue has its own web page even when
external publishing is simulated.
"""

from __future__ import annotations

from html import escape
from typing import Any

from app.core.config import settings
from app.models.newsletter import Newsletter


def _esc(value: Any) -> str:
    return escape("" if value is None else str(value))


def _citation(cit: dict | None) -> str:
    if not cit:
        return ""
    url = cit.get("source_url")
    name = cit.get("source_name") or cit.get("title") or url
    if not url:
        return f'<div class="src">Source: {_esc(name)}</div>' if name else ""
    return f'<div class="src">Source: <a href="{_esc(url)}" target="_blank" rel="noopener">{_esc(name)}</a></div>'


def _story(s: dict) -> str:
    parts = [f'<h3>{_esc(s.get("headline"))}</h3>']
    if s.get("what_happened"):
        parts.append(f'<p>{_esc(s["what_happened"])}</p>')
    if s.get("why_it_matters"):
        parts.append(f'<p><strong>Why it matters.</strong> {_esc(s["why_it_matters"])}</p>')
    if s.get("testing_implications"):
        parts.append(f'<p><strong>Testing implications.</strong> {_esc(s["testing_implications"])}</p>')
    if s.get("key_takeaway"):
        parts.append(f'<p class="takeaway">{_esc(s["key_takeaway"])}</p>')
    parts.append(_citation(s.get("citation")))
    return f'<article class="story">{"".join(parts)}</article>'


def _tool(t: dict) -> str:
    parts = [f'<h3>{_esc(t.get("name"))}</h3>']
    if t.get("what_it_does"):
        parts.append(f'<p>{_esc(t["what_it_does"])}</p>')
    cases = t.get("use_cases") or []
    if cases:
        items = "".join(f"<li>{_esc(c)}</li>" for c in cases)
        parts.append(f"<ul>{items}</ul>")
    parts.append(_citation(t.get("citation")))
    return f'<article class="story">{"".join(parts)}</article>'


def _insight_block(title: str, d: dict | None, fields: list[tuple[str, str]]) -> str:
    if not d:
        return ""
    rows = []
    head = d.get("title") or d.get("paper") or d.get("use_case")
    if head:
        rows.append(f"<h3>{_esc(head)}</h3>")
    for key, label in fields:
        if d.get(key):
            rows.append(f"<p><strong>{_esc(label)}</strong> {_esc(d[key])}</p>")
    rows.append(_citation(d.get("citation")))
    if len(rows) <= 1 and not any("<p>" in r for r in rows):
        return ""
    return f'<section class="block"><h2>{_esc(title)}</h2>{"".join(rows)}</section>'


def _trend(t: dict) -> str:
    parts = [f'<h3>{_esc(t.get("signal"))}</h3>']
    if t.get("evidence"):
        parts.append(f'<p>{_esc(t["evidence"])}</p>')
    if t.get("prediction"):
        parts.append(f'<p><strong>Prediction.</strong> {_esc(t["prediction"])}</p>')
    return f'<article class="story">{"".join(parts)}</article>'


_STYLE = """
:root{color-scheme:light}
*{box-sizing:border-box}
body{margin:0;background:#f4f5f7;color:#1c2230;font:16px/1.65 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:0 20px 64px}
.masthead{text-align:center;padding:48px 0 28px;border-bottom:3px solid #1c2230;margin-bottom:8px}
.masthead h1{font-size:30px;margin:0 0 6px;letter-spacing:-0.02em}
.masthead .tag{color:#5a6275;margin:0 0 14px}
.meta{font-size:13px;color:#6b7280;display:flex;gap:14px;justify-content:center;flex-wrap:wrap}
.meta span{display:inline-flex;gap:5px}
.summary{background:#fff;border:1px solid #e3e6ec;border-radius:12px;padding:20px 24px;margin:24px 0}
.summary p{margin:0}
h2{font-size:14px;text-transform:uppercase;letter-spacing:0.06em;color:#3b82f6;margin:36px 0 6px;border-bottom:1px solid #e3e6ec;padding-bottom:6px}
.block{margin-top:8px}
.story{background:#fff;border:1px solid #e3e6ec;border-radius:12px;padding:18px 22px;margin:14px 0}
.story h3{margin:0 0 8px;font-size:19px}
.story p{margin:8px 0}
.takeaway{background:#eef4ff;border-left:3px solid #3b82f6;border-radius:0 6px 6px 0;padding:8px 12px;font-size:15px}
.src{font-size:13px;color:#6b7280;margin-top:10px}
.src a{color:#2563eb}
ul{margin:8px 0;padding-left:20px}
.takeaways{background:#fff;border:1px solid #e3e6ec;border-radius:12px;padding:18px 22px;margin:14px 0}
.footer{text-align:center;margin-top:48px;padding-top:24px;border-top:1px solid #e3e6ec;color:#6b7280;font-size:14px}
.footer a{color:#2563eb}
.cta{display:inline-block;margin-top:10px;background:#1c2230;color:#fff;text-decoration:none;padding:10px 22px;border-radius:8px;font-weight:600}
.notice{text-align:center;padding:80px 20px;color:#6b7280}
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<title>{_esc(title)}</title><style>{_STYLE}</style></head>"
        f"<body><div class='wrap'>{body}</div></body></html>"
    )


def render_newsletter_html(newsletter: Newsletter, content: dict | None) -> str:
    """Render the full newsletter page, or a friendly placeholder if no draft."""
    issue = newsletter.issue_number
    if not content:
        body = (
            "<div class='masthead'><h1>Newsletter not available yet</h1>"
            f"<p class='tag'>Issue #{_esc(issue)} has no generated draft.</p></div>"
            "<div class='notice'>This issue hasn't produced content yet. "
            "Trigger or finish its run, then reload this page.</div>"
        )
        return _page(f"Issue #{issue}", body)

    cover = content.get("cover") or {}
    name = cover.get("title") or newsletter.title or settings.NEWSLETTER_NAME
    tagline = cover.get("tagline") or settings.NEWSLETTER_TAGLINE
    pub_date = cover.get("publication_date") or (
        newsletter.publication_date.date().isoformat() if newsletter.publication_date else ""
    )
    reading = cover.get("estimated_reading_time_minutes")

    parts: list[str] = []
    parts.append(
        "<div class='masthead'>"
        f"<h1>{_esc(name)}</h1>"
        f"<p class='tag'>{_esc(tagline)}</p>"
        "<div class='meta'>"
        f"<span>Issue #{_esc(issue)}</span>"
        + (f"<span>{_esc(pub_date)}</span>" if pub_date else "")
        + (f"<span>{_esc(reading)} min read</span>" if reading else "")
        + "</div></div>"
    )

    if content.get("executive_summary"):
        parts.append(f"<div class='summary'><p>{_esc(content['executive_summary'])}</p></div>")

    stories = content.get("top_stories") or []
    if stories:
        parts.append("<h2>Top stories</h2>")
        parts.extend(_story(s) for s in stories)

    tools = content.get("tools") or []
    if tools:
        parts.append("<h2>Tools worth watching</h2>")
        parts.extend(_tool(t) for t in tools)

    parts.append(
        _insight_block(
            "Testing &amp; quality",
            content.get("testing"),
            [("insight", "Insight."), ("recommendation", "Recommendation.")],
        )
    )
    parts.append(
        _insight_block(
            "Enterprise AI adoption",
            content.get("enterprise"),
            [("summary", "Summary."), ("lessons_learned", "Lessons."), ("recommendations", "Recommendations.")],
        )
    )
    parts.append(
        _insight_block(
            "Research watch",
            content.get("research"),
            [("key_findings", "Findings."), ("practical_implications", "Implications.")],
        )
    )
    parts.append(
        _insight_block(
            "Benchmark watch",
            content.get("benchmark"),
            [("what_improved", "What improved."), ("learnings", "Learnings.")],
        )
    )

    trends = content.get("trends") or []
    if trends:
        parts.append("<h2>Weekly trend signals</h2>")
        parts.extend(_trend(t) for t in trends)

    takeaways = content.get("final_takeaways") or []
    if takeaways:
        items = "".join(f"<li>{_esc(t)}</li>" for t in takeaways)
        parts.append(f"<h2>Final takeaways</h2><div class='takeaways'><ul>{items}</ul></div>")

    sub = settings.NEWSLETTER_SUBSCRIBE_URL
    parts.append(
        "<div class='footer'>"
        f"<div>{_esc(name)} — Issue #{_esc(issue)}</div>"
        + (f"<a class='cta' href='{_esc(sub)}' target='_blank' rel='noopener'>Subscribe</a>" if sub else "")
        + "</div>"
    )

    return _page(f"{name} — Issue #{issue}", "".join(parts))
