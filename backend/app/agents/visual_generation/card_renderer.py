"""Programmatic card rendering with Pillow (original visuals, copyright-safe)."""

from __future__ import annotations

from PIL import Image, ImageDraw

from app.agents.visual_generation import layout_engine as le
from app.agents.visual_generation.brand_config import BrandConfig

# Per-spec text limits for carousel slides.
MAX_TITLE_WORDS = 8
MAX_BODY_WORDS = 35
MAX_FOOTER_WORDS = 12


def _truncate_words(text: str, max_words: int) -> str:
    words = (text or "").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip(",;.") + "…"


def render_card(
    brand: BrandConfig,
    *,
    size: tuple[int, int],
    label: str,
    title: str,
    body: str,
    footer_left: str,
    footer_right: str = "",
    badge: str | None = None,
    attribution: str | None = None,
) -> Image.Image:
    """Render a single branded text card. Returns a PIL image."""
    width, height = size
    margin = brand.safe_margin
    img = le.new_canvas(size, brand, inverse=True)
    draw = ImageDraw.Draw(img)
    content_w = width - 2 * margin

    # Badge (e.g. slide number) top-right.
    if badge:
        bfont = le.get_font(26, bold=True)
        bw = draw.textlength(badge, font=bfont)
        draw.text((width - margin - bw, margin), badge, font=bfont, fill=brand.muted_color)

    # Logo / brand name top-left.
    draw.text((margin, margin), brand.logo_text, font=le.get_font(26, bold=True),
              fill=brand.inverse_text_color)

    # Section label + accent bar.
    y = margin + 90
    label_font = le.get_font(28, bold=True)
    draw.text((margin, y), label.upper(), font=label_font, fill=brand.accent_color)
    y += 44
    le.accent_bar(draw, (margin, y), 120, brand.accent_color)
    y += 36

    # Title (large).
    title_font = le.get_font(56, bold=True)
    y = le.draw_paragraph(draw, (margin, y), _truncate_words(title, MAX_TITLE_WORDS),
                          title_font, brand.inverse_text_color, content_w, line_spacing=8)
    y += 16

    # Body.
    body_font = le.get_font(32)
    le.draw_paragraph(draw, (margin, y), _truncate_words(body, MAX_BODY_WORDS),
                      body_font, brand.surface_color, content_w, line_spacing=12)

    # Attribution (source) above footer.
    if attribution:
        attr_font = le.get_font(20)
        draw.text((margin, height - margin // 2 - 56),
                  _truncate_words(attribution, 16), font=attr_font, fill=brand.muted_color)

    le.draw_footer(draw, size, brand, _truncate_words(footer_left, MAX_FOOTER_WORDS), footer_right)
    return img


def _attr(citation: dict | None) -> str | None:
    if not citation:
        return None
    name = citation.get("source_name")
    date = (citation.get("publication_date") or "")[:10]
    if name and date:
        return f"Source: {name} · {date}"
    return f"Source: {name}" if name else None


def summary_card(brand: BrandConfig, story: dict, issue: int | None, size) -> Image.Image:
    return render_card(
        brand, size=size, label="Top Story", title=story.get("headline", "Top Story"),
        body=story.get("what_happened", ""),
        footer_left=brand.footer_text, footer_right=f"Issue {issue} · {le.utcstamp()}",
        attribution=_attr(story.get("citation")),
    )


def tool_card(brand: BrandConfig, tool: dict, issue: int | None, size) -> Image.Image:
    return render_card(
        brand, size=size, label="AI Tool Worth Watching", title=tool.get("name", "Tool"),
        body=tool.get("what_it_does", ""),
        footer_left=brand.footer_text, footer_right=f"Issue {issue} · {le.utcstamp()}",
        attribution=_attr(tool.get("citation")),
    )


def research_card(brand: BrandConfig, research: dict, issue: int | None, size) -> Image.Image:
    return render_card(
        brand, size=size, label="Research Watch", title=research.get("paper", "Research"),
        body=research.get("key_findings", ""),
        footer_left=brand.footer_text, footer_right=f"Issue {issue} · {le.utcstamp()}",
        attribution=_attr(research.get("citation")),
    )


def benchmark_card(brand: BrandConfig, benchmark: dict, issue: int | None, size) -> Image.Image:
    return render_card(
        brand, size=size, label="Coding Agent Benchmark", title=benchmark.get("title", "Benchmark"),
        body=benchmark.get("what_improved", ""),
        footer_left=brand.footer_text, footer_right=f"Issue {issue} · {le.utcstamp()}",
        attribution=_attr(benchmark.get("citation")),
    )


def takeaway_card(brand: BrandConfig, takeaways: list[str], issue: int | None, size) -> Image.Image:
    body = " • ".join(takeaways[:3]) if takeaways else "Pilot before broad adoption."
    return render_card(
        brand, size=size, label="Final Takeaways", title="What to do this week",
        body=body, footer_left=brand.footer_text,
        footer_right=f"Issue {issue} · {le.utcstamp()}",
    )
