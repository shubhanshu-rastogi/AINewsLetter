"""Visual versioning helpers."""

from __future__ import annotations

from app.models.generated_visual import GeneratedVisual
from app.models.visual_version import VisualVersion


def record_version(visual: GeneratedVisual, *, reason: str | None) -> VisualVersion:
    """Create a VisualVersion snapshot capturing the visual's current state."""
    return VisualVersion(
        visual_id=visual.id,
        version_number=visual.version,
        file_path=visual.file_path,
        prompt_used=visual.prompt_used,
        change_reason=reason,
    )
