"""CLI to run workflow recovery (after a restart or incident).

Usage:
    python -m scripts.recover
"""

from __future__ import annotations

import asyncio
import json

from app.db.session import AsyncSessionLocal
from app.services.workflow_recovery import WorkflowRecoveryService


async def _run() -> dict:
    service = WorkflowRecoveryService(AsyncSessionLocal)
    service.ensure_scheduler()
    return await service.recover_all()


def main() -> None:
    summary = asyncio.run(_run())
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
