"""Run Alembic migrations (customer install)."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _alembic_ini() -> Path | None:
    root = os.environ.get("HMS_ROOT", "").strip()
    if root:
        candidate = Path(root) / "alembic.ini"
        if candidate.is_file():
            return candidate

    if getattr(sys, "frozen", False):
        # onedir: exe is .../backend/HMS Backend.exe ; alembic.ini is next to it or at HMS_ROOT
        exe_dir = Path(sys.executable).resolve().parent
        for candidate in (exe_dir / "alembic.ini", exe_dir.parent / "alembic.ini"):
            if candidate.is_file():
                return candidate

    cwd = Path("alembic.ini")
    if cwd.is_file():
        return cwd

    return None


def upgrade_head() -> None:
    """Apply pending migrations in *this* process (used by --alembic-upgrade)."""
    from alembic import command
    from alembic.config import Config

    ini = _alembic_ini()
    if ini is None:
        logger.warning("alembic.ini not found — skipping migrations")
        return

    # Ensure alembic finds script_location relative to ini / HMS_ROOT
    root = os.environ.get("HMS_ROOT", "").strip()
    if root:
        os.chdir(root)
    elif ini.parent.is_dir():
        os.chdir(ini.parent)

    logger.info("Running alembic upgrade head (%s)", ini)
    command.upgrade(Config(str(ini)), "head")
    logger.info("Alembic upgrade complete.")


def run_migrations() -> None:
    """Apply any pending DB migrations. Safe to call every startup.

    Must NOT use multiprocessing.Process on frozen Windows builds: spawn re-runs
    HMS Backend.exe as a full server, which creates dozens of stuck processes and
    deadlocks Alembic. Always use a dedicated --alembic-upgrade subprocess.
    """
    ini = _alembic_ini()
    if ini is None:
        return

    logger.info("Checking database migrations...")

    env = os.environ.copy()
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--alembic-upgrade"]
        cwd = env.get("HMS_ROOT") or str(Path(sys.executable).resolve().parent.parent)
    else:
        # Dev: same interpreter, isolated process (avoids asyncio lifespan deadlock)
        cmd = [
            sys.executable,
            "-c",
            "from app.migrate import upgrade_head; upgrade_head()",
        ]
        cwd = str(Path(__file__).resolve().parents[1])  # backend/

    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            timeout=120,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "Alembic upgrade timed out after 120s. "
            "Close all HMS Backend.exe processes in Task Manager, "
            "confirm PostgreSQL is running, then Start HMS again."
        ) from exc

    if completed.returncode != 0:
        raise RuntimeError(f"Alembic upgrade failed (exit {completed.returncode})")
    logger.info("Database migrations up to date.")
