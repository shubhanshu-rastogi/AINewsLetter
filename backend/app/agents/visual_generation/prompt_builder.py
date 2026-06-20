"""Prompt builder for AI-generated visuals (cover / conceptual graphics)."""

from __future__ import annotations

from app.agents.visual_generation.brand_config import BrandConfig

AUDIENCE = "IT leaders, engineering managers, QA leaders, SDETs, and software architects"
POSITIONING = "Agentic AI, AI engineering, QA, and enterprise technology leadership"

_RESTRICTIONS = [
    "no copyrighted logos or brand marks",
    "no realistic screenshots or fake UI",
    "no fake product logos",
    "no meme style",
    "no exaggerated or sci-fi AI imagery",
    "no text artifacts or garbled words",
]

_STYLE = "clean, professional, minimal, enterprise-friendly, high-contrast, abstract geometric, LinkedIn-ready"


def build_visual_prompt(
    visual_type: str,
    theme: str,
    brand: BrandConfig,
    *,
    aspect_ratio: str = "1200x630",
) -> str:
    """Compose a safe, on-brand prompt for an AI image model."""
    parts = [
        f"Create a {visual_type} background image for '{brand.logo_text}'.",
        f"Audience: {AUDIENCE}.",
        f"Positioning: {POSITIONING}.",
        f"Content theme: {theme}.",
        f"Style: {_STYLE}.",
        f"Aspect ratio: {aspect_ratio}.",
        "Use a deep navy-to-blue palette with subtle sky-blue accents.",
        "Restrictions: " + "; ".join(_RESTRICTIONS) + ".",
        "Leave clear negative space for overlaid title text.",
    ]
    return " ".join(parts)
