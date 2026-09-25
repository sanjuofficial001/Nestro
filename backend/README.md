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

| Variable               | Default                                                        | Notes                                                                               |
| ---------------------- | -------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `PROJECT_NAME`         | `Nestro`                                                       |                                                                                     |
| `API_V1_PREFIX`        | `/api/v1`                                                      | Base path for versioned routes                                                      |
| `ENVIRONMENT`          | `development`                                                  | Must be `development`, `staging`, or `production` — anything else fails at boot     |
| `DEBUG`                | `False`                                                        | Enables DEBUG-level logging                                                         |
| `DATABASE_URL`         | `postgresql+psycopg://postgres:postgres@localhost:5432/nestro` | Placeholder; set a real URL to connect to a database                                |
| `SUPABASE_URL`         | _(empty)_                                                      | Supabase project URL; enables JWKS-based access-token verification                  |
| `JWT_SECRET`           | `change-me`                                                    | Placeholder; only relevant to legacy symmetric Supabase projects (not enforced)     |
| `JWT_VERIFICATION_KEY` | _(empty)_                                                      | Static RSA PEM for offline dev/tests; ignored when `SUPABASE_URL` is set            |
| `JWT_ISSUER`           | `supabase`                                                     | Access-token issuer; defaults to `<SUPABASE_URL>/auth/v1` when unset and URL is set |
| `JWT_AUDIENCE`         | `authenticated`                                                | Required token `aud` claim                                                          |

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

- `UserRepository` (`app/repositories/user.py`) is the typed data-access contract for users: `get_by_id`, `get_by_email` (case-insensitive), `exists_by_email`, `create`, `create_user`. It takes a `Session` and stays free of business logic.

### Authentication Foundation

**Supabase Auth owns authentication; Nestro owns application identity and authorization.** Nestro stores no passwords, no hashes, and no tokens — the `users` table has no credential columns. Access tokens are verified on every request.

- **Authentication authority — Supabase Auth.** Clients sign in with Supabase; Supabase issues short-lived access JWTs (RS256).
- **Verification** (`app/core/auth.py`) — cookies free, stateless, every request. The JWT signature is verified against the Supabase project's JWKS endpoint (`<SUPABASE_URL>/auth/v1/.well-known/jwks.json`, fetched and cached via PyJWT's `PyJWKClient` when `SUPABASE_URL` is set; a static `JWT_VERIFICATION_KEY` PEM covers offline dev/tests). `exp`, `aud`, `iss`, and the algorithm allow-list (RS256 only) are enforced; every failure is a uniform `401`.
- **Identity — Nestro User by email.** The verified token `email` claim is looked up case-insensitively in `users` (`get_by_email`). Unknown or `is_active = false` users are rejected with the same uniform `401`. The token `sub` is a Supabase auth UUID and is never used to look up Nestro users.
- **Authorization — Nestro database only.** `get_current_user` / `require_role(...)` / `require_any_role(...)` (`app/api/deps.py`) hand routes the Nestro `User`; role and active status always come from the DB row, never from JWT claims.
- **Role guards** compose per route: `Depends(get_current_user)` for any authenticated caller, `Depends(require_role(RoleEnum.PG_OWNER))` for role-restricted ones. `SUPER_ADMIN` (platform-wide role) passes every guard.

#### Register API

Self-service tenant registration (Phase 1.4.1). Creates a Nestro user profile with `RoleEnum.TENANT`; the Supabase Auth account side ships with the Supabase-first signup milestone.

- **Endpoint** — `POST /api/v1/auth/register` (`app/api/v1/routes/auth.py`), visible in Swagger and OpenAPI.
- **Request** (`RegisterRequest`): `email` (EmailStr, normalized to lowercase), `phone`, `full_name` (stripped), `password` (min 8 chars). Strict: unknown fields rejected (`extra="forbid"`).
- **Response** (`RegisterResponse`, 201): `id` (UUID), `email`, `phone`, `full_name`, `created_at` — never the password.
- **Service** — `AuthService` (`app/services/auth_service.py`): duplicate-email check → transient password hash → create user with `RoleEnum.TENANT`.
- **Password hashing is transient** (`app/core/security.py`, Argon2id via `pwdlib`): hashes are computed for validation and then discarded. **No hash is ever persisted** — credentials remain Supabase Auth's job (see `users table`).

