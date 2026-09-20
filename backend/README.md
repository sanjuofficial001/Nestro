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
| `DATABASE_URL`  | `postgresql+psycopg://postgres:postgres@localhost:5432/nestro` | Placeholder; set a real URL to connect to a database                            |
| `JWT_SECRET`    | `change-me`                                                    | Placeholder; replace before any auth work                                       |

All six are optional to boot (dev defaults) but must be set per environment in production. Values load from `.env` via `Settings` (`pydantic-settings`), accessed through the cached `get_settings()`.

The application must reach its database at startup.

- **development** — unreachable database logs a warning and the app continues (local iteration without a running Postgres).
- **staging / production** — unreachable database raises and startup aborts: the app refuses to boot without its data layer.

## Run

```bash
uv run uvicorn app.main:app --reload
```

- API docs: http://localhost:8000/docs (Swagger) and /redoc
- Health: `GET /health` and `GET /api/v1/health` → `{"status": "healthy", "environment": "development"}`

On startup the lifespan hook logs the database URL (password masked), checks the connection, then continues or aborts per the environment policy above.

## Database

Access is layered: `api/` → `services/` → `repositories/` → `db/`. The backend is the only client of the database — no app touches it directly.

### Engine

- `app/db/session.py` exposes `create_engine_instance(url)` and the lazily-initialized `get_engine()` (global singleton). Engine **creation never connects**; the first query does.
- Safe FastAPI defaults: `pool_pre_ping=True` (stale connections are discarded), `pool_recycle=1800` (30 min), `pool_size=5`, `max_overflow=10`.
- PostgreSQL URLs get a 5-second `connect_timeout` so boot failures surface fast; SQLite gets `check_same_thread=False`.

### Sessions

- `SessionLocal` is a `sessionmaker` bound to the engine: `autoflush=False`, `autocommit=False`, `expire_on_commit=False`.
- `get_db()` yields a session and always closes it — wired into routes as a FastAPI dependency when the first data feature arrives.

### Models & conventions

- All models inherit from `Base` (`app/db/base.py`), which applies a fixed naming convention to generated constraints: `ix_`, `uq_`, `ck_`, `fk_`, `pk_` — so migrations are deterministic across databases.
- `TimestampMixin` (`app/db/mixins.py`) provides timezone-aware `created_at` / `updated_at` with database-side defaults (`func.now()`); `updated_at` auto-refreshes on every UPDATE.
- `DATABASE_URL` must point to a UTC-timed PostgreSQL for correct timestamps.

### Migrations (Alembic)

Alembic reads `DATABASE_URL` from settings and targets `Base.metadata`, so `autogenerate` reflects real schema drift. Schema changes always ship with a migration.

```bash
# Generate a migration from model changes (against a reachable DATABASE_URL)
uv run alembic revision --autogenerate -m "describe the change"
uv run alembic upgrade head

# Inspect current state
uv run alembic current
uv run alembic history
```

Local development without a Postgres server: no migration is generated until a real URL is configured.

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
├── db/         declarative Base (naming conventions), engine/session, mixins, health
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
