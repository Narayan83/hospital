import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

ALLOWED_AADHAR = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


def _storage_root() -> Path:
    root = get_settings().patients_storage_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


async def save_patient_aadhar_scan(patient_id: str, upload: UploadFile) -> str:
    if not upload.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

    suffix = Path(upload.filename).suffix.lower()
    if suffix not in ALLOWED_AADHAR:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_AADHAR))}",
        )

    folder = _storage_root() / patient_id
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"aadhar_{uuid.uuid4().hex}{suffix}"
    target = folder / filename

    content = await upload.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aadhar scan must be under 10 MB",
        )

    target.write_bytes(content)
    backend_root = _storage_root().parent.parent
    return str(target.relative_to(backend_root)).replace("\\", "/")


def resolve_patient_file(path: str | None) -> Path | None:
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        file_path = Path(".") / path
    return file_path if file_path.is_file() else None
