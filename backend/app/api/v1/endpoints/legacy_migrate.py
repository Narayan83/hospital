"""Legacy MySQL → PostgreSQL database migration endpoints."""

from __future__ import annotations

import asyncio
import contextlib
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.api.v1.endpoints.admin import CLEAR_DB_PASSWORD, require_admin
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.services import legacy_migration as mig

router = APIRouter()


class MappingOverride(BaseModel):
    key: str
    legacy_table: str | None = None
    source_filter: str | None = None
    selected: bool | None = None


class MysqlTestRequest(BaseModel):
    mysql_connection_string: str = Field(default=mig.DEFAULT_MYSQL_ODBC)


class PostgresTestRequest(BaseModel):
    postgres_connection_string: str


class PreviewRequest(BaseModel):
    mysql_connection_string: str = Field(default=mig.DEFAULT_MYSQL_ODBC)
    mappings: list[MappingOverride] = Field(default_factory=list)


class RunMigrationRequest(BaseModel):
    password: str = Field(..., description="Maintenance password")
    mysql_connection_string: str = Field(default=mig.DEFAULT_MYSQL_ODBC)
    postgres_connection_string: str | None = Field(
        default=None,
        description="Defaults to the application's DATABASE_URL when empty.",
    )
    selected_keys: list[str] = Field(default_factory=list)
    mappings: list[MappingOverride] = Field(default_factory=list)
    replace_existing: bool = False
    dry_run: bool = False


@router.get("/legacy-migrate/defaults")
async def legacy_migrate_defaults(_: User = Depends(require_admin)) -> dict:
    return {
        "mysql_connection_string": mig.DEFAULT_MYSQL_ODBC,
        "postgres_connection_string": mig.display_postgres_url(),
        "mappings": mig.DEFAULT_MAPPINGS,
        "migrate_order": mig.MIGRATE_ORDER,
        "maintenance_password_hint": "Same password as Reset Database",
    }


@router.post("/legacy-migrate/test-mysql")
async def legacy_migrate_test_mysql(
    payload: MysqlTestRequest,
    _: User = Depends(require_admin),
) -> dict:
    try:
        return mig.test_mysql_connection(payload.mysql_connection_string)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/legacy-migrate/test-postgres")
async def legacy_migrate_test_postgres(
    payload: PostgresTestRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> dict:
    try:
        info = mig.test_postgres_connection(payload.postgres_connection_string)
        # Quick live check against the app DB when URLs match; otherwise open a short connection.
        from sqlalchemy import text

        display_app = mig.display_postgres_url()
        if mig.display_postgres_url(payload.postgres_connection_string) == display_app:
            ver = await session.execute(text("SELECT version()"))
            version = ver.scalar()
            return {
                "ok": True,
                "message": f"Using application PostgreSQL. {version}",
                **info,
            }

        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(info["normalized_url"], echo=False)
        try:
            async with engine.connect() as conn:
                ver = await conn.execute(text("SELECT version()"))
                version = ver.scalar()
        finally:
            await engine.dispose()
        return {"ok": True, "message": f"Connected. {version}", **info}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/legacy-migrate/preview")
async def legacy_migrate_preview(
    payload: PreviewRequest,
    _: User = Depends(require_admin),
) -> dict:
    catalog = {m["key"]: dict(m) for m in mig.DEFAULT_MAPPINGS}
    for ov in payload.mappings:
        if ov.key not in catalog:
            continue
        if ov.legacy_table:
            catalog[ov.key]["legacy_table"] = ov.legacy_table.strip()
        if ov.source_filter is not None:
            catalog[ov.key]["source_filter"] = ov.source_filter.strip()
    mappings = list(catalog.values())
    try:
        counts = mig.preview_legacy_counts(payload.mysql_connection_string, mappings)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return {"counts": counts}


@router.post("/legacy-migrate/run")
async def legacy_migrate_run(
    payload: RunMigrationRequest,
    session: AsyncSession = Depends(get_session),
    _: User = Depends(require_admin),
) -> dict:
    if payload.password != CLEAR_DB_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect maintenance password.",
        )
    if not payload.selected_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least one table to migrate.",
        )
    try:
        return await mig.run_migration(
            mysql_conn_str=payload.mysql_connection_string,
            postgres_url=payload.postgres_connection_string,
            selected_keys=payload.selected_keys,
            mapping_overrides=[m.model_dump() for m in payload.mappings],
            replace_existing=payload.replace_existing,
            dry_run=payload.dry_run,
            app_session=session,
        )
    except Exception as exc:  # noqa: BLE001
        detail = str(getattr(exc, "orig", exc) or exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        ) from exc


@router.post("/legacy-migrate/run-stream")
async def legacy_migrate_run_stream(
    payload: RunMigrationRequest,
    _: User = Depends(require_admin),
) -> StreamingResponse:
    """Stream newline-delimited JSON progress while a migration runs."""
    if payload.password != CLEAR_DB_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Incorrect maintenance password.",
        )
    if not payload.selected_keys:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least one table to migrate.",
        )

    queue: asyncio.Queue = asyncio.Queue()

    async def progress(event: dict) -> None:
        await queue.put(event)

    async def runner() -> None:
        async with AsyncSessionLocal() as session:
            try:
                result = await mig.run_migration(
                    mysql_conn_str=payload.mysql_connection_string,
                    postgres_url=payload.postgres_connection_string,
                    selected_keys=payload.selected_keys,
                    mapping_overrides=[m.model_dump() for m in payload.mappings],
                    replace_existing=payload.replace_existing,
                    dry_run=payload.dry_run,
                    app_session=session,
                    progress=progress,
                )
                await queue.put({"type": "complete", **result})
            except Exception as exc:  # noqa: BLE001
                detail = str(getattr(exc, "orig", exc) or exc)
                await queue.put({"type": "error", "message": detail})
            finally:
                await queue.put(None)

    async def generate():
        task = asyncio.create_task(runner())
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield json.dumps(event, default=str) + "\n"
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
