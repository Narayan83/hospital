import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

ALLOWED_PHOTO = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_CERT = {".pdf", ".jpg", ".jpeg", ".png"}


def _storage_root() -> Path:
    root = get_settings().doctors_storage_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


async def save_doctor_file(doctor_id: str, upload: UploadFile, *, kind: str) -> str:
    if not upload.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

    suffix = Path(upload.filename).suffix.lower()
    allowed = ALLOWED_PHOTO if kind == "photo" else ALLOWED_CERT
    if suffix not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(allowed))}",
        )

    folder = _storage_root() / doctor_id
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{kind}_{uuid.uuid4().hex}{suffix}"
    target = folder / filename

    content = await upload.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if kind == "photo" and len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Photo must be under 5 MB")
    if kind == "certificate" and len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Certificate must be under 10 MB")

    target.write_bytes(content)
    backend_root = _storage_root().parent.parent
    return str(target.relative_to(backend_root)).replace("\\", "/")


def resolve_doctor_file(path: str | None) -> Path | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        # stored relative to backend folder
        file_path = Path(".") / path
    return file_path if file_path.is_file() else None
