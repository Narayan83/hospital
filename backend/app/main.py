import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.update_routes import router as update_router
from app.api.v1.router import api_router
from app.config import get_settings
from app.core.database import AsyncSessionLocal, engine
from app.migrate import run_migrations
from app.seeds.bootstrap import seed_initial_data

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.reports_output_dir.mkdir(parents=True, exist_ok=True)
    settings.doctors_storage_dir.mkdir(parents=True, exist_ok=True)
    settings.patients_storage_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_migrations()
        if settings.seed_on_startup:
            async with AsyncSessionLocal() as session:
                await seed_initial_data(session)
                await session.commit()
            logger.info("Database connected and seed data ready.")
        else:
            logger.info("Startup seed skipped (SEED_ON_STARTUP=false).")
    except Exception as exc:
        logger.error(
            "Database startup failed: %s. "
            "Start PostgreSQL, run: python ..\\scripts\\create_hms_db.py && alembic upgrade head",
            exc,
        )
        raise
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    # Unauthenticated and outside the API prefix: client launchers hit this before login.
    app.include_router(update_router)

    @app.get("/health", tags=["health"])
    async def health_check():
        return {"status": "ok", "service": "hms-backend"}

    return app


app = create_app()