| Method | Path                    | Success | Errors                                                   |
| ------ | ----------------------- | ------- | -------------------------------------------------------- |
| POST   | `/api/v1/auth/register` | 201     | 409 `{"detail":"email already exists"}` · 422 validation |
| GET    | `/api/v1/auth/me`       | 200     | 401 authentication                                       |
| POST   | `/api/v1/auth/onboard`  | 201     | 409 slug/membership conflict · 422 validation            |

```json
// Request
{ "email": "user@example.com", "phone": "9876543210", "full_name": "John Doe", "password": "StrongPass123" }
// Response 201
{ "id": "…", "email": "user@example.com", "phone": "9876543210", "full_name": "John Doe", "created_at": "…" }
```

#### GET /api/v1/auth/me

Returns the authenticated Nestro user profile (`app/api/v1/routes/auth.py`).

- **Authentication** — `Authorization: Bearer <access token>`; no role restriction, any authenticated user may read their own profile.
- **Authority** — the JWT proves identity; the Nestro database provides the role, the active status, and every other field in the response. JWT role claims are never trusted.
- **Response** (`AuthMeResponse`, 200): `id`, `email`, `phone`, `full_name`, `role`, `is_active`, `created_at`, `updated_at` — database fields only, never token/internal fields.

```json
// Request
GET /api/v1/auth/me
Authorization: Bearer <access token>
// Response 200
{ "id": "…", "email": "user@example.com", "phone": "9876543210", "full_name": "John Doe", "role": "TENANT", "is_active": true, "created_at": "…", "updated_at": "…" }
```

### Onboarding Bootstrap

Bootstraps the user's first business: an organization plus an OWNER membership. One-time flow per user.

#### POST /api/v1/auth/onboard

Creates the user's first organization and owner membership (`app/services/onboarding_service.py`) — the bridge from an authenticated user to an operator. Requires authentication; runs only once per user.

- **Request** (`OnboardingRequest`): `organization_name` (1–255, stripped), `organization_slug` (3–100, lowercase, no spaces). Strict: unknown fields rejected (`extra="forbid"`).
- **Response** (`OnboardingResponse`, 201): `organization_id`, `organization_name`, `organization_slug`, `membership_id`, `role` (`OWNER`).
- **Errors** — 409 `{"detail":"organization slug already exists"}`; 409 `{"detail":"user already onboarded"}`; 422 validation; 401 unauthenticated.
- **Transaction** — the organization and membership are created in a single transaction; any failure rolls back, so a partial organization never persists.
- **Notes** — one-time bootstrap; creates the organization; creates the owner membership; does **not** create properties; does **not** join existing organizations; no invitations, switching, or multi-org support yet.

```json
// Request
POST /api/v1/auth/onboard
Authorization: Bearer <access token>
{ "organization_name": "My PG", "organization_slug": "my-pg" }
// Response 201
{ "organization_id": "…", "organization_name": "My PG", "organization_slug": "my-pg", "membership_id": "…", "role": "OWNER" }
```

### Organization Foundation

The tenant boundary sits between platform `users` and future Parking Groups. Database + models + repositories only — no routes or services yet.

- **organizations** — top-level business/customer account. `id` (UUID PK), `name`, `slug` (unique), `is_active`, mixin timestamps. The slug is lowercase, space-free, 3–100 chars.
- **organization_members** — join table connecting a user to one organization: `organization_id` / `user_id` FKs plus a `role` and mixin timestamps. `UNIQUE (organization_id, user_id)` blocks duplicate memberships.
- **Membership roles** — `OrganizationRoleEnum` (`app/models/enums.py`), stored as a native PostgreSQL ENUM `organization_role`: `OWNER`, `MANAGER`, `STAFF`. Independent from platform `RoleEnum`; resident roles arrive with the resident-profile milestone.
- **Repositories** — `OrganizationRepository` (`get_by_id`, `get_by_slug`, `exists_by_slug`, `create`) and `OrganizationMemberRepository` (`get_by_id`, `get_members_for_org`, `get_org_for_user`, `exists_membership`, `create`).
- **Schemas** — `Organization{Base,Create,Read}` and `OrganizationMember{Base,Create,Read}` (`app/schemas/`), strict with `extra="forbid"`.
- **Models** — `Organization` / `OrganizationMember` (`app/models/`) with bidirectional `members` ↔ `organization` / `user` relationships.

