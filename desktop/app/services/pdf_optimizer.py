from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from PIL import Image

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
MAX_EDGE_PX = 3500
JPEG_QUALITY = 92


def _open_image(path: Path) -> Image.Image:
    image = Image.open(path)
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    elif image.mode != "RGB":
        image = image.convert("RGB")
    return image


def _maybe_resize(image: Image.Image) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= MAX_EDGE_PX:
        return image
    scale = MAX_EDGE_PX / float(longest)
    new_size = (int(width * scale), int(height * scale))
    return image.resize(new_size, Image.Resampling.LANCZOS)


def images_to_pdf(image_paths: list[Path]) -> tuple[Path, int]:
    if not image_paths:
        raise ValueError("No images to convert")

    images: list[Image.Image] = []
    for path in image_paths:
        if path.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        img = _maybe_resize(_open_image(path))
        images.append(img)

    if not images:
        raise ValueError("No supported image files found")

    output = Path(tempfile.gettempdir()) / f"hms_doc_{uuid.uuid4().hex}.pdf"
    first, *rest = images
    save_kwargs = {
        "save_all": bool(rest),
        "append_images": rest,
        "resolution": 200.0,
        "quality": JPEG_QUALITY,
        "optimize": True,
    }
    first.save(output, "PDF", **save_kwargs)
    for image in images:
        image.close()

    page_count = len(images)
    file_size = output.stat().st_size
    return output, page_count if page_count else 1


def pdf_page_count(path: Path) -> int:
    suffix = path.suffix.lower()
    if suffix != ".pdf":
        return 1
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(path)).pages)
    except Exception:
        return 1


def normalize_to_pdf(path: Path) -> tuple[Path, int]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return path, pdf_page_count(path)
    if suffix in IMAGE_SUFFIXES:
        pdf_path, pages = images_to_pdf([path])
        return pdf_path, pages
    raise ValueError(f"Unsupported file type: {suffix}")
