"""Create the hms database if it does not exist."""
import asyncio
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

_BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.hms_env import read_env_value  # noqa: E402


def _load_database_url() -> str:
    url = read_env_value("DATABASE_URL")
    if url:
        return url
    return "postgresql://postgres:postpass@127.0.0.1:5432/hms"


async def main() -> None:
    raw_url = _load_database_url()
    parsed = urlparse(raw_url.replace("postgresql+asyncpg://", "postgresql://"))
    host = parsed.hostname or "127.0.0.1"
    if host == "localhost":
        host = "127.0.0.1"
    port = parsed.port or 5432
    user = parsed.username or "postgres"
    password = parsed.password or ""
    db_name = (parsed.path or "/hms").lstrip("/") or "hms"

    try:
        conn = await asyncpg.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database="postgres",
            ssl=False,
        )
    except Exception as exc:
        print(f"Cannot connect to PostgreSQL at {host}:{port}")
        print(f"Error: {exc}")
        print("")
        print("Fix:")
        print("  1. Start PostgreSQL (services.msc -> postgresql -> Start)")
        print("  2. Check DATABASE_URL in config\\hms.env (or backend/.env for dev)")
        print("  3. Use host 127.0.0.1 instead of localhost")
        sys.exit(1)

    try:
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            db_name,
        )
        if exists:
            print(f"Database '{db_name}' already exists.")
        else:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"Database '{db_name}' created successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
