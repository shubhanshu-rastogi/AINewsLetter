"""Email preparation (HTML + plain text). No delivery provider yet - interface only."""

from __future__ import annotations

import html

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("publishing.email")


def _escape(text: str | None) -> str:
    return html.escape(text or "")


def prepare_email(package: dict, cover_image_url: str | None = None) -> dict:
    """Build subject, preview text, HTML, and plain-text versions of the issue."""
    content = package.get("newsletter_draft", {}) or {}
    cover = content.get("cover", {})
    title = package.get("title") or cover.get("title") or "AI & Quality Engineering Weekly"
    issue = package.get("issue_number") or cover.get("issue_number")
    summary = content.get("executive_summary", "")
    stories = content.get("top_stories", [])
    tools = content.get("tools", [])
    subscribe_url = settings.NEWSLETTER_SUBSCRIBE_URL

    subject = f"{title} — Issue {issue}" if issue else title
    preview_text = (summary[:120] + "…") if len(summary) > 120 else summary

    # --- HTML ---
    parts: list[str] = [f"<h1>{_escape(title)}</h1>"]
    if issue:
        parts.append(f"<p><em>Issue {issue}</em></p>")
    if cover_image_url:
        parts.append(f'<img src="{_escape(cover_image_url)}" alt="cover" width="600" />')
    if summary:
        parts.append(f"<h2>This week</h2><p>{_escape(summary)}</p>")
    if stories:
        parts.append("<h2>Top Stories</h2><ul>")
        for s in stories:
            parts.append(f"<li><strong>{_escape(s.get('headline'))}</strong>: {_escape(s.get('what_happened'))}</li>")
        parts.append("</ul>")
    if tools:
        parts.append("<h2>AI Tools Worth Watching</h2><ul>")
        for t in tools:
            parts.append(f"<li><strong>{_escape(t.get('name'))}</strong>: {_escape(t.get('what_it_does'))}</li>")
        parts.append("</ul>")
    parts.append(
        f'<hr/><p><a href="{_escape(subscribe_url)}">Subscribe</a> to '
        f"{_escape(title)} for weekly AI + Quality Engineering insights.</p>"
    )
    html_body = "\n".join(parts)

    # --- Plain text ---
    text_lines = [title]
    if issue:
        text_lines.append(f"Issue {issue}")
    if summary:
        text_lines += ["", "This week:", summary]
    if stories:
        text_lines += ["", "Top Stories:"]
        text_lines += [f"- {s.get('headline')}: {s.get('what_happened')}" for s in stories]
    if tools:
        text_lines += ["", "AI Tools Worth Watching:"]
        text_lines += [f"- {t.get('name')}: {t.get('what_it_does')}" for t in tools]
    text_lines += ["", f"Subscribe: {subscribe_url}"]
    text_body = "\n".join(text_lines)

    logger.info("email_package_prepared", subject=subject, html_chars=len(html_body))
    return {
        "subject": subject,
        "preview_text": preview_text,
        "html": html_body,
        "text": text_body,
        "subscribe_url": subscribe_url,
    }