### Property (PG) Foundation

The first organization-scoped business entity, built on the Organization Foundation. Database + models + repositories only — no routes or services yet.

- **properties** — a venue owned by one organization (PG, hostel, hotel, apartment, co-living). `id` (UUID PK), `organization_id` (FK, indexed tenant boundary), `name`, `property_type`, `address`, `contact_phone`, `rules`, `status`, `deleted_at` (soft-delete column), mixin timestamps.
- **Enums** — `PropertyTypeEnum` (`PG`, `HOSTEL`, `HOTEL`, `APARTMENT`, `COLIVING`) and `PropertyStatusEnum` (`ACTIVE`, `INACTIVE`, `CLOSED`), stored as native PostgreSQL ENUMs `property_type` / `property_status`.
- **Repository** — `PropertyRepository` (`app/repositories/property.py`): `get_by_id`, `list_for_org`, `exists_by_name`, `create`. Every read is scoped by `organization_id` — no unscoped read path.
- **Schemas** — `Property{Base,Create,Read}` (`app/schemas/property.py`), strict with `extra="forbid"`; `PropertyCreate` carries `organization_id`.
- **Model** — `Property` (`app/models/property.py`) with bidirectional `properties` ↔ `organization` relationship.

### Property API

Org-scoped CRUD for the first business entity. Authorization always derives from `OrganizationMember.role` — **not** `users.role` — except for the platform-wide SUPER_ADMIN bypass. The caller's organization is never read from a request body field beyond `organization_id`; single-property routes derive it from the row itself.

| Role        | Read | Write |
| ----------- | ---- | ----- |
| OWNER       | Yes  | Yes   |
| MANAGER     | Yes  | Yes   |
| STAFF       | Yes  | No    |
| SUPER_ADMIN | Yes  | Yes   |

- **Endpoints** — `POST /api/v1/properties` (201), `GET /api/v1/properties?organization_id=<uuid>`, `GET /api/v1/properties/{id}`, `PATCH /api/v1/properties/{id}` (`app/api/v1/routes/properties.py`).
- **Guard** — `require_org_roles(...)` (`app/api/permissions.py`): pure org-scoped helper reading `OrganizationMember.role`; the platform SUPER_ADMIN role passes any guard. No FastAPI dependencies.
- **Service** — `PropertyService` (`app/services/property_service.py`) composes membership resolution (`OrganizationMemberRepository`) with property data access (`PropertyRepository`).
- **Create** (`PropertyCreate`) — requires OWNER/MANAGER membership in the target organization; duplicate `name` within the organization → 409.
- **Update** (`PropertyUpdate`) — only `name`, `address`, `contact_phone`, `rules`, `status` are editable; `organization_id` and `property_type` are structurally immutable (not even accepted in the request body). Omitted fields are left unchanged.
- **Read** — any member may list/get; missing property → 404.
- **Errors** — 401 unauthenticated · 403 `insufficient permissions` · 404 `property not found` · 409 `property already exists` · 422 validation.
- **Notes** — soft delete and `DELETE` are **not** implemented. No pagination or filtering yet. Building/floor/room/bed, resident, and tenant-stay APIs remain future milestones.

| Method | Path                      | Success | Errors                                                                 |
| ------ | ------------------------- | ------- | ---------------------------------------------------------------------- |
| POST   | `/api/v1/properties`      | 201     | 403 insufficient permissions · 409 duplicate · 422 validation          |
| GET    | `/api/v1/properties`      | 200     | 403 insufficient permissions · 422 missing organization_id             |
| GET    | `/api/v1/properties/{id}` | 200     | 403 insufficient permissions · 404 property not found                  |
| PATCH  | `/api/v1/properties/{id}` | 200     | 403 insufficient permissions · 404 property not found · 422 validation |

