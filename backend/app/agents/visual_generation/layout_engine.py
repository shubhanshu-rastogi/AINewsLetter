"""Low-level Pillow layout primitives: fonts, backgrounds, text, footers."""

from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from app.agents.visual_generation.brand_config import BrandConfig

# Candidate TrueType fonts across common environments (fallback to default).
_TTF_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuSans.ttf",
]
_TTF_BOLD = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "DejaVuSans-Bold.ttf",
]


@lru_cache(maxsize=64)
def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (_TTF_BOLD if bold else _TTF_CANDIDATES):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def gradient_background(size: tuple[int, int], top: tuple, bottom: tuple) -> Image.Image:
    width, height = size
    base = Image.new("RGB", size, top)
    top_img = Image.new("RGB", size, bottom)
    mask = Image.new("L", size)
    mask_data = []
    for y in range(height):
        mask_data.extend([int(255 * (y / max(height - 1, 1)))] * width)
    mask.putdata(mask_data)
    base.paste(top_img, (0, 0), mask)
    return base


def new_canvas(size: tuple[int, int], brand: BrandConfig, *, inverse: bool = True) -> Image.Image:
    if brand.background_style == "gradient" and inverse:
        return gradient_background(size, brand.bg_color, brand.bg_accent_color)
    color = brand.bg_color if inverse else brand.surface_color
    return Image.new("RGB", size, color)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = (text or "").split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def draw_paragraph(
    draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill,
    max_width: int, line_spacing: int = 10,
) -> int:
    x, y = xy
    for line in wrap_text(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        ascent, descent = font.getmetrics()
        y += ascent + descent + line_spacing
    return y


def accent_bar(draw: ImageDraw.ImageDraw, xy: tuple[int, int], width: int, color, height: int = 8) -> None:
    x, y = xy
    draw.rounded_rectangle([x, y, x + width, y + height], radius=height // 2, fill=color)


def draw_footer(
    draw: ImageDraw.ImageDraw, size: tuple[int, int], brand: BrandConfig,
    left_text: str, right_text: str = "", *, fill=None,
) -> None:
    width, height = size
    font = get_font(22)
    fill = fill or brand.muted_color
    margin = brand.safe_margin
    y = height - margin // 2 - 22
    draw.text((margin, y), left_text[:90], font=font, fill=fill)
    if right_text:
        rw = draw.textlength(right_text, font=font)
        draw.text((width - margin - rw, y), right_text, font=font, fill=fill)


def utcstamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def to_png_bytes(image: Image.Image) -> bytes:
    import io

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
