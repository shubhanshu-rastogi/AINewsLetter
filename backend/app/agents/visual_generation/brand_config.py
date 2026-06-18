"""Reusable brand configuration for visuals.

Single source of truth for colors, fonts, dimensions, and layout variables so
brand values are never hardcoded across renderers.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import settings


@dataclass(frozen=True, slots=True)
class Dimensions:
    width: int
    height: int

    def as_tuple(self) -> tuple[int, int]:
        return (self.width, self.height)


@dataclass(frozen=True, slots=True)
class BrandConfig:
    logo_text: str
    tagline: str
    footer_text: str

    # Typography
    primary_font: str = "primary"
    secondary_font: str = "secondary"

    # Palette (enterprise, high-contrast, minimal)
    bg_color: tuple[int, int, int] = (15, 23, 42)        # slate-900
    bg_accent_color: tuple[int, int, int] = (30, 58, 138)  # blue-900
    surface_color: tuple[int, int, int] = (248, 250, 252)  # slate-50
    text_color: tuple[int, int, int] = (15, 23, 42)
    inverse_text_color: tuple[int, int, int] = (248, 250, 252)
    accent_color: tuple[int, int, int] = (56, 189, 248)   # sky-400
    muted_color: tuple[int, int, int] = (100, 116, 139)   # slate-500

    # Layout
    background_style: str = "gradient"
    border_radius: int = 24
    safe_margin: int = 64
    layout_grid: int = 12

    # Canvas sizes
    dimensions: dict[str, Dimensions] = field(
        default_factory=lambda: {
            "newsletter_cover": Dimensions(1200, 630),
            "linkedin_carousel": Dimensions(1080, 1080),
            "linkedin_post": Dimensions(1200, 627),
            "email_card": Dimensions(1200, 800),
        }
    )

    def dim(self, key: str) -> Dimensions:
        return self.dimensions[key]


def load_brand_config() -> BrandConfig:
    return BrandConfig(
        logo_text=settings.NEWSLETTER_NAME,
        tagline=settings.NEWSLETTER_TAGLINE,
        footer_text=f"{settings.NEWSLETTER_NAME} · Practical AI insights",
    )