```json
// Create
POST /api/v1/properties
Authorization: Bearer <access token>
{ "organization_id": "…", "name": "PSG Boys PG", "property_type": "PG", "address": "Gandhi St, Chennai" }
// Response 201
{ "id": "…", "organization_id": "…", "name": "PSG Boys PG", "property_type": "PG", "address": "Gandhi St, Chennai", "contact_phone": null, "rules": null, "status": "ACTIVE", "created_at": "…", "updated_at": "…", "deleted_at": null }
```

```json
// Update (only provided fields change; organization_id / property_type immutable)
PATCH /api/v1/properties/{id}
Authorization: Bearer <access token>
{ "name": "PSG Boys North", "status": "INACTIVE" }
// Response 200
{ "id": "…", "organization_id": "…", "name": "PSG Boys North", "property_type": "PG", "status": "INACTIVE", "…": "…" }
```

### Building API

Org-scoped CRUD for the first level of the physical hierarchy — buildings under a property. Authorization mirrors the Property API: it derives from `OrganizationMember.role` (**not** `users.role`), except the platform-wide SUPER_ADMIN bypass. A building's organization/property is never taken from a body field beyond `organization_id`/`property_id`; single-building routes derive them from the row itself, and list/create verify the referenced property belongs to the caller's organization.

| Role        | Read | Write |
| ----------- | ---- | ----- |
| OWNER       | Yes  | Yes   |
| MANAGER     | Yes  | Yes   |
| STAFF       | Yes  | No    |
| SUPER_ADMIN | Yes  | Yes   |

- **Endpoints** — `POST /api/v1/buildings` (201), `GET /api/v1/buildings?organization_id=<uuid>&property_id=<uuid>`, `GET /api/v1/buildings/{id}`, `PATCH /api/v1/buildings/{id}` (`app/api/v1/routes/buildings.py`).
- **Guard** — `require_org_roles(...)` (`app/api/permissions.py`), the org-scoped helper shared with the Property API.
- **Service** — `BuildingService` (`app/services/building_service.py`) composes membership resolution, property existence/ownership checks (`PropertyRepository`), and building data access (`BuildingRepository`).
- **Create** (`BuildingCreate`) — requires OWNER/MANAGER membership; the referenced property must exist and belong to the same organization; duplicate `name` within a property → 409 (`UNIQUE (property_id, name)`).
- **Update** (`BuildingUpdate`) — only `name` and `description` are editable; `organization_id` and `property_id` are structurally immutable (not even accepted in the request body). Omitted fields are left unchanged.
- **Read** — any member may list/get; missing building → 404.
- **Errors** — 401 unauthenticated · 403 `insufficient permissions` · 404 `building not found` / `property not found` · 409 `building already exists` / property-organization conflict · 422 validation.
- **Notes** — no soft delete and no `DELETE`. Floor/room/bed, resident, and tenant-stay APIs remain future milestones.

| Method | Path                     | Success | Errors                                                                                           |
| ------ | ------------------------ | ------- | ------------------------------------------------------------------------------------------------ |
| POST   | `/api/v1/buildings`      | 201     | 403 insufficient permissions · 404 property not found · 409 duplicate/belongs-to-other-org · 422 |
| GET    | `/api/v1/buildings`      | 200     | 403 insufficient permissions · 404 property not found · 422 missing query params                 |
| GET    | `/api/v1/buildings/{id}` | 200     | 403 insufficient permissions · 404 building not found                                            |
| PATCH  | `/api/v1/buildings/{id}` | 200     | 403 insufficient permissions · 404 building not found · 422 validation                           |

```json
// Create
POST /api/v1/buildings
Authorization: Bearer <access token>
{ "organization_id": "…", "property_id": "…", "name": "Block A", "description": "North wing" }
// Response 201
{ "id": "…", "organization_id": "…", "property_id": "…", "name": "Block A", "description": "North wing", "created_at": "…", "updated_at": "…" }
```

