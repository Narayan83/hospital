"""Serve the update package to client PCs over the API they already talk to.

Clients previously read the zip from \\SERVER\HMSUpdates, which only works if an
administrator created that SMB share by hand. These routes are unauthenticated on
purpose: the launcher runs the update check before anyone has logged in.
"""
from __future__ import annotations

import hashlib
import logging
import zipfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from app.hms_env import resolve_hms_root

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/update", tags=["update"])

UPDATE_FILE_NAMES = ("HMS-Update.zip", "update.zip")
VERSION_ENTRY = "config/VERSION"

# sha256 of a 20 MB zip is re-read on every client launch, so keep the last result.
_info_cache: dict[str, object] = {}


def find_update_zip() -> Path | None:
    root = resolve_hms_root()
    if root is None:
        return None
    folder = root / "updates"
    if not folder.is_dir():
        return None
    for name in UPDATE_FILE_NAMES:
        candidate = folder / name
        if candidate.is_file():
            return candidate
    return None


def read_zip_version(zip_path: Path) -> str | None:
    # build.ps1 writes entry names with backslashes, so normalise before matching.
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            if name.replace("\\", "/") == VERSION_ENTRY:
                return archive.read(name).decode("utf-8-sig").strip()
    return None


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


@router.get("/info")
async def update_info() -> JSONResponse:
    zip_path = find_update_zip()
    if zip_path is None:
        return JSONResponse({"available": False, "reason": "no update zip on server"})

    stat = zip_path.stat()
    cache_key = f"{zip_path}|{stat.st_mtime_ns}|{stat.st_size}"
    cached = _info_cache.get(cache_key)
    if cached is not None:
        return JSONResponse(cached)

    try:
        version = read_zip_version(zip_path)
    except (OSError, zipfile.BadZipFile) as exc:
        logger.warning("Update zip %s is unreadable: %s", zip_path, exc)
        return JSONResponse({"available": False, "reason": f"unreadable zip: {exc}"})

    if not version:
        return JSONResponse({"available": False, "reason": "zip has no config/VERSION"})

    payload = {
        "available": True,
        "version": version,
        "filename": zip_path.name,
        "size": stat.st_size,
        "sha256": file_sha256(zip_path),
    }
    _info_cache.clear()
    _info_cache[cache_key] = payload
    return JSONResponse(payload)


@router.get("/download")
async def update_download():
    zip_path = find_update_zip()
    if zip_path is None:
        return JSONResponse(
            {"detail": "No update package on the server."}, status_code=404
        )
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=zip_path.name,
    )
