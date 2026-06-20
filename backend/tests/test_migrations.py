"""Migration up/down tests against a temporary SQLite database."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from alembic.config import Config

from alembic import command

BACKEND_DIR = Path(__file__).resolve().parents[1]

EXPECTED_TABLES = {
    "users",
    "content_sources",
    "collected_articles",
    "article_categories",
    "article_tags",
    "newsletters",
    "newsletter_sections",
    "generated_visuals",
    "review_sessions",
    "feedback_items",
    "publication_records",
    "agent_runs",
    "workflow_runs",
    "system_settings",
}


def _config(db_path: Path) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    os.environ["ALEMBIC_DATABASE_URL"] = f"sqlite:///{db_path}"
    return cfg


def _table_names(db_path: Path) -> set[str]:
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' AND name != 'alembic_version'"
        )
        return {r[0] for r in rows}
    finally:
        con.close()


def test_migration_upgrade_and_downgrade(tmp_path) -> None:
    db_path = tmp_path / "migration_test.db"
    cfg = _config(db_path)
    try:
        command.upgrade(cfg, "head")
        assert EXPECTED_TABLES <= _table_names(db_path)

        # Idempotent: re-running upgrade is a no-op.
        command.upgrade(cfg, "head")

        command.downgrade(cfg, "base")
        assert _table_names(db_path) == set()
    finally:
        os.environ.pop("ALEMBIC_DATABASE_URL", None)