```json
// Update (only provided fields change; organization_id / property_id immutable)
PATCH /api/v1/buildings/{id}
Authorization: Bearer <access token>
{ "name": "Block A North", "description": "Renamed wing" }
// Response 200
{ "id": "…", "organization_id": "…", "property_id": "…", "name": "Block A North", "description": "Renamed wing", "…": "…" }
```

### Physical Structure Foundation

The inventory hierarchy under a property. Database + models + repositories only — no routes, services, occupancy, or assignment yet.

```text
Organization
    └── Property
          └── Building
                └── Floor
                      └── Room
                            └── Bed (0..N)
```

- **buildings** — `id`, `organization_id` (FK, indexed), `property_id` (FK, indexed), `name`, `description`, mixin timestamps. `UNIQUE (property_id, name)`.
- **floors** — `id`, `organization_id` (FK, indexed), `building_id` (FK, indexed), `floor_number`, `name`, mixin timestamps. `UNIQUE (building_id, floor_number)`.
- **rooms** — `id`, `organization_id` (FK, indexed), `floor_id` (FK, indexed), `room_number` (indexed), `room_type`, mixin timestamps. `UNIQUE (floor_id, room_number)`.
- **beds** — `id`, `organization_id` (FK, indexed), `room_id` (FK, indexed), `bed_number`, `status` (indexed), mixin timestamps. `UNIQUE (room_id, bed_number)`.
- **Room capacity is not stored.** Capacity is always derived from the number of `Bed` records associated with a `Room` (`COUNT(beds.id)`). This allows rooms to support any number of beds without schema changes: a single room has 1 bed, a double has 2, a four-share PG room has 4, a dorm has 20+. No `capacity` / `max_beds` / `bed_count` column exists anywhere.
- **Enums** — `RoomTypeEnum` (`SINGLE`, `DOUBLE`, `TRIPLE`, `FOUR_SHARE`, `FIVE_SHARE`, `CUSTOM`) and `BedStatusEnum` (`AVAILABLE`, `OCCUPIED`, `BLOCKED`, `MAINTENANCE`), stored as native PostgreSQL ENUMs `room_type` / `bed_status`.
- **Repositories** — `BuildingRepository` / `FloorRepository` / `RoomRepository` / `BedRepository`: each has `get_by_id`, a scoped `list_for_<parent>` (`list_for_property` / `list_for_building` / `list_for_floor` / `list_for_room`), and `create`. Every read is scoped by `organization_id` — no unscoped read path.
- **Schemas** — `{Building,Floor,Room,Bed}{Base,Create,Read}` (`app/schemas/`), strict with `extra="forbid"`; `Create` carries `organization_id` and the parent FK. `RoomRead` has no capacity field.
- **Models** — `Building` / `Floor` / `Room` / `Bed` (`app/models/`) with fully bidirectional relationships (`property` ↔ `buildings` ↔ `floors` ↔ `rooms` ↔ `beds`).

### Tenant Foundation

The resident/tenant domain layer. Database + models + repositories only — no routes, services, bookings, or business logic yet.

```text
User
    ↓  (organization_members)
Organization Member
    ↓
ResidentProfile
    ↓  (Tenant Stay Foundation)
TenantStay / Bed Assignment
```

- **resident_profiles** — one residency profile per organization membership (`UNIQUE (organization_member_id)`). `id` (UUID PK), `organization_id` (FK, indexed tenant boundary), `organization_member_id` (FK, unique), `property_id` (FK, nullable, indexed — a profile can exist before assignment), `emergency_contact_name`, `emergency_contact_phone`, `address`, `notes` (nullable), `is_active` (default true), mixin timestamps.
- **Identity via membership, not the raw user** — names/phone/email stay on `users`; the profile adds only residency data (DATABASE.md §14). Because uniqueness is per membership, a user can be a resident in multiple organizations through separate memberships.
- **No lifecycle columns** — move-in/move-out and occupancy history live in `tenant_stays` (§15, Tenant Stay Foundation below); the profile intentionally does not store moved-in/out dates. Capacity-related rules from 1.3.8 keep applying (rooms derive size from their beds).
- **Repository** — `ResidentProfileRepository` (`app/repositories/resident_profile.py`): `get_by_id`, `get_by_user_id` (multi-org aware, joins via `organization_members`), `list_for_org`, `exists_for_user`, `create`. Every read is scoped by organization or user — no unscoped read path.
- **Schemas** — `ResidentProfile{Base,Create,Read}` (`app/schemas/resident_profile.py`), strict with `extra="forbid"`; `ResidentProfileCreate` carries `organization_id` + `organization_member_id`.
- **Models** — `ResidentProfile` (`app/models/resident_profile.py`) with bidirectional `organization` ↔ `resident_profiles`, `organization_member` ↔ `resident_profile`, `property` ↔ `resident_profiles`.

