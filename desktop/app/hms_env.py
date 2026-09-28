"""Load API settings from install config (customer deployment)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _resolve_hms_root() -> Path | None:
    explicit = os.environ.get("HMS_ROOT", "").strip()
    if explicit:
        return Path(explicit)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return None


def _resolve_config_file() -> Path | None:
    explicit = os.environ.get("HMS_CONFIG_FILE", "").strip()
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
    root = _resolve_hms_root()
    if root is not None:
        candidate = root / "config" / "hms.env"
        if candidate.is_file():
            return candidate
    return None


def _read_config_values() -> dict[str, str]:
    config = _resolve_config_file()
    if config is None:
        return {}
    values: dict[str, str] = {}
    for line in config.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def resolve_config_summary() -> dict[str, str]:
    """Values useful for desktop.log when diagnosing client connection issues."""
    from app.config import get_config

    config_file = _resolve_config_file()
    cfg = get_config()
    return {
        "config_file": str(config_file) if config_file else "(not found)",
        "api_url": cfg.api_url,
        "api_base": cfg.api_base,
        "base_url_env": os.environ.get("BASE_URL", ""),
        "update_path": os.environ.get("UPDATE_PATH", ""),
    }


def apply_install_config() -> None:
    """Set API env vars from config/hms.env before connecting to backend."""
    file_values = _read_config_values()
    for key in (
        "BASE_URL",
        "HMS_API_URL",
        "BACKEND_HOST",
        "BACKEND_PORT",
        "HMS_API_PREFIX",
        "UPDATE_PATH",
    ):
        if key in file_values and key not in os.environ:
            os.environ[key] = file_values[key]

    root = _resolve_hms_root()
    if root is not None and "HMS_ROOT" not in os.environ:
        os.environ["HMS_ROOT"] = str(root)

    # Ensure per-PC print.ini exists early (system-level printer mapping).
    try:
        from app.services.print_local_config import ensure_print_ini

        ensure_print_ini()
    except Exception:
        pass
