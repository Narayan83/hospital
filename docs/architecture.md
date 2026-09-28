# HMS Architecture

## Overview

```
┌─────────────────┐     HTTP/JSON      ┌──────────────────────────────┐
│  Desktop (Qt)   │ ─────────────────► │  Backend API (FastAPI)       │
│  PySide6        │                    │  ├── api/      (routes)      │
│  ui/            │                    │  ├── services/ (business)    │
│  controllers/   │                    │  ├── repositories/ (DB)      │
│  api_client/    │                    │  ├── models/   (SQLAlchemy)  │
└─────────────────┘                    │  └── reports/  (Jinja2+PDF)  │
                                       └──────────────┬───────────────┘
┌─────────────────┐                                  │
│  Web (future)   │ ─────────────────────────────────┘
└─────────────────┘                                  ▼
                                          ┌──────────────────┐
                                          │   PostgreSQL     │
                                          └──────────────────┘
```

## Layer Responsibilities

### Backend

| Folder | Role |
|--------|------|
| `app/api` | HTTP endpoints, validation, dependency injection |
| `app/services` | Business rules, orchestration, error handling |
| `app/repositories` | CRUD and queries only |
| `app/models` | SQLAlchemy table definitions |
| `app/schemas` | Pydantic request/response DTOs |
| `app/reports` | Jinja2 HTML templates + WeasyPrint PDF |
| `app/modules` | Future module-specific packages |

### Desktop

| Folder | Role |
|--------|------|
| `app/ui` | Widgets, layouts, user interaction |
| `app/controllers` | Call API, map results for UI |
| `app/api_client` | HTTP client to backend |

**Rule:** Desktop must never import SQLAlchemy or connect to PostgreSQL directly.

## Scalability (50–300 users)

- Async FastAPI with connection pooling (`pool_size=20`, `max_overflow=40`)
- Stateless API — horizontal scaling behind a load balancer
- PostgreSQL as single source of truth
- Desktop clients are thin — no local DB for transactional data

## Module Roadmap

1. Patient Registration ✓ (starter)
2. Doctor Management ✓ (starter)
3. OP Billing
4. IP Management
5. Pharmacy
6. Lab Reports
7. Inventory
8. Reports & Analytics

Each module follows: `models` → `repositories` → `services` → `api` → desktop `ui`.
