# Nestro Backend

FastAPI service — the single access point for all Nestro data. PostgreSQL (Supabase-compatible) is accessed only through this backend.

## Tech

- Python 3.12+, FastAPI, Pydantic v2 (strict), SQLAlchemy 2.x, Alembic, PostgreSQL
- Package manager: `uv`; ruff for lint, pytest for tests
- Layers: `api/` (routes) → `services/` (business logic) → `repositories/` (data access) → `db/` (persistence). Routes never contain business logic or DB access.

## Setup

```bash
cd backend
uv venv .venv --python 3.12
uv pip install -r requirements.txt
```

Copy `.env.example` to `.env` and set real values when required:

```bash
cp .env.example .env
```

### Environment variables

| Variable        | Default                                                        | Notes                                                                           |
| --------------- | -------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| `PROJECT_NAME`  | `Nestro`                                                       |                                                                                 |
| `API_V1_PREFIX` | `/api/v1`                                                      | Base path for versioned routes                                                  |
| `ENVIRONMENT`   | `development`                                                  | Must be `development`, `staging`, or `production` — anything else fails at boot |
| `DEBUG`         | `False`                                                        | Enables DEBUG-level logging                                                     |
| `DATABASE_URL`  | `postgresql+psycopg://postgres:postgres@localhost:5432/nestro` | Placeholder; set a real URL when the DB milestone lands                         |
| `JWT_SECRET`    | `change-me`                                                    | Placeholder; replace before any auth work                                       |

All six are optional to boot (dev defaults) but must be set per environment in production. Values load from `.env` via `Settings` (`pydantic-settings`), accessed through the cached `get_settings()`.

## Run

```bash
uv run uvicorn app.main:app --reload
```

- API docs: http://localhost:8000/docs (Swagger) and /redoc
- Health: `GET /health` and `GET /api/v1/health` → `{"status": "healthy", "environment": "development"}`

On startup the lifespan hook logs `Application starting`; on shutdown it logs `Application shutting down`.

## Verify

```bash
uv run ruff check .
uv run pytest
```

## Layout

```
app/
├── api/v1/     versioned HTTP routes (health)
├── core/       config (pydantic-settings), logging, lifespan, exceptions
├── db/         declarative Base — Alembic target for future models
├── models/     SQLAlchemy models (future)
├── repositories/  data access (future)
├── schemas/    Pydantic request/response models
├── services/   business logic (future)
└── main.py     create_application() factory, exposes `app`
alembic/        migration structure (schema change ships with a migration)
tests/          pytest suite
```

## Conventions

- All imports are absolute from the `app` package: `from app.core.config import settings`.
- Every request/response is validated by a Pydantic model.
- Config comes from environment variables only; no secrets in code or commits.
- The app is built by `create_application()`; routers, exception handlers, logging, and lifespan are registered there, keeping `main.py` small.
