"""Runtime configuration backed by the ``system_settings`` table.

Lets the operator UI manage configuration (API keys, models, feature flags)
without editing ``.env``. Values are persisted to the database — secrets
encrypted at rest — and applied to the live :data:`app.core.config.settings`
object so agents pick them up immediately.

Only an explicit allowlist of fields is editable. ``SECRET_KEY`` and
``REVIEW_AUTH_TOKEN`` are intentionally excluded (managed via environment) so the
UI can't lock itself out or break secret decryption.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.core.logging import get_logger
from app.models.system_setting import SystemSetting

logger = get_logger("runtime_config")

_KEY_PREFIX = "cfg."
_MASK = "__SET__"  # sentinel returned for secrets that have a stored value


@dataclass(frozen=True)
class Field:
    key: str
    label: str
    type: str  # string | secret | bool | number | select
    group: str
    help: str = ""
    options: tuple[str, ...] = ()


FIELDS: tuple[Field, ...] = (
    # ---- LLM provider ----
    Field("LLM_PROVIDER", "LLM provider", "select", "LLM", options=("anthropic", "openai")),
    Field("LLM_MODEL", "LLM model", "string", "LLM", help="e.g. claude-haiku-4-5-20251001"),
    Field("ANTHROPIC_API_KEY", "Anthropic API key", "secret", "LLM"),
    Field("OPENAI_API_KEY", "OpenAI API key", "secret", "LLM"),
    # ---- AI feature toggles ----
    Field("ENABLE_LLM_CLASSIFICATION", "Use LLM for classification", "bool", "AI features"),
    Field("ENABLE_LLM_FACTCHECK", "Use LLM for fact-checking", "bool", "AI features"),
    Field("ENABLE_LLM_WRITER", "Use LLM for writing", "bool", "AI features"),
    Field("ENABLE_LLM_FEEDBACK", "Use LLM for feedback", "bool", "AI features"),
    Field("ENABLE_AI_IMAGES", "Generate AI images", "bool", "AI features"),
    Field("AI_IMAGE_MODEL", "AI image model", "string", "AI features", help="e.g. gpt-image-1"),
    # ---- Brand ----
    Field("NEWSLETTER_NAME", "Newsletter name", "string", "Brand"),
    Field("NEWSLETTER_TAGLINE", "Tagline", "string", "Brand"),
    Field("MIN_CONFIDENCE_FOR_PUBLISH", "Min fact-check confidence", "number", "Brand"),
    # ---- Publishing ----
    Field("ENABLE_REAL_PUBLISHING", "Publish for real", "bool", "Publishing"),
    Field("BEEHIIV_API_KEY", "Beehiiv API key", "secret", "Publishing"),
    Field("BEEHIIV_PUBLICATION_ID", "Beehiiv publication ID", "string", "Publishing"),
    Field("LINKEDIN_CLIENT_ID", "LinkedIn client ID", "string", "Publishing"),
    Field("LINKEDIN_CLIENT_SECRET", "LinkedIn client secret", "secret", "Publishing"),
    Field("LINKEDIN_AUTHOR_URN", "LinkedIn author URN", "string", "Publishing"),
    # ---- Integrations ----
    Field("NOTION_API_KEY", "Notion API key", "secret", "Integrations"),
    Field("NOTION_REVIEW_DATABASE_ID", "Notion review DB ID", "string", "Integrations"),
)

_FIELD_BY_KEY = {f.key: f for f in FIELDS}


def _coerce(field: Field, raw: Any) -> Any:
    if field.type == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    if field.type == "number":
        try:
            return float(raw)
        except (TypeError, ValueError):
            return 0.0
    return "" if raw is None else str(raw)


def _apply_to_settings(field: Field, value: Any) -> None:
    setattr(settings, field.key, value)


async def load_into_settings(session: AsyncSession) -> int:
    """Load persisted config from the DB into the live settings object."""
    rows = (await session.execute(select(SystemSetting).where(SystemSetting.key.like(f"{_KEY_PREFIX}%")))).scalars()
    applied = 0
    for row in rows:
        key = row.key[len(_KEY_PREFIX) :]
        field = _FIELD_BY_KEY.get(key)
        if field is None or row.value is None:
            continue
        stored = decrypt(row.value) if field.type == "secret" else row.value
        try:
            _apply_to_settings(field, _coerce(field, stored))
            applied += 1
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("config_apply_failed", key=key, error=str(exc))
    if applied:
        logger.info("runtime_config_loaded", count=applied)
    return applied


def get_config() -> dict[str, Any]:
    """Return the field schema + current values (secrets masked, never exposed)."""
    values: dict[str, Any] = {}
    secret_set: dict[str, bool] = {}
    for field in FIELDS:
        current = getattr(settings, field.key, None)
        if field.type == "secret":
            secret_set[field.key] = bool(current)
            values[field.key] = _MASK if current else ""
        else:
            values[field.key] = current
    return {
        "fields": [
            {
                "key": f.key,
                "label": f.label,
                "type": f.type,
                "group": f.group,
                "help": f.help,
                "options": list(f.options),
            }
            for f in FIELDS
        ],
        "values": values,
        "secret_set": secret_set,
    }


async def update_config(session: AsyncSession, updates: dict[str, Any]) -> dict[str, Any]:
    """Persist + apply a partial config update. Unknown keys are ignored.

    For secrets, an empty/masked value leaves the existing secret untouched.
    """
    changed: list[str] = []
    for key, raw in updates.items():
        field = _FIELD_BY_KEY.get(key)
        if field is None:
            continue
        if field.type == "secret" and (raw in ("", None, _MASK)):
            continue  # don't overwrite an existing secret with a blank
        coerced = _coerce(field, raw)
        stored = encrypt(str(coerced)) if field.type == "secret" else str(coerced)

        db_key = f"{_KEY_PREFIX}{key}"
        existing = (
            await session.execute(select(SystemSetting).where(SystemSetting.key == db_key))
        ).scalar_one_or_none()
        if existing is None:
            session.add(SystemSetting(key=db_key, value=stored))
        else:
            existing.value = stored
        _apply_to_settings(field, coerced)
        changed.append(key)

    await session.commit()
    logger.info("runtime_config_updated", changed=changed)
    return {"changed": changed}
