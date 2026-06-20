"""Visual generation agent tests (AI image calls mocked)."""

from __future__ import annotations

import glob
import io
import os
import uuid

import pytest
from PIL import Image
from sqlalchemy import func, select

from app.agents.visual_generation import card_renderer, image_generator, prompt_builder
from app.agents.visual_generation.asset_storage import LocalAssetStorage
from app.agents.visual_generation.brand_config import load_brand_config
from app.agents.visual_generation.exceptions import VisualNotFoundError
from app.agents.visual_generation.visual_agent import VisualGenerationAgent
from app.core.config import settings
from app.models.enums import GenerationMethod, VisualKind
from app.models.generated_visual import GeneratedVisual
from app.models.newsletter import Newsletter
from app.models.newsletter_draft import NewsletterDraft
from app.models.visual_version import VisualVersion

CONTENT = {
    "cover": {"title": "AI & Quality Engineering Weekly", "issue_number": 1},
    "executive_summary": "This week: agents ship, evals mature, benchmarks climb.",
    "top_stories": [
        {
            "headline": "OpenAI ships Agents SDK",
            "what_happened": "Orchestration, guardrails, tracing.",
            "citation": {"source_name": "OpenAI", "publication_date": "2026-06-18"},
        },
        {
            "headline": "Eval gates go mainstream",
            "what_happened": "CI quality gates with LLM judging.",
            "citation": {"source_name": "InfoQ", "publication_date": "2026-06-17"},
        },
    ],
    "tools": [
        {
            "name": "Playwright AI",
            "what_it_does": "Generate tests from natural language.",
            "citation": {"source_name": "TestGuild", "publication_date": "2026-06-16"},
        }
    ],
    "testing": {"title": "LLM-as-judge", "insight": "Rubric-based judging in CI."},
    "research": {
        "paper": "Agent-authored tests",
        "key_findings": "High coverage.",
        "citation": {"source_name": "arXiv", "publication_date": "2026-06-15"},
    },
    "benchmark": {
        "title": "SWE-bench new high",
        "what_improved": "Top agents improve; gaps remain.",
        "citation": {"source_name": "SWE-bench", "publication_date": "2026-06-14"},
    },
    "trends": [{"signal": "Agent observability"}],
    "final_takeaways": ["Pilot agent frameworks", "Add eval gates", "Track benchmarks"],
}


@pytest.fixture
def storage(tmp_path):
    return LocalAssetStorage(str(tmp_path))


async def _seed_newsletter(session_factory, content=CONTENT) -> str:
    async with session_factory() as s:
        nl = Newsletter(title="x", issue_number=1)
        s.add(nl)
        await s.flush()
        s.add(NewsletterDraft(newsletter_id=nl.id, content=content, current_version=1))
        await s.commit()
        return str(nl.id)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (1200, 630), "navy").save(buf, format="PNG")
    return buf.getvalue()


# --- brand + prompt --- #
def test_brand_config() -> None:
    brand = load_brand_config()
    assert brand.logo_text == settings.NEWSLETTER_NAME
    assert brand.dim("newsletter_cover").as_tuple() == (1200, 630)
    assert brand.dim("linkedin_carousel").as_tuple() == (1080, 1080)
    assert brand.safe_margin > 0


def test_prompt_generation() -> None:
    brand = load_brand_config()
    prompt = prompt_builder.build_visual_prompt("newsletter cover", "agentic AI", brand, aspect_ratio="1200x630")
    assert "no copyrighted logos" in prompt
    assert "1200x630" in prompt
    assert brand.logo_text in prompt
    assert "no realistic screenshots" in prompt


# --- card rendering --- #
def test_programmatic_card_rendering() -> None:
    brand = load_brand_config()
    img = card_renderer.render_card(
        brand,
        size=(1080, 1080),
        label="Top Story",
        title="A very long headline that definitely exceeds eight words for truncation testing here",
        body="body text",
        footer_left="footer",
        badge="3/10",
    )
    assert img.size == (1080, 1080)
    assert img.mode == "RGB"


