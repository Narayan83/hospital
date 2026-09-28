# Hospital Management System (HMS)

Modern hospital ERP replacing legacy VFP applications. Built for long-term maintainability, clean architecture, and 50–300 concurrent users.

## Architecture

```
hospital/
├── backend/     # FastAPI + SQLAlchemy + PostgreSQL
├── desktop/     # PySide6 desktop client (Windows EXE target)
├── web/         # Future web module (React / Bootstrap)
├── shared/      # Shared constants and types
├── scripts/     # Build and deployment scripts
└── docs/        # Project documentation
```

## Quick Start (Windows — desktop UI)

See **[docs/getting-started.md](docs/getting-started.md)** for full step-by-step instructions.

**Easiest — one command (backend + desktop):**

```powershell
cd D:\fullstack\others\hospital
.\scripts\dev.ps1
```

Or double-click **`RUN.bat`** in the project folder.

| Command | What it does |
|---------|----------------|
| `.\scripts\dev.ps1` | Setup, start backend (new window), open desktop |
| `.\scripts\run_backend.ps1` | Backend only (Terminal 1) |
| `.\scripts\run_desktop.ps1` | Desktop only (Terminal 2 — backend must be running) |
| `.\scripts\stop_all.ps1` | Stop backend + desktop |

From `desktop\` folder: `.\run.ps1` or `..\scripts\dev.ps1`

**Login:** `admin@admin.com` / `admin123`

**Stop:** close the HMS window, then `.\scripts\stop_all.ps1` if the backend window is still open.

**Note:** First start can take up to ~60 seconds while menus seed. The script waits automatically.

Before the first run, install **PostgreSQL** locally and create the database (one-time). Details in `docs/getting-started.md`.

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ (installed on Windows — not Docker)
- PySide6 (installed automatically with desktop requirements)

## License

Proprietary — internal hospital use.
