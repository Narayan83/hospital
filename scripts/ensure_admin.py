#!/usr/bin/env python3
"""Ensure Super Admin exists (admin@admin.com / admin123)."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import app.models  # noqa: F401

from app.core.database import AsyncSessionLocal
from app.seeds.bootstrap import seed_initial_data


async def main() -> None:
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)
        await session.commit()
    print("Admin ready: admin@admin.com / admin123")


if __name__ == "__main__":
    asyncio.run(main())
