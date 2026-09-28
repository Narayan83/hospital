"""Application and login performance logging.

Frozen installs write under the install folder (next to HMS Desktop.exe) and
also mirror to %LOCALAPPDATA%\\HospitalManagement\\logs so logs are always
findable even when the install folder is not writable.
"""

from __future__ import annotations

import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

_start: float | None = None
_last: float | None = None
_flow: str = "login_to_main"
_log_dirs: list[Path] | None = None
_primary_log_dir: Path | None = None


def install_root() -> Path:
    """Folder that contains HMS Desktop.exe (or desktop/ in dev)."""
    explicit = os.environ.get("HMS_ROOT", "").strip()
    if explicit:
        return Path(explicit)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _candidate_log_dirs() -> list[Path]:
    dirs = [install_root() / "logs"]
    local = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "HospitalManagement" / "logs"
    if local not in dirs:
        dirs.append(local)
    return dirs


def log_dirs() -> list[Path]:
    """All directories we write logs into (primary first)."""
    global _log_dirs, _primary_log_dir
    if _log_dirs is not None:
        return _log_dirs
    usable: list[Path] = []
    for directory in _candidate_log_dirs():
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            usable.append(directory)
        except OSError:
            continue
    if not usable:
        # Last resort: temp
        fallback = Path(os.environ.get("TEMP", ".")) / "HMS_logs"
        fallback.mkdir(parents=True, exist_ok=True)
        usable = [fallback]
    _log_dirs = usable
    _primary_log_dir = usable[0]
    return usable


def log_dir() -> Path:
    global _primary_log_dir
    if _primary_log_dir is None:
        log_dirs()
    assert _primary_log_dir is not None
    return _primary_log_dir


def desktop_log_path() -> Path:
    return log_dir() / "desktop.log"


def perf_log_path() -> Path:
    return log_dir() / "startup_perf.log"


def _append_all(filename: str, line: str) -> None:
    for directory in log_dirs():
        path = directory / filename
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
                handle.flush()
        except OSError:
            continue
    try:
        print(line, file=sys.stderr, flush=True)
    except OSError:
        pass


def log_info(message: str, **details: object) -> None:
    """Always-on desktop log (connection, config, crashes)."""
    extra = " | ".join(f"{key}={value}" for key, value in details.items())
    suffix = f" | {extra}" if extra else ""
    stamp = datetime.now().isoformat(timespec="seconds")
    _append_all("desktop.log", f"{stamp} | {message}{suffix}")


def log_exception(message: str, exc: BaseException | None = None) -> Path:
    """Write an error + traceback; return the primary log file path."""
    log_info(message, error=str(exc) if exc else "")
    if exc is not None:
        _append_all("desktop.log", traceback.format_exc())
    return desktop_log_path()


def init_app_log() -> Path:
    """Create logs folder(s) and write a startup banner. Call as early as possible."""
    dirs = log_dirs()
    primary = desktop_log_path()
    stamp = datetime.now().isoformat(timespec="seconds")
    banner = (
        f"=== HMS Desktop started {stamp} ===\n"
        f"install_root={install_root()}\n"
        f"executable={sys.executable}\n"
        f"frozen={getattr(sys, 'frozen', False)}\n"
        f"HMS_ROOT={os.environ.get('HMS_ROOT', '')}\n"
        f"HMS_CONFIG_FILE={os.environ.get('HMS_CONFIG_FILE', '')}\n"
        f"log_dirs={'; '.join(str(d) for d in dirs)}\n"
        f"primary_log={primary}\n"
    )
    for directory in dirs:
        try:
            marker = directory / "READ_ME_LOGS_ARE_HERE.txt"
            marker.write_text(
                "HMS Desktop logs are in this folder.\n"
                f"Primary: {primary}\n"
                "Files: desktop.log, startup_perf.log, desktop-launcher.log\n",
                encoding="utf-8",
            )
            with (directory / "desktop.log").open("a", encoding="utf-8") as handle:
                handle.write(banner)
                handle.flush()
        except OSError:
            continue
    print(f"[HMS] Logging to {primary}", file=sys.stderr, flush=True)
    # Pointer file next to the EXE so users always find logs.
    try:
        pointer = install_root() / "LOGS_ARE_HERE.txt"
        pointer.write_text(
            "HMS Desktop log folder(s):\n"
            + "\n".join(str(d) for d in dirs)
            + f"\n\nOpen: {primary}\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    return primary


def _write_perf(line: str, *, to_console: bool = False) -> None:
    _append_all("startup_perf.log", line)
    if to_console:
        print(f"[HMS-PERF] {line}", file=sys.stderr, flush=True)


def begin_flow(name: str = "login_to_main") -> None:
    global _start, _last, _flow
    _flow = name
    _start = time.perf_counter()
    _last = _start
    for directory in log_dirs():
        path = directory / "startup_perf.log"
        try:
            with path.open("w", encoding="utf-8") as handle:
                handle.write(
                    f"=== {name} started {datetime.now().isoformat(timespec='seconds')} ===\n"
                )
                handle.write(f"log file: {path}\n")
                handle.flush()
        except OSError:
            continue
    print(f"[HMS-PERF] Logging to {perf_log_path()}", file=sys.stderr, flush=True)
    log_info(f"flow start: {name}")


def step(label: str, **details: object) -> None:
    global _last
    if _start is None or _last is None:
        begin_flow()
    now = time.perf_counter()
    delta_ms = (now - _last) * 1000
    total_ms = (now - _start) * 1000
    _last = now
    extra = " | ".join(f"{key}={value}" for key, value in details.items())
    suffix = f" | {extra}" if extra else ""
    _write_perf(f"+{delta_ms:8.1f}ms | total {total_ms:8.1f}ms | {label}{suffix}")


def end_flow(label: str = "DONE — main window visible") -> None:
    step(label)
    if _start is not None:
        total_ms = (time.perf_counter() - _start) * 1000
        _write_perf(f"=== TOTAL {total_ms:.1f}ms ===\n")
        print(
            f"[HMS-PERF] Login complete in {total_ms:.0f}ms — see {perf_log_path()}",
            file=sys.stderr,
            flush=True,
        )
    log_info(f"flow end: {label}")
