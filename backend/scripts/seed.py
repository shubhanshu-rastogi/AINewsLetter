"""CLI entry point for seeding reference data.

Usage:
    python -m scripts.seed
"""

from __future__ import annotations

import asyncio

from app.db.seed import run_seed


def main() -> None:
    result = asyncio.run(run_seed())
    print("Seed complete:", result)


if __name__ == "__main__":
    main()
