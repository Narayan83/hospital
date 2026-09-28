"""Resolve HMS install paths and external config (customer deployment)."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_hms_root() -> Path | None:
    explicit = os.environ.get("HMS_ROOT", "").strip()
    if explicit:
        return Path(explicit)

    # PyInstaller: exe directory
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return None


def resolve_config_file() -> Path | None:
    explicit = os.environ.get("HMS_CONFIG_FILE", "").strip()
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path

    root = resolve_hms_root()
    if root is not None:
        candidate = root / "config" / "hms.env"
        if candidate.is_file():
            return candidate

    return None


def resolve_env_files() -> tuple[str, ...]:
    """Env files in load order (later overrides earlier in pydantic)."""
    files: list[str] = []

    config = resolve_config_file()
    if config is not None:
        files.append(str(config))

    dev_env = Path(".env")
    if dev_env.is_file():
        files.append(str(dev_env))

    return tuple(files)


def resolve_storage_root() -> Path:
    root = resolve_hms_root()
    if root is not None:
        return root / "data" / "storage"
    return Path("./storage")


def read_env_value(key: str, default: str | None = None) -> str | None:
    config = resolve_config_file()
    if config is not None:
        for line in config.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()

    dev_env = Path(".env")
    if dev_env.is_file():
        for line in dev_env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()

    return default
