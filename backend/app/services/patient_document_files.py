import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

ALLOWED_UPLOAD = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
MAX_BYTES = 50 * 1024 * 1024

# backend/app/services/this_file.py -> backend/
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _configured_storage_dir() -> Path:
    """Absolute patient-documents directory, independent of process CWD when possible."""
    configured = Path(get_settings().patient_documents_storage_dir)
    if configured.is_absolute():
        return configured.resolve()

    cwd_candidate = (Path.cwd() / configured).resolve()
    backend_candidate = (_BACKEND_ROOT / configured).resolve()
    if cwd_candidate.is_dir():
        return cwd_candidate
    if backend_candidate.is_dir():
        return backend_candidate
    return backend_candidate


def _storage_root(*, create: bool = True) -> Path:
    root = _configured_storage_dir()
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def _path_roots() -> list[Path]:
    """Directories that historical file_path values may be relative to."""
    storage = _storage_root(create=False)
    roots = [
        Path.cwd(),
        _BACKEND_ROOT,
        storage,
        storage.parent,  # .../storage
        storage.parent.parent,  # backend/ or .../data
    ]
    # Installed layout: HMS_ROOT when storage is <root>/data/storage/patient-documents
    if storage.parent.name.lower() == "storage" and storage.parent.parent.name.lower() == "data":
        roots.append(storage.parent.parent.parent)

    seen: set[str] = set()
    unique: list[Path] = []
    for root in roots:
        try:
            key = str(root.resolve())
        except OSError:
            key = str(root)
        if key in seen:
            continue
        seen.add(key)
        unique.append(root)
    return unique


def _relative_path(target: Path) -> str:
    """Store paths relative to the patient-documents storage root when possible."""
    target = target.resolve()
    storage = _storage_root(create=False)
    try:
        return str(target.relative_to(storage)).replace("\\", "/")
    except ValueError:
        pass
    # Fallback: previous convention (relative to storage's grandparent)
    try:
        return str(target.relative_to(storage.parent.parent)).replace("\\", "/")
    except ValueError:
        return str(target)


async def save_patient_document_pdf(patient_id: str, upload: UploadFile) -> tuple[str, int]:
    if not upload.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File name is required")

    suffix = Path(upload.filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Allowed: {', '.join(sorted(ALLOWED_UPLOAD))}",
        )

    folder = _storage_root(create=True) / patient_id
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"doc_{uuid.uuid4().hex}.pdf"
    target = folder / filename

    content = await upload.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document must be under 50 MB",
        )

    target.write_bytes(content)
    return _relative_path(target), len(content)


def resolve_patient_document_file(path: str | None) -> Path | None:
    """Resolve a stored patient-document path across install and dev layouts."""
    if not path:
        return None

    raw = str(path).strip().replace("\\", "/")
    if not raw:
        return None

    candidates: list[Path] = [Path(raw)]
    for root in _path_roots():
        candidates.append(root / raw)

    # Old rows used storage/patient-documents/... relative to different roots.
    marker = "patient-documents/"
    lower = raw.lower()
    if marker in lower:
        suffix = raw[lower.index(marker) + len(marker) :]
        if suffix:
            candidates.append(_storage_root(create=False) / suffix)

    parts = Path(raw).parts
    if parts:
        storage = _storage_root(create=False)
        candidates.append(storage / Path(*parts[-2:]) if len(parts) >= 2 else storage / parts[-1])

    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        if resolved.is_file():
            return resolved
    return None