def test_truncate_words() -> None:
    out = card_renderer._truncate_words("one two three four five", 3)  # noqa: SLF001
    assert out.endswith("…") and out.startswith("one two three")


# --- cover: programmatic + AI (mocked) --- #
async def test_cover_programmatic_default(session_factory, storage) -> None:
    nid = await _seed_newsletter(session_factory)
    agent = VisualGenerationAgent(session_factory, storage=storage)
    meta = await agent.generate_cover_only(nid)
    assert meta["generation_method"] == GenerationMethod.PROGRAMMATIC.value
    assert os.path.exists(meta["file_path"])
    assert Image.open(meta["file_path"]).size == (1200, 630)


async def test_cover_ai_generation_mocked(session_factory, storage, monkeypatch) -> None:
    async def fake_ai(prompt, size):
        return _png_bytes()

    monkeypatch.setattr(image_generator, "ai_generate_image", fake_ai)
    monkeypatch.setattr(settings, "ENABLE_AI_IMAGES", True)
    try:
        nid = await _seed_newsletter(session_factory)
        agent = VisualGenerationAgent(session_factory, storage=storage)
        meta = await agent.generate_cover_only(nid)
    finally:
        monkeypatch.setattr(settings, "ENABLE_AI_IMAGES", False)
    assert meta["generation_method"] == GenerationMethod.AI_IMAGE.value


async def test_cover_ai_failure_falls_back(session_factory, storage, monkeypatch) -> None:
    async def boom(prompt, size):
        raise RuntimeError("image api down")

    monkeypatch.setattr(image_generator, "ai_generate_image", boom)
    monkeypatch.setattr(settings, "ENABLE_AI_IMAGES", True)
    try:
        nid = await _seed_newsletter(session_factory)
        agent = VisualGenerationAgent(session_factory, storage=storage)
        meta = await agent.generate_cover_only(nid)
    finally:
        monkeypatch.setattr(settings, "ENABLE_AI_IMAGES", False)
    assert meta["generation_method"] == GenerationMethod.PROGRAMMATIC.value


# --- carousel --- #
async def test_carousel_has_ten_slides(session_factory, storage) -> None:
    nid = await _seed_newsletter(session_factory)
    agent = VisualGenerationAgent(session_factory, storage=storage)
    result = await agent.generate_carousel_only(nid)
    assert result["count"] == 10
    assert all(s["width"] == 1080 and s["height"] == 1080 for s in result["slides"])
    assert sorted(s["slide_number"] for s in result["slides"]) == list(range(1, 11))


# --- full generation + persistence + files + dimensions --- #
async def test_generate_all_visuals(session_factory, storage) -> None:
    nid = await _seed_newsletter(session_factory)
    agent = VisualGenerationAgent(session_factory, storage=storage)
    result = await agent.generate_all_visuals(nid)

    assert result["carousel_slides"] == 10
    assert result["total"] == 17  # cover + 10 slides + 2 summary + 1 tool + research + benchmark + takeaway
    assert os.path.exists(result["metadata_path"])

    pngs = glob.glob(str(storage.root) + "/**/*.png", recursive=True)
    assert len(pngs) == 17

    async with session_factory() as s:
        rows = (await s.execute(select(GeneratedVisual))).scalars().all()
    assert len(rows) == 17
    cover = next(r for r in rows if r.visual_kind == VisualKind.COVER.value)
    assert (cover.width, cover.height) == (1200, 630)
    slide = next(r for r in rows if r.visual_kind == VisualKind.CAROUSEL_SLIDE.value)
    assert (slide.width, slide.height) == (1080, 1080)


async def test_visual_metadata_fields(session_factory, storage) -> None:
    nid = await _seed_newsletter(session_factory)
    agent = VisualGenerationAgent(session_factory, storage=storage)
    await agent.generate_all_visuals(nid)
    async with session_factory() as s:
        visual = (await s.execute(select(GeneratedVisual))).scalars().first()
        meta = agent.create_visual_metadata(visual)
    for key in ("id", "visual_kind", "file_path", "preview_url", "width", "height", "version", "status"):
        assert key in meta


