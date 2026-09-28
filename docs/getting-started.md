# Getting Started — Run the Desktop App (Windows)

This guide runs the **PySide6 desktop UI** on your PC. The desktop talks to the **backend API**, which uses **PostgreSQL** installed directly on Windows (no Docker).

## What you will see

- Sidebar with all HMS modules
- **Dashboard** welcome screen
- **Patient Registration** — search, list, and register patients (when backend is running)

---

## Step 1 — PostgreSQL database (one-time)

HMS uses your **existing PostgreSQL server** with a **separate database** named `hms` (not `tracknova` or other project DBs).

Create the database (psql or pgAdmin):

```sql
CREATE DATABASE hms;
```

Or:

```powershell
psql -U postgres -f scripts\setup_database.sql
```

Credentials are in `backend\.env` (same pattern as your other projects):

```
DATABASE_URL=postgresql://postgres:postpass@localhost:5432/hms
BACKEND_HOST=localhost
BACKEND_PORT=8010
BASE_URL=http://127.0.0.1:8010
```

---

## Step 2 — Install Python dependencies (one-time)

Open **PowerShell** in the project folder (`d:\fullstack\others\hospital`).

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

`backend\.env` is already set for `postgres:postpass@localhost:5432/hms`. Edit if your password differs.

### Run database migrations (one-time, or after schema changes)

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head
```

### Desktop

```powershell
cd desktop
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## Development vs EXE (important)

**You do NOT need to build an EXE to test changes.**

| When | What to run |
|------|-------------|
| **Daily development** | `run_backend.ps1` + `run_desktop.ps1` (Python directly) |
| **Customer install** | Build EXE once (PyInstaller) — only when shipping |

After code changes:
- **Backend** — auto-reloads if uvicorn was started with `--reload` (our script does this). Just save files.
- **Desktop** — close the HMS window, run `stop_desktop.ps1` or Task Manager, then `run_desktop.ps1` again.

---

## Stop running processes (when Ctrl+C does not work)

In a **new** PowerShell window:

```powershell
cd D:\fullstack\others\hospital

# Stop everything
.\scripts\stop_all.ps1

# Or separately
.\scripts\stop_backend.ps1
.\scripts\stop_desktop.ps1
```

Other options:
- Click inside the terminal, press **Ctrl+C** twice
- Close the terminal tab (trash icon on the terminal)
- **Task Manager** → end `python.exe` for uvicorn / HMS
- For desktop: close the HMS window, then run `stop_desktop.ps1`

---

## Step 3 — Start the backend (Terminal 1)

```powershell
cd d:\fullstack\others\hospital
.\scripts\run_backend.ps1
```

Leave this window open. You should see:

```
Uvicorn running on http://127.0.0.1:8010
```

Check in browser: http://127.0.0.1:8010/health → `{"status":"ok",...}`

---

## Login (desktop)

Default super admin (auto-created on backend startup):

| Field | Value |
|-------|-------|
| Email | `admin@admin.com` |
| Password | `admin123` |

Menus in the sidebar are filtered by the user's role.

---

## Step 4 — Start the desktop app (Terminal 2)

Open a **new** PowerShell window:

```powershell
cd d:\fullstack\others\hospital
.\scripts\run_desktop.ps1
```

The HMS window opens.

- Status bar should say **Backend connected (ok)**
- Click **Patient Registration** in the sidebar
- Fill the form and click **Save Patient**

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Desktop says "Backend Unavailable" | Start Terminal 1 (`run_backend.ps1`) first |
| `connection refused` on port 5432 | Start PostgreSQL service in Windows Services |
| `password authentication failed` | Fix `DATABASE_URL` in `backend\.env` |
| `alembic` / table errors | Run `alembic upgrade head` in backend venv |
| UI opens but save fails | Backend must be running and DB migrated |

### Start PostgreSQL service (if stopped)

```powershell
Get-Service postgresql*
# Then in Services app (services.msc), start "postgresql-x64-16" (name may vary)
```

---

## UI-only preview (backend not required)

You can open the desktop window without the backend — it will show a warning, but you can still browse the layout:

```powershell
cd desktop
.\.venv\Scripts\Activate.ps1
python -m app.main
```

Patient save/list will not work until the backend and database are running.

---

## Project layout reminder

```
Desktop (PySide6)  →  HTTP  →  Backend (FastAPI)  →  PostgreSQL
```

The desktop never connects to the database directly.
