"""Cover image generation: AI image (optional/mockable) or programmatic fallback."""

from __future__ import annotations

import base64

from PIL import Image, ImageDraw

from app.agents.visual_generation import layout_engine as le
from app.agents.visual_generation.brand_config import BrandConfig
from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import GenerationMethod

logger = get_logger("visuals.image")


def programmatic_cover(brand: BrandConfig, content: dict) -> Image.Image:
    """Render an original cover image with Pillow (no external API)."""
    size = brand.dim("newsletter_cover").as_tuple()
    width, height = size
    margin = brand.safe_margin
    img = le.gradient_background(size, brand.bg_color, brand.bg_accent_color)
    draw = ImageDraw.Draw(img)

    cover = content.get("cover", {})
    issue = cover.get("issue_number")

    draw.text((margin, margin), brand.logo_text, font=le.get_font(34, bold=True), fill=brand.inverse_text_color)

    y = height // 2 - 80
    le.accent_bar(draw, (margin, y - 30), 140, brand.accent_color)
    le.draw_paragraph(
        draw,
        (margin, y),
        "Weekly AI & Quality Engineering Briefing",
        le.get_font(60, bold=True),
        brand.inverse_text_color,
        width - 2 * margin,
        line_spacing=8,
    )

    draw.text((margin, height - margin - 70), brand.tagline[:80], font=le.get_font(24), fill=brand.surface_color)
    le.draw_footer(
        draw, size, brand, f"Issue {issue}" if issue else "Weekly Edition", le.utcstamp(), fill=brand.accent_color
    )
    return img


async def ai_generate_image(prompt: str, size: tuple[int, int]) -> bytes:
    """Generate a cover via OpenAI Images API. Mocked in tests."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    result = await client.images.generate(
        model=settings.AI_IMAGE_MODEL,
        prompt=prompt,
        size=f"{size[0]}x{size[1]}",
    )
    return base64.b64decode(result.data[0].b64_json)


async def generate_cover(
    brand: BrandConfig, content: dict, prompt: str
) -> tuple[bytes, GenerationMethod, tuple[int, int]]:
    """Return (png_bytes, method, (w,h)). Falls back to programmatic on AI failure."""
    size = brand.dim("newsletter_cover").as_tuple()
    if settings.ENABLE_AI_IMAGES:
        try:
            data = await ai_generate_image(prompt, size)
            logger.info("cover_generated", method="ai_image")
            return data, GenerationMethod.AI_IMAGE, size
        except Exception as exc:  # noqa: BLE001 - fall back, never block the pipeline
            logger.warning("ai_image_failed_fallback", error=str(exc))
    image = programmatic_cover(brand, content)
    logger.info("cover_generated", method="programmatic")
    return le.to_png_bytes(image), GenerationMethod.PROGRAMMATIC, size
