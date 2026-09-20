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
- `UUIDPrimaryKeyMixin` keys every table on a client-side `uuid.uuid4` UUID (`Uuid` → `UUID` on PostgreSQL).
- `TimestampMixin` (`app/db/mixins.py`) provides timezone-aware `created_at` / `updated_at` with database-side defaults (`func.now()`); `updated_at` auto-refreshes on every UPDATE.
- `DATABASE_URL` must point to a UTC-timed PostgreSQL for correct timestamps.

### users table

- Platform-wide account table (no `organization_id` — org scoping flows through `organization_members`, the Organization Foundation).
- Columns: `id` (UUID PK), `email` (unique, not null), `phone` (unique, nullable), `full_name`, `role`, `is_active`, `is_verified` (timestamps via the mixin).
- No password or auth columns — credentials live in Supabase Auth, never here.

### Role system

- `RoleEnum` (`app/models/enums.py`): `SUPER_ADMIN`, `PG_OWNER`, `MANAGER`, `STAFF`, `TENANT`.
- Stored as a native PostgreSQL ENUM (`user_role`), so the database enforces the allowed values; SQLite fallbacks to a VARCHAR column for tests.
- The `role` column is indexed for platform-wide role lookups.
- The `organization_members` table and `OrganizationRoleEnum` exist (Organization Foundation); role _grants_ and a permissions engine arrive with the auth milestone.

### Repository layer

- `UserRepository` (`app/repositories/user.py`) is the typed data-access contract for users: `get_by_id`, `get_by_email`, `exists_by_email`, `create`. It takes a `Session` and stays free of business logic.

### Organization Foundation

The tenant boundary sits between platform `users` and future Parking Groups. Database + models + repositories only — no routes or services yet.

- **organizations** — top-level business/customer account. `id` (UUID PK), `name`, `slug` (unique), `is_active`, mixin timestamps. The slug is lowercase, space-free, 3–100 chars.
- **organization_members** — join table connecting a user to one organization: `organization_id` / `user_id` FKs plus a `role` and mixin timestamps. `UNIQUE (organization_id, user_id)` blocks duplicate memberships.
- **Membership roles** — `OrganizationRoleEnum` (`app/models/enums.py`), stored as a native PostgreSQL ENUM `organization_role`: `OWNER`, `MANAGER`, `STAFF`. Independent from platform `RoleEnum`; resident roles arrive with the resident-profile milestone.
- **Repositories** — `OrganizationRepository` (`get_by_id`, `get_by_slug`, `exists_by_slug`, `create`) and `OrganizationMemberRepository` (`get_by_id`, `get_members_for_org`, `get_org_for_user`, `exists_membership`, `create`).
- **Schemas** — `Organization{Base,Create,Read}` and `OrganizationMember{Base,Create,Read}` (`app/schemas/`), strict with `extra="forbid"`.
- **Models** — `Organization` / `OrganizationMember` (`app/models/`) with bidirectional `members` ↔ `organization` / `user` relationships.

### Migrations (Alembic)

Alembic reads `DATABASE_URL` from settings and targets `Base.metadata` (importing `app.models`), so `autogenerate` reflects real schema drift. Schema changes always ship with a migration. The first migration (`create users table and role enum`) ships in `alembic/versions/`.

```bash
# Apply migrations (against a reachable DATABASE_URL)
uv run alembic upgrade head

# Generate a migration from model changes
uv run alembic revision --autogenerate -m "describe the change"

# Inspect current state
uv run alembic current
uv run alembic history
```

Local development without a Postgres server: point `DATABASE_URL` at a SQLite file (`sqlite+pysqlite:///./dev.db`) to apply migrations and exercise the schema locally.

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
├── models/     SQLAlchemy models (users, organizations, memberships, enums)
├── repositories/  data access (users, organizations, memberships)
├── schemas/    Pydantic request/response models (users, organizations, memberships)
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
