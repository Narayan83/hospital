"""Production entry point for PyInstaller / customer install."""
import asyncio
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _ensure_install_env() -> None:
    if getattr(sys, "frozen", False) and "HMS_ROOT" not in os.environ:
        exe_dir = Path(sys.executable).resolve().parent
        # onedir: D:\HMS\backend\HMS Backend.exe  ->  HMS_ROOT = D:\HMS
        if (exe_dir.parent / "config" / "hms.env").is_file():
            root = exe_dir.parent
        elif (exe_dir / "config" / "hms.env").is_file():
            root = exe_dir
        else:
            root = exe_dir.parent if exe_dir.name.lower() == "backend" else exe_dir
        os.environ["HMS_ROOT"] = str(root)
        config = root / "config" / "hms.env"
        if config.is_file():
            os.environ.setdefault("HMS_CONFIG_FILE", str(config))


_ensure_install_env()


def run_setup_only() -> int:
    """Migrate DB and seed new menus/options (called after update zip on server)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from app.config import get_settings
    from app.core.database import AsyncSessionLocal, engine
    from app.migrate import run_migrations
    from app.seeds.bootstrap import seed_initial_data

    settings = get_settings()

    async def _run() -> None:
        settings.reports_output_dir.mkdir(parents=True, exist_ok=True)
        settings.doctors_storage_dir.mkdir(parents=True, exist_ok=True)
        settings.patients_storage_dir.mkdir(parents=True, exist_ok=True)
        run_migrations()
        if settings.seed_on_startup:
            async with AsyncSessionLocal() as session:
                await seed_initial_data(session)
                await session.commit()
            logger.info("Database updated and menus synced.")
        else:
            logger.info("Migrations complete (seed skipped).")
        await engine.dispose()

    try:
        asyncio.run(_run())
        return 0
    except Exception as exc:
        logger.error("Setup failed: %s", exc)
        return 1


def main() -> int:
    # Dedicated migration worker — exit without starting uvicorn.
    # Frozen Windows must not use multiprocessing.Process (spawn restarts this exe).
    if "--alembic-upgrade" in sys.argv:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        try:
            from app.migrate import upgrade_head

            upgrade_head()
            return 0
        except Exception as exc:
            logger.error("Alembic upgrade failed: %s", exc)
            return 1

    if "--setup-only" in sys.argv:
        return run_setup_only()

    import uvicorn  # noqa: E402

    from app.config import get_settings  # noqa: E402
    from app.main import app  # noqa: E402

    settings = get_settings()
    host = settings.backend_host
    if host in ("localhost", "127.0.0.1") and os.environ.get("HMS_LISTEN_ALL", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        host = "0.0.0.0"
    uvicorn.run(
        app,
        host=host,
        port=settings.backend_port,
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