### Tenant Stay Foundation

Occupancy history and bed assignment. Database + models + repositories only — no routes, services, check-in/check-out workflows, or billing yet.

```text
User
    ↓  (organization_members)
Organization Member
    ↓
ResidentProfile
    ↓
TenantStay
    ↓
Bed
```

- **tenant_stays** — one stay = a resident (`resident_profile_id`) occupying a bed (`bed_id`) inside a property (`property_id`, stored for venue-queryable occupancy) for a period. `start_date` (required), `end_date` (nullable — an open stay has none), `status`, `notes` (nullable), mixin timestamps. `organization_id` FK + index on every stay (tenant boundary).
- **Occupancy is stays, not a resident→bed column** — a "current bed" is `get_active_for_bed(bed_id)`, and the whole history (COMPLETED / CANCELLED stays) stays queryable (`list_for_bed`). Never store `resident → bed` directly (DATABASE.md §15).
- **Status** — `TenantStayStatusEnum` (`ACTIVE`, `COMPLETED`, `CANCELLED`), native PostgreSQL ENUM `tenant_stay_status`; defaults to `ACTIVE` on create.
- **One ACTIVE stay per bed** — enforced by a **partial unique index** `uq_tenant_stays_active_bed` on `(bed_id) WHERE status = 'ACTIVE'` (both SQLite and PostgreSQL). This is the deliberate alternative to `UNIQUE (bed_id, status)`, which would permit only a single COMPLETED stay per bed and break history. Deferred with the billing milestone: `security_deposit` and a one-ACTIVE-per-resident rule.
- **Repository** — `TenantStayRepository` (`app/repositories/tenant_stay.py`): `get_by_id`, `list_for_org`, `list_for_resident`, `list_for_bed`, `get_active_for_bed`, `create`. Every read is scoped by stay id, organization, resident, or bed — no unscoped read path.
- **Schemas** — `TenantStay{Base,Create,Read}` (`app/schemas/tenant_stay.py`), strict with `extra="forbid"`; `end_date` / `notes` nullable, `status` defaults to `ACTIVE`.
- **Models** — `TenantStay` (`app/models/tenant_stay.py`) with bidirectional `organization` / `resident_profile` / `property` / `bed` ↔ `tenant_stays` relationships.

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
├── api/v1/     versioned HTTP routes (health, auth/register, auth/me, auth/onboard, properties, buildings)
├── core/       config (pydantic-settings), logging, lifespan, exceptions, security (JWT verification + JWKS, password hashing)
├── db/         declarative Base (naming conventions), engine/session, mixins, health
├── models/     SQLAlchemy models (users, orgs, memberships, properties, buildings, floors, rooms, beds, resident profiles, tenant stays, enums)
├── repositories/  data access (users, orgs, memberships, properties, buildings, floors, rooms, beds, resident profiles, tenant stays)
├── schemas/    Pydantic request/response models (users, auth, orgs, properties, buildings, building_api, floors, rooms, beds, resident profiles, tenant stays)
├── services/   business logic (auth service — registration; onboarding service; property service; building service)
└── main.py     create_application() factory, exposes `app`
alembic/        migration structure (schema change ships with a migration)
tests/          pytest suite
```

## Conventions

- All imports are absolute from the `app` package: `from app.core.config import settings`.
- Every request/response is validated by a Pydantic model.
- Config comes from environment variables only; no secrets in code or commits.
- The app is built by `create_application()`; routers, exception handlers, logging, and lifespan are registered there, keeping `main.py` small.
