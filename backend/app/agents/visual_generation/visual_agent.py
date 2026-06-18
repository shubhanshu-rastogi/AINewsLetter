"""VisualGenerationAgent - generates, stores, and versions newsletter visuals."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.visual_generation import (
    card_renderer,
    carousel_builder,
    image_generator,
    layout_engine,
    prompt_builder,
    visual_versioning,
)
from app.agents.visual_generation.asset_storage import AssetStorage, get_storage, newsletter_dir
from app.agents.visual_generation.brand_config import BrandConfig, load_brand_config
from app.agents.visual_generation.exceptions import VisualNotFoundError
from app.core.logging import get_logger
from app.models.enums import GenerationMethod, VisualKind, VisualStatus, VisualType
from app.models.generated_visual import GeneratedVisual
from app.models.newsletter_draft import NewsletterDraft

logger = get_logger("visuals")

# Coarse legacy enum mapping for the existing visual_type column.
_COARSE = {
    VisualKind.COVER: VisualType.HERO,
    VisualKind.CAROUSEL_SLIDE: VisualType.SOCIAL,
    VisualKind.SUMMARY_CARD: VisualType.SECTION,
    VisualKind.TOOL_CARD: VisualType.SECTION,
    VisualKind.RESEARCH_CARD: VisualType.SECTION,
    VisualKind.BENCHMARK_CARD: VisualType.SECTION,
    VisualKind.TAKEAWAY_CARD: VisualType.SECTION,
}


class VisualGenerationAgent:
    def __init__(
        self, session_factory: Callable[[], AsyncSession], storage: AssetStorage | None = None
    ) -> None:
        self.session_factory = session_factory
        self.brand: BrandConfig = load_brand_config()
        self.storage = storage or get_storage()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def build_visual_prompt(self, visual_type: str, theme: str, aspect_ratio: str = "1200x630") -> str:
        return prompt_builder.build_visual_prompt(visual_type, theme, self.brand, aspect_ratio=aspect_ratio)

    def save_asset(self, newsletter_id: str, subdir: str, filename: str, data: bytes) -> str:
        rel = f"{newsletter_dir(newsletter_id, subdir)}/{filename}"
        return self.storage.save_bytes(rel, data)

    def _save_image(self, newsletter_id: str, subdir: str, filename: str, image: Image.Image) -> str:
        return self.save_asset(newsletter_id, subdir, filename, layout_engine.to_png_bytes(image))

    def create_visual_metadata(self, visual: GeneratedVisual) -> dict[str, Any]:
        return {
            "id": str(visual.id),
            "visual_kind": visual.visual_kind,
            "visual_type": visual.visual_type.value if visual.visual_type else None,
            "title": visual.title,
            "description": visual.description,
            "generation_method": visual.generation_method,
            "file_path": visual.file_path,
            "preview_url": self.storage.url_for(visual.file_path) if visual.file_path else None,
            "file_format": visual.file_format,
            "width": visual.width,
            "height": visual.height,
            "slide_number": visual.slide_number,
            "version": visual.version,
            "status": visual.status,
        }

    def _record(
        self, session: AsyncSession, newsletter_id: uuid.UUID, *, kind: VisualKind,
        title: str, description: str, file_path: str, method: GenerationMethod,
        size: tuple[int, int], slide_number: int | None = None, prompt: str | None = None,
    ) -> GeneratedVisual:
        visual = GeneratedVisual(
            newsletter_id=newsletter_id,
            visual_type=_COARSE[kind],
            visual_kind=kind.value,
            title=title[:512],
            description=description,
            prompt_used=prompt,
            generation_method=method.value,
            file_path=file_path,
            file_format="png",
            width=size[0],
            height=size[1],
            slide_number=slide_number,
            version=1,
            status=VisualStatus.GENERATED.value,
        )
        session.add(visual)
        return visual

    # ------------------------------------------------------------------ #
    # Per-visual generation
    # ------------------------------------------------------------------ #
    async def generate_cover_image(
        self, session: AsyncSession, newsletter_id: str, content: dict
    ) -> GeneratedVisual:
        prompt = self.build_visual_prompt("newsletter cover", "this week's AI engineering highlights")
        data, method, size = await image_generator.generate_cover(self.brand, content, prompt)
        path = self.save_asset(newsletter_id, "cover", "cover.png", data)
        return self._record(
            session, uuid.UUID(newsletter_id), kind=VisualKind.COVER,
            title=f"{self.brand.logo_text} cover", description="Newsletter cover image",
            file_path=path, method=method, size=size, prompt=prompt,
        )

    def generate_carousel_slide(
        self, session: AsyncSession, newsletter_id: str, content: dict, spec: dict,
        slide_number: int, issue: int | None,
    ) -> GeneratedVisual:
        size = self.brand.dim("linkedin_carousel").as_tuple()
        image = carousel_builder.render_slide(self.brand, spec, slide_number, issue, size)
        path = self._save_image(newsletter_id, "carousel", f"slide_{slide_number:02d}.png", image)
        return self._record(
            session, uuid.UUID(newsletter_id), kind=VisualKind.CAROUSEL_SLIDE,
            title=spec["title"], description=spec["label"], file_path=path,
            method=GenerationMethod.PROGRAMMATIC, size=size, slide_number=slide_number,
        )

    async def generate_carousel(
        self, session: AsyncSession, newsletter_id: str, content: dict, issue: int | None
    ) -> list[GeneratedVisual]:
        specs = carousel_builder.build_slide_specs(content, self.brand)
        visuals = [
            self.generate_carousel_slide(session, newsletter_id, content, spec, i, issue)
            for i, spec in enumerate(specs, start=1)
        ]
        logger.info("carousel_generated", slides=len(visuals))
        return visuals

    def _card(
        self, session: AsyncSession, newsletter_id: str, kind: VisualKind, image: Image.Image,
        filename: str, title: str, description: str, index: int,
    ) -> GeneratedVisual:
        size = self.brand.dim("email_card").as_tuple()
        path = self._save_image(newsletter_id, "cards", filename, image)
        return self._record(
            session, uuid.UUID(newsletter_id), kind=kind, title=title,
            description=description, file_path=path, method=GenerationMethod.PROGRAMMATIC,
            size=size, slide_number=index,
        )

    def generate_summary_card(self, session, newsletter_id, story, issue, index) -> GeneratedVisual:
        size = self.brand.dim("email_card").as_tuple()
        image = card_renderer.summary_card(self.brand, story, issue, size)
        return self._card(session, newsletter_id, VisualKind.SUMMARY_CARD, image,
                          f"summary_{index}.png", story.get("headline", "Top Story"), "Top story card", index)

    def generate_tool_card(self, session, newsletter_id, tool, issue, index) -> GeneratedVisual:
        size = self.brand.dim("email_card").as_tuple()
        image = card_renderer.tool_card(self.brand, tool, issue, size)
        return self._card(session, newsletter_id, VisualKind.TOOL_CARD, image,
                          f"tool_{index}.png", tool.get("name", "Tool"), "AI tool card", index)

    def generate_research_card(self, session, newsletter_id, research, issue) -> GeneratedVisual:
        size = self.brand.dim("email_card").as_tuple()
        image = card_renderer.research_card(self.brand, research, issue, size)
        return self._card(session, newsletter_id, VisualKind.RESEARCH_CARD, image,
                          "research.png", research.get("paper", "Research"), "Research card", 0)

    def generate_benchmark_card(self, session, newsletter_id, benchmark, issue) -> GeneratedVisual:
        size = self.brand.dim("email_card").as_tuple()
        image = card_renderer.benchmark_card(self.brand, benchmark, issue, size)
        return self._card(session, newsletter_id, VisualKind.BENCHMARK_CARD, image,
                          "benchmark.png", benchmark.get("title", "Benchmark"), "Benchmark card", 0)

    def generate_takeaway_card(self, session, newsletter_id, takeaways, issue) -> GeneratedVisual:
        size = self.brand.dim("email_card").as_tuple()
        image = card_renderer.takeaway_card(self.brand, takeaways, issue, size)
        return self._card(session, newsletter_id, VisualKind.TAKEAWAY_CARD, image,
                          "takeaway.png", "Final takeaways", "Takeaways card", 0)

    # ------------------------------------------------------------------ #
    # Orchestration
    # ------------------------------------------------------------------ #
    async def _load_content(self, session: AsyncSession, newsletter_id: str, content: dict | None) -> dict:
        if content:
            return content
        draft = await session.scalar(
            select(NewsletterDraft).where(NewsletterDraft.newsletter_id == uuid.UUID(newsletter_id))
        )
        return draft.content if draft and draft.content else {}

    async def generate_all_visuals(
        self, newsletter_id: str, content: dict | None = None
    ) -> dict[str, Any]:
        logger.info("visual_generation_started", newsletter_id=newsletter_id)
        async with self.session_factory() as session:
            content = await self._load_content(session, newsletter_id, content)
            issue = content.get("cover", {}).get("issue_number")
            nid = uuid.UUID(newsletter_id)

            # Regenerate the full set (idempotent).
            await session.execute(
                delete(GeneratedVisual).where(GeneratedVisual.newsletter_id == nid)
            )

            visuals: list[GeneratedVisual] = []
            visuals.append(await self.generate_cover_image(session, newsletter_id, content))
            visuals.extend(await self.generate_carousel(session, newsletter_id, content, issue))
            for i, story in enumerate(content.get("top_stories", [])[:3]):
                visuals.append(self.generate_summary_card(session, newsletter_id, story, issue, i))
            for i, t in enumerate(content.get("tools", [])[:3]):
                visuals.append(self.generate_tool_card(session, newsletter_id, t, issue, i))
            if content.get("research"):
                visuals.append(self.generate_research_card(session, newsletter_id, content["research"], issue))
            if content.get("benchmark"):
                visuals.append(self.generate_benchmark_card(session, newsletter_id, content["benchmark"], issue))
            visuals.append(self.generate_takeaway_card(session, newsletter_id, content.get("final_takeaways", []), issue))

            await session.flush()
            metadata = {
                "newsletter_id": newsletter_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "brand": self.brand.logo_text,
                "issue_number": issue,
                "visuals": [self.create_visual_metadata(v) for v in visuals],
            }
            metadata_path = self.storage.write_json(
                f"{newsletter_dir(newsletter_id)}/metadata.json", metadata
            )
            visual_ids = [str(v.id) for v in visuals]
            await session.commit()

        logger.info("visual_generation_completed", newsletter_id=newsletter_id, count=len(visual_ids))
        return {
            "newsletter_id": newsletter_id,
            "visual_ids": visual_ids,
            "carousel_slides": sum(1 for v in visuals if v.visual_kind == VisualKind.CAROUSEL_SLIDE.value),
            "total": len(visual_ids),
            "metadata_path": metadata_path,
        }

    async def generate_cover_only(self, newsletter_id: str, content: dict | None = None) -> dict[str, Any]:
        async with self.session_factory() as session:
            content = await self._load_content(session, newsletter_id, content)
            nid = uuid.UUID(newsletter_id)
            await session.execute(
                delete(GeneratedVisual).where(
                    GeneratedVisual.newsletter_id == nid,
                    GeneratedVisual.visual_kind == VisualKind.COVER.value,
                )
            )
            visual = await self.generate_cover_image(session, newsletter_id, content)
            await session.flush()
            meta = self.create_visual_metadata(visual)
            await session.commit()
        return meta

    async def generate_carousel_only(self, newsletter_id: str, content: dict | None = None) -> dict[str, Any]:
        async with self.session_factory() as session:
            content = await self._load_content(session, newsletter_id, content)
            issue = content.get("cover", {}).get("issue_number")
            nid = uuid.UUID(newsletter_id)
            await session.execute(
                delete(GeneratedVisual).where(
                    GeneratedVisual.newsletter_id == nid,
                    GeneratedVisual.visual_kind == VisualKind.CAROUSEL_SLIDE.value,
                )
            )
            visuals = await self.generate_carousel(session, newsletter_id, content, issue)
            await session.flush()
            metas = [self.create_visual_metadata(v) for v in visuals]
            await session.commit()
        return {"newsletter_id": newsletter_id, "slides": metas, "count": len(metas)}

    async def version_visual(self, visual_id: str, reason: str = "regeneration") -> dict[str, Any]:
        logger.info("visual_versioned_started", visual_id=visual_id)
        async with self.session_factory() as session:
            visual = await session.get(GeneratedVisual, uuid.UUID(visual_id))
            if visual is None:
                raise VisualNotFoundError(visual_id)
            content = await self._load_content(session, str(visual.newsletter_id), None)
            issue = content.get("cover", {}).get("issue_number")

            session.add(visual_versioning.record_version(visual, reason=reason))
            new_version = visual.version + 1
            new_path = self._rerender(str(visual.newsletter_id), visual, content, issue, new_version)

            visual.version = new_version
            visual.file_path = new_path
            visual.status = VisualStatus.REGENERATED.value
            await session.commit()
            result = {"visual_id": visual_id, "version": new_version, "file_path": new_path}
        logger.info("visual_versioned", visual_id=visual_id, version=result["version"])
        return result

    def _rerender(self, newsletter_id: str, visual: GeneratedVisual, content: dict, issue, version: int) -> str:
        kind = VisualKind(visual.visual_kind)
        suffix = f"_v{version}"
        if kind == VisualKind.COVER:
            image = image_generator.programmatic_cover(self.brand, content)
            return self._save_image(newsletter_id, "cover", f"cover{suffix}.png", image)
        if kind == VisualKind.CAROUSEL_SLIDE:
            specs = carousel_builder.build_slide_specs(content, self.brand)
            n = visual.slide_number or 1
            image = carousel_builder.render_slide(
                self.brand, specs[n - 1], n, issue, self.brand.dim("linkedin_carousel").as_tuple()
            )
            return self._save_image(newsletter_id, "carousel", f"slide_{n:02d}{suffix}.png", image)

        size = self.brand.dim("email_card").as_tuple()
        idx = visual.slide_number or 0
        if kind == VisualKind.SUMMARY_CARD:
            stories = content.get("top_stories", [])
            image = card_renderer.summary_card(self.brand, stories[idx] if idx < len(stories) else {}, issue, size)
            name = f"summary_{idx}{suffix}.png"
        elif kind == VisualKind.TOOL_CARD:
            tools = content.get("tools", [])
            image = card_renderer.tool_card(self.brand, tools[idx] if idx < len(tools) else {}, issue, size)
            name = f"tool_{idx}{suffix}.png"
        elif kind == VisualKind.RESEARCH_CARD:
            image = card_renderer.research_card(self.brand, content.get("research") or {}, issue, size)
            name = f"research{suffix}.png"
        elif kind == VisualKind.BENCHMARK_CARD:
            image = card_renderer.benchmark_card(self.brand, content.get("benchmark") or {}, issue, size)
            name = f"benchmark{suffix}.png"
        else:  # TAKEAWAY_CARD
            image = card_renderer.takeaway_card(self.brand, content.get("final_takeaways", []), issue, size)
            name = f"takeaway{suffix}.png"
        return self._save_image(newsletter_id, "cards", name, image)

    def update_workflow_state(self, visual_ids: list[str]) -> dict[str, Any]:
        return {"visual_ids": visual_ids}