# --- versioning --- #
async def test_visual_versioning(session_factory, storage) -> None:
    nid = await _seed_newsletter(session_factory)
    agent = VisualGenerationAgent(session_factory, storage=storage)
    result = await agent.generate_all_visuals(nid)
    visual_id = result["visual_ids"][0]

    out = await agent.version_visual(visual_id, reason="refresh")
    assert out["version"] == 2
    assert os.path.exists(out["file_path"])

    async with session_factory() as s:
        versions = await s.scalar(select(func.count()).select_from(VisualVersion))
        visual = await s.get(GeneratedVisual, uuid.UUID(visual_id))
    assert versions == 1
    assert visual.version == 2
    assert visual.status == "regenerated"


async def test_version_missing_visual_raises(session_factory, storage) -> None:
    agent = VisualGenerationAgent(session_factory, storage=storage)
    with pytest.raises(VisualNotFoundError):
        await agent.version_visual(str(uuid.uuid4()))


@pytest.mark.parametrize(
    "kind",
    [
        VisualKind.COVER,
        VisualKind.CAROUSEL_SLIDE,
        VisualKind.SUMMARY_CARD,
        VisualKind.TOOL_CARD,
        VisualKind.RESEARCH_CARD,
        VisualKind.BENCHMARK_CARD,
        VisualKind.TAKEAWAY_CARD,
    ],
)
async def test_regenerate_each_visual_kind(session_factory, storage, kind) -> None:
    nid = await _seed_newsletter(session_factory)
    agent = VisualGenerationAgent(session_factory, storage=storage)
    await agent.generate_all_visuals(nid)
    async with session_factory() as s:
        visual = await s.scalar(select(GeneratedVisual).where(GeneratedVisual.visual_kind == kind.value))
    out = await agent.version_visual(str(visual.id), reason="refresh")
    assert out["version"] == 2
    assert os.path.exists(out["file_path"])


# --- asset storage --- #
def test_asset_storage(tmp_path) -> None:
    store = LocalAssetStorage(str(tmp_path))
    path = store.save_bytes("visuals/newsletters/x/cover/cover.png", b"abc")
    assert store.exists(path)
    assert store.url_for(path).endswith("cover/cover.png")
    jpath = store.write_json("visuals/newsletters/x/metadata.json", {"a": 1})
    assert os.path.exists(jpath)


# --- workflow integration --- #
async def test_workflow_integration(workflow_service, session_factory, monkeypatch) -> None:
    from app.agents.source_collection import rss_collector

    RSS = b"""<?xml version='1.0'?><rss version='2.0'><channel>
    <item><title>Agentic AI orchestration framework launches</title>
    <link>https://openai.com/a1</link>
    <description>Agents orchestration guardrails evaluation launch.</description></item>
    </channel></rss>"""

    async def fake_fetch(url, **kw):
        return RSS

    monkeypatch.setattr(rss_collector, "fetch_bytes", fake_fetch)
    from app.models.content_source import ContentSource
    from app.models.enums import CollectionMethod, SourceType

    async with session_factory() as s:
        s.add(
            ContentSource(
                source_name="OpenAI",
                source_type=SourceType.RSS,
                source_url="https://openai.com",
                rss_url="https://openai.com/feed",
                priority=1,
                credibility_score=0.95,
                freshness_score=0.9,
                relevance_score=0.9,
                preferred_collection_method=CollectionMethod.RSS,
                fallback_collection_method=CollectionMethod.WEB,
                category="AI",
            )
        )
        await s.commit()

    result = await workflow_service.start_newsletter_workflow()
    state = result["state"]
    assert state["current_step"] == "human_review_node"
    assert state.get("visual_ids")  # visuals generated by the node

    async with session_factory() as s:
        count = await s.scalar(select(func.count()).select_from(GeneratedVisual))
    assert count >= 11  # cover + 10 carousel slides at minimum
