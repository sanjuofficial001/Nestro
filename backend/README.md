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

### Floor API

Org-scoped CRUD for the second level of the physical hierarchy — floors within a building. Authorization mirrors the Property/Building APIs: it derives from `OrganizationMember.role` (**not** `users.role`), except the platform-wide SUPER_ADMIN bypass. A floor's organization/building is never taken from a body field beyond `organization_id`/`building_id`; single-floor routes derive them from the row itself, and list/create verify the referenced building belongs to the caller's organization.

| Role        | Read | Write |
| ----------- | ---- | ----- |
| OWNER       | Yes  | Yes   |
| MANAGER     | Yes  | Yes   |
| STAFF       | Yes  | No    |
| SUPER_ADMIN | Yes  | Yes   |

- **Endpoints** — `POST /api/v1/floors` (201), `GET /api/v1/floors?organization_id=<uuid>&building_id=<uuid>`, `GET /api/v1/floors/{id}`, `PATCH /api/v1/floors/{id}` (`app/api/v1/routes/floors.py`).
- **Guard** — `require_org_roles(...)` (`app/api/permissions.py`), the org-scoped helper shared with the Property/Building APIs.
- **Service** — `FloorService` (`app/services/floor_service.py`) composes membership resolution, building existence/ownership checks (`BuildingRepository`), and floor data access (`FloorRepository`).
- **Create** (`FloorCreate`) — requires OWNER/MANAGER membership; the referenced building must exist and belong to the same organization; duplicate `floor_number` within a building → 409 (`UNIQUE (building_id, floor_number)`).
- **Update** (`FloorUpdate`) — only `floor_number` and `name` are editable; `organization_id` and `building_id` are structurally immutable (not even accepted in the request body). Changing `floor_number` to a value already used in the building → 409. Omitted fields are left unchanged.
- **Read** — any member may list/get; missing floor → 404.
- **Errors** — 401 unauthenticated · 403 `insufficient permissions` · 404 `floor not found` / `building not found` · 409 `floor already exists` / building-organization conflict · 422 validation.
- **Notes** — no soft delete and no `DELETE`. Room/bed, resident, and tenant-stay APIs remain future milestones.

| Method | Path                  | Success | Errors                                                                                           |
| ------ | --------------------- | ------- | ------------------------------------------------------------------------------------------------ |
| POST   | `/api/v1/floors`      | 201     | 403 insufficient permissions · 404 building not found · 409 duplicate/belongs-to-other-org · 422 |
| GET    | `/api/v1/floors`      | 200     | 403 insufficient permissions · 404 building not found · 422 missing query params                 |
| GET    | `/api/v1/floors/{id}` | 200     | 403 insufficient permissions · 404 floor not found                                               |
| PATCH  | `/api/v1/floors/{id}` | 200     | 403 insufficient permissions · 404 floor not found · 409 duplicate floor number · 422 validation |

```json
// Create
POST /api/v1/floors
Authorization: Bearer <access token>
{ "organization_id": "…", "building_id": "…", "floor_number": 1, "name": "First" }
// Response 201
{ "id": "…", "organization_id": "…", "building_id": "…", "floor_number": 1, "name": "First", "created_at": "…", "updated_at": "…" }
```

```json
// Update (only provided fields change; organization_id / building_id immutable)
PATCH /api/v1/floors/{id}
Authorization: Bearer <access token>
{ "floor_number": 2, "name": "Second" }
// Response 200
{ "id": "…", "organization_id": "…", "building_id": "…", "floor_number": 2, "name": "Second", "…": "…" }
```

### Room API

Org-scoped CRUD for the third level of the physical hierarchy — rooms within a floor. Authorization mirrors the Property/Building/Floor APIs: it derives from `OrganizationMember.role` (**not** `users.role`), except the platform-wide SUPER_ADMIN bypass. A room's organization/floor is never taken from a body field beyond `organization_id`/`floor_id`; single-room routes derive them from the row itself, and list/create verify the referenced floor belongs to the caller's organization.

| Role        | Read | Write |
| ----------- | ---- | ----- |
| OWNER       | Yes  | Yes   |
| MANAGER     | Yes  | Yes   |
| STAFF       | Yes  | No    |
| SUPER_ADMIN | Yes  | Yes   |

- **Endpoints** — `POST /api/v1/rooms` (201), `GET /api/v1/rooms?organization_id=<uuid>&floor_id=<uuid>`, `GET /api/v1/rooms/{id}`, `PATCH /api/v1/rooms/{id}` (`app/api/v1/routes/rooms.py`).
- **Guard** — `require_org_roles(...)` (`app/api/permissions.py`), the org-scoped helper shared with the Property/Building/Floor APIs.
- **Service** — `RoomService` (`app/services/room_service.py`) composes membership resolution, floor existence/ownership checks (`FloorRepository`), and room data access (`RoomRepository`).
- **Create** (`RoomCreate`) — requires OWNER/MANAGER membership; the referenced floor must exist and belong to the same organization; duplicate `room_number` within a floor → 409 (`UNIQUE (floor_id, room_number)`).
- **Update** (`RoomUpdate`) — only `room_number` and `room_type` are editable; `organization_id` and `floor_id` are structurally immutable (not even accepted in the request body). Changing `room_number` to a value already used in the floor → 409. Omitted fields are left unchanged.
- **Read** — any member may list/get; missing room → 404.
- **Capacity is derived, never stored** — a room has no `capacity`/`max_beds`/`bed_count` column, schema field, or response field. Its size is always `COUNT(beds.id)` (see Physical Structure Foundation below).
- **Errors** — 401 unauthenticated · 403 `insufficient permissions` · 404 `room not found` / `floor not found` · 409 `room already exists` / floor-organization conflict · 422 validation.
- **Notes** — no soft delete and no `DELETE`. Bed, resident, and tenant-stay APIs remain future milestones.

| Method | Path                 | Success | Errors                                                                                         |
| ------ | -------------------- | ------- | ---------------------------------------------------------------------------------------------- |
| POST   | `/api/v1/rooms`      | 201     | 403 insufficient permissions · 404 floor not found · 409 duplicate/belongs-to-other-org · 422  |
| GET    | `/api/v1/rooms`      | 200     | 403 insufficient permissions · 404 floor not found · 422 missing query params                  |
| GET    | `/api/v1/rooms/{id}` | 200     | 403 insufficient permissions · 404 room not found                                              |
| PATCH  | `/api/v1/rooms/{id}` | 200     | 403 insufficient permissions · 404 room not found · 409 duplicate room number · 422 validation |

```json
// Create
POST /api/v1/rooms
Authorization: Bearer <access token>
{ "organization_id": "…", "floor_id": "…", "room_number": "101", "room_type": "DOUBLE" }
// Response 201
{ "id": "…", "organization_id": "…", "floor_id": "…", "room_number": "101", "room_type": "DOUBLE", "created_at": "…", "updated_at": "…" }
```

```json
// Update (only provided fields change; organization_id / floor_id immutable)
PATCH /api/v1/rooms/{id}
Authorization: Bearer <access token>
{ "room_number": "201", "room_type": "TRIPLE" }
// Response 200
{ "id": "…", "organization_id": "…", "floor_id": "…", "room_number": "201", "room_type": "TRIPLE", "…": "…" }
```

### Bed API

Org-scoped CRUD for the fourth level of the physical hierarchy — beds within a room. Authorization mirrors the Property/Building/Floor/Room APIs: it derives from `OrganizationMember.role` (**not** `users.role`), except the platform-wide SUPER_ADMIN bypass. A bed's organization/room is never taken from a body field beyond `organization_id`/`room_id`; single-bed routes derive them from the row itself, and list/create verify the referenced room belongs to the caller's organization.

| Role        | Read | Write |
| ----------- | ---- | ----- |
| OWNER       | Yes  | Yes   |
| MANAGER     | Yes  | Yes   |
| STAFF       | Yes  | No    |
| SUPER_ADMIN | Yes  | Yes   |

- **Endpoints** — `POST /api/v1/beds` (201), `GET /api/v1/beds?organization_id=<uuid>&room_id=<uuid>`, `GET /api/v1/beds/{id}`, `PATCH /api/v1/beds/{id}` (`app/api/v1/routes/beds.py`).
- **Guard** — `require_org_roles(...)` (`app/api/permissions.py`), the org-scoped helper shared with the Property/Building/Floor/Room APIs.
- **Service** — `BedService` (`app/services/bed_service.py`) composes membership resolution, room existence/ownership checks (`RoomRepository`), and bed data access (`BedRepository`).
- **Create** (`BedCreate`) — requires OWNER/MANAGER membership; the referenced room must exist and belong to the same organization; duplicate `bed_number` within a room → 409 (`UNIQUE (room_id, bed_number)`). `status` defaults to `AVAILABLE`.
- **Update** (`BedUpdate`) — only `bed_number` and `status` are editable; `organization_id` and `room_id` are structurally immutable (not even accepted in the request body). Changing `bed_number` to a value already used in the room → 409. Omitted fields are left unchanged.
- **Read** — any member may list/get; missing bed → 404.
- **Capacity is derived, never stored** — Room capacity is always derived from `COUNT(beds.id)`. No capacity value is stored in the database or returned by Bed APIs.
- **Errors** — 401 unauthenticated · 403 `insufficient permissions` · 404 `bed not found` / `room not found` · 409 `bed already exists` / room-organization conflict · 422 validation.
- **Notes** — no soft delete and no `DELETE`. Bed assignment, occupancy, resident profiles, and tenant-stay APIs remain future milestones.

| Method | Path                | Success | Errors                                                                                       |
| ------ | ------------------- | ------- | -------------------------------------------------------------------------------------------- |
| POST   | `/api/v1/beds`      | 201     | 403 insufficient permissions · 404 room not found · 409 duplicate/belongs-to-other-org · 422 |
| GET    | `/api/v1/beds`      | 200     | 403 insufficient permissions · 404 room not found · 422 missing query params                 |
| GET    | `/api/v1/beds/{id}` | 200     | 403 insufficient permissions · 404 bed not found                                             |
| PATCH  | `/api/v1/beds/{id}` | 200     | 403 insufficient permissions · 404 bed not found · 409 duplicate bed number · 422 validation |

```json
// Create
POST /api/v1/beds
Authorization: Bearer <access token>
{ "organization_id": "…", "room_id": "…", "bed_number": "1", "status": "AVAILABLE" }
// Response 201
{ "id": "…", "organization_id": "…", "room_id": "…", "bed_number": "1", "status": "AVAILABLE", "created_at": "…", "updated_at": "…" }
```

```json
// Update (only provided fields change; organization_id / room_id immutable)
PATCH /api/v1/beds/{id}
Authorization: Bearer <access token>
{ "bed_number": "2", "status": "BLOCKED" }
// Response 200
{ "id": "…", "organization_id": "…", "room_id": "…", "bed_number": "2", "status": "BLOCKED", "…": "…" }
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
- **Repository** — `ResidentProfileRepository` (`app/repositories/resident_profile.py`): `get_by_id`, `get_by_user_id` (multi-org aware, joins via `organization_members`), `list_for_org`, `exists_for_user`, `exists_for_member` (mirrors `UNIQUE (organization_member_id)`), `create`. Every read is scoped by organization or user — no unscoped read path.
- **Schemas** — `ResidentProfile{Base,Create,Read}` (`app/schemas/resident_profile.py`), strict with `extra="forbid"`; `ResidentProfileCreate` carries `organization_id` + `organization_member_id`.
- **Models** — `ResidentProfile` (`app/models/resident_profile.py`) with bidirectional `organization` ↔ `resident_profiles`, `organization_member` ↔ `resident_profile`, `property` ↔ `resident_profiles`.

### Resident Profile API

Org-scoped CRUD for resident profiles. A profile is not a hierarchy node: it belongs to an **organization membership** (`UNIQUE (organization_member_id)`) and may optionally reference a property. Authorization mirrors the Property/Building/Floor/Room/Bed APIs: it derives from `OrganizationMember.role` (**not** `users.role`), except the platform-wide SUPER_ADMIN bypass. A profile's organization and membership are never taken from a body field beyond `organization_id`/`organization_member_id`; single-profile routes derive them from the row itself, and create/update verify the referenced membership and any supplied `property_id` belong to the caller's organization.

| Role        | Read | Write |
| ----------- | ---- | ----- |
| OWNER       | Yes  | Yes   |
| MANAGER     | Yes  | Yes   |
| STAFF       | Yes  | No    |
| SUPER_ADMIN | Yes  | Yes   |

- **Endpoints** — `POST /api/v1/resident-profiles` (201), `GET /api/v1/resident-profiles?organization_id=<uuid>`, `GET /api/v1/resident-profiles/{id}`, `PATCH /api/v1/resident-profiles/{id}` (`app/api/v1/routes/resident_profiles.py`).
- **Guard** — `require_org_roles(...)` (`app/api/permissions.py`), the org-scoped helper shared with every org-scoped API.
- **Service** — `ResidentProfileService` (`app/services/resident_profile_service.py`) composes membership resolution, membership/property existence + ownership checks (`OrganizationMemberRepository`, `PropertyRepository`), and profile data access (`ResidentProfileRepository`).
- **Create** (`ResidentProfileCreate`) — requires OWNER/MANAGER membership; the referenced membership must exist and belong to the same organization; a supplied `property_id` must exist and belong to the same organization; a second profile for the same membership → 409 (`UNIQUE (organization_member_id)`).
- **Update** (`ResidentProfileUpdate`) — only `property_id`, `emergency_contact_name`, `emergency_contact_phone`, `address`, `notes`, and `is_active` are editable; `organization_id` and `organization_member_id` are structurally immutable (not even accepted in the request body), which also makes `UNIQUE (organization_member_id)` unreachable from an update. A changed `property_id` is re-validated against the organization. Omitted fields are left unchanged.
- **Read** — any member may list/get; missing profile → 404.
- **Errors** — 401 unauthenticated/inactive · 403 `insufficient permissions` · 404 `resident profile not found` / `organization member not found` / `property not found` · 409 `resident profile already exists` / membership-organization or property-organization conflict · 422 validation.
- **Notes** — `property_id` is optional (a profile can exist before property assignment). No bed assignment, move-in/move-out, occupancy, billing, and no soft delete or `DELETE` — those remain future milestones (`tenant_stays` owns stay history).

| Method | Path                             | Success | Errors                                                                                                                       |
| ------ | -------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------- |
| POST   | `/api/v1/resident-profiles`      | 201     | 403 insufficient permissions · 404 organization member/property not found · 409 duplicate/belongs-to-other-org · 422         |
| GET    | `/api/v1/resident-profiles`      | 200     | 403 insufficient permissions · 422 missing query params                                                                      |
| GET    | `/api/v1/resident-profiles/{id}` | 200     | 403 insufficient permissions · 404 resident profile not found                                                                |
| PATCH  | `/api/v1/resident-profiles/{id}` | 200     | 403 insufficient permissions · 404 resident profile/property not found · 409 property-organization conflict · 422 validation |

```json
// Create
POST /api/v1/resident-profiles
Authorization: Bearer <access token>
{ "organization_id": "…", "organization_member_id": "…", "property_id": "…", "emergency_contact_name": "Asha Rao", "emergency_contact_phone": "9876543210", "address": "12 MG Road" }
// Response 201
{ "id": "…", "organization_id": "…", "organization_member_id": "…", "property_id": "…", "emergency_contact_name": "Asha Rao", "emergency_contact_phone": "9876543210", "address": "12 MG Road", "notes": null, "is_active": true, "created_at": "…", "updated_at": "…" }
```

```json
// Update (only provided fields change; organization_id / organization_member_id immutable)
PATCH /api/v1/resident-profiles/{id}
Authorization: Bearer <access token>
{ "emergency_contact_name": "Asha Menon", "is_active": false }
// Response 200
{ "id": "…", "organization_id": "…", "organization_member_id": "…", "…": "…", "emergency_contact_name": "Asha Menon", "is_active": false }
```

### Tenant Stay Foundation

Occupancy history and bed assignment. Database + models + schemas + repositories. The HTTP surface lives in [Tenant Stay API](#tenant-stay-api) below; check-in/check-out workflows and billing are still future work.

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
- **Repository** — `TenantStayRepository` (`app/repositories/tenant_stay.py`): `get_by_id`, `list_for_org`, `list_for_resident`, `list_for_bed`, `get_active_for_bed`, `create`. The three list methods take an optional `status` filter applied in SQL; ordering is always `start_date DESC`. Every read is scoped by stay id, organization, resident, or bed — no unscoped read path.
- **Schemas** — `TenantStay{Base,Create,Read}` (`app/schemas/tenant_stay.py`), strict with `extra="forbid"`; `end_date` / `notes` nullable, `status` defaults to `ACTIVE`.
- **Models** — `TenantStay` (`app/models/tenant_stay.py`) with bidirectional `organization` / `resident_profile` / `property` / `bed` ↔ `tenant_stays` relationships.

### Tenant Stay API

Org-scoped CRUD over occupancy history. A stay is the only thing that records "this resident occupied this bed from this date", so occupancy is derived from `ACTIVE` stays — never stored on the resident or the bed. Authorization mirrors the Property/Building/Floor/Room/Bed/Resident Profile APIs: it derives from `OrganizationMember.role` (**not** `users.role`), except the platform-wide SUPER_ADMIN bypass. A stay's organization is never taken from a body field beyond `organization_id` on create; single-stay routes derive it from the row itself.

| Role        | Read | Write |
| ----------- | ---- | ----- |
| OWNER       | Yes  | Yes   |
| MANAGER     | Yes  | Yes   |
| STAFF       | Yes  | No    |
| SUPER_ADMIN | Yes  | Yes   |

- **Endpoints** — `POST /api/v1/tenant-stays` (201), `GET /api/v1/tenant-stays?organization_id=<uuid>[&resident_profile_id=&bed_id=&status=]`, `GET /api/v1/tenant-stays/{id}`, `PATCH /api/v1/tenant-stays/{id}` (`app/api/v1/routes/tenant_stays.py`).
- **Guard** — `require_org_roles(...)` (`app/api/permissions.py`), the org-scoped helper shared with every org-scoped API.
- **Service** — `TenantStayService` (`app/services/tenant_stay_service.py`) composes membership resolution, resident/bed/property existence + ownership checks (`ResidentProfileRepository`, `BedRepository`, `PropertyRepository`), and stay data access (`TenantStayRepository`).
- **Create** (`TenantStayCreate`) — requires OWNER/MANAGER membership; the referenced resident profile, bed, and property must each exist and belong to the same organization; the bed's real property (`bed.room.floor.building.property_id`) must equal the supplied `property_id`, so a stay can never claim a property its bed is not in; an `ACTIVE` stay on a bed that already has one → 409.
- **Update** (`TenantStayUpdate`) — only `end_date`, `status`, and `notes` are editable; `organization_id`, `resident_profile_id`, `property_id`, `bed_id`, and `start_date` are structurally immutable (not even accepted in the request body), which is what keeps "who/where/when it began" fixed. Omitted fields are left unchanged; `null` never clears a value.
- **Status semantics** — `ACTIVE` is the only occupied state and its `end_date` must be null; `COMPLETED` (ended on its own) and `CANCELLED` (terminated early) are closed history and always carry an `end_date`; a closed stay cannot be reopened (`COMPLETED` ↔ `CANCELLED` is allowed). `end_date` never precedes `start_date`.
- **One ACTIVE stay per bed** — enforced in the database by `uq_tenant_stays_active_bed` and pre-checked with `get_active_for_bed`, so a collision is a 409 rather than a 500. Closing a stay frees the bed because it simply stops being `ACTIVE`; nothing is deleted.
- **Read** — any member may list/get. Listing takes required `organization_id` plus optional `resident_profile_id`, `bed_id`, and `status`; results are ordered by `start_date DESC`. Resident/bed filters are org-checked first so a foreign-org id returns 404 rather than leaking rows.
- **Errors** — 401 unauthenticated/inactive · 403 `insufficient permissions` · 404 `tenant stay not found` / `resident profile not found` / `bed not found` / `property not found` · 409 `end_date must not precede start_date` / `an active stay cannot have an end_date` / `a closed stay requires an end_date` / `a closed stay cannot be reopened` / `bed already has an active stay` / resident-organization, bed-organization, or property-organization conflict / `bed does not belong to the property` · 422 validation.
- **Not here (future work)** — a one-ACTIVE-per-resident constraint and `security_deposit` (deferred to the billing milestone, DATABASE.md §15), billing/rent/invoices, bed transfers, resident reassignment, occupancy dashboards, notifications, and no soft delete or `DELETE`.

| Method | Path                        | Success | Errors                                                                                                          |
| ------ | --------------------------- | ------- | --------------------------------------------------------------------------------------------------------------- |
| POST   | `/api/v1/tenant-stays`      | 201     | 403 insufficient permissions · 404 resident/bed/property not found · 409 lifecycle/ownership/occupied-bed · 422 |
| GET    | `/api/v1/tenant-stays`      | 200     | 403 insufficient permissions · 404 resident/bed not found · 422 missing query params                            |
| GET    | `/api/v1/tenant-stays/{id}` | 200     | 403 insufficient permissions · 404 tenant stay not found                                                        |
| PATCH  | `/api/v1/tenant-stays/{id}` | 200     | 403 insufficient permissions · 404 tenant stay not found · 409 lifecycle conflict · 422 validation              |

```json
// Create (check-in)
POST /api/v1/tenant-stays
Authorization: Bearer <access token>
{ "organization_id": "…", "resident_profile_id": "…", "property_id": "…", "bed_id": "…", "start_date": "2026-01-01" }
// Response 201
{ "id": "…", "organization_id": "…", "resident_profile_id": "…", "property_id": "…", "bed_id": "…", "start_date": "2026-01-01", "end_date": null, "status": "ACTIVE", "notes": null, "created_at": "…", "updated_at": "…" }
```

```json
// Update (check-out) — status and end_date close the stay together
PATCH /api/v1/tenant-stays/{id}
Authorization: Bearer <access token>
{ "status": "COMPLETED", "end_date": "2026-06-30", "notes": "  Vacated early  " }
// Response 200
{ "id": "…", "…": "…", "status": "COMPLETED", "end_date": "2026-06-30", "notes": "Vacated early" }
```

```json
// List (any member); optional resident_profile_id / bed_id / status narrow the result
GET /api/v1/tenant-stays?organization_id=…&status=ACTIVE
Authorization: Bearer <access token>
// Response 200
[ { "id": "…", "bed_id": "…", "resident_profile_id": "…", "status": "ACTIVE", "start_date": "2026-01-01", "end_date": null, "…": "…" } ]
```

### Complaint Foundation

Resident-raised issues and their triage state. Database + models + schemas + repositories. The HTTP surface lives in [Complaint API](#complaint-api) and [Complaint Comment API](#complaint-comment-api) below; resident-facing submission and the reopen audit are still future work.

```text
User
    ↓  (organization_members)
Organization Member
    ↓
ResidentProfile
    ↓
Complaint
    ↓
Property
    ↓
ComplaintComment  (discussion thread)
```

- **complaints** — one complaint = an issue a resident (`resident_profile_id`) raised about a property (`property_id`) inside an organization (`organization_id`). `title`, `description`, `category`, `priority`, `status`, `assigned_to_member_id` (nullable), `resolved_at` (nullable), mixin timestamps. `organization_id` FK + index on every complaint (tenant boundary), plus indexes on `property_id`, `resident_profile_id`, `status`, and `priority` because those are the query shapes the API exposes.
- **Category** — `ComplaintCategoryEnum` (`MAINTENANCE`, `ELECTRICAL`, `PLUMBING`, `FOOD`, `HOUSEKEEPING`, `SECURITY`, `INTERNET`, `OTHER`), native PostgreSQL ENUM `complaint_category`. Fixed at creation: a complaint is filed under the category it was raised as, so `ComplaintUpdate` does not accept it and a PATCH carrying it is a 422.
- **Priority** — `ComplaintPriorityEnum` (`LOW`, `MEDIUM`, `HIGH`, `URGENT`), native ENUM `complaint_priority`; defaults to `MEDIUM` on create and is editable.
- **Status** — `ComplaintStatusEnum` (`OPEN`, `IN_PROGRESS`, `ON_HOLD`, `RESOLVED`, `CLOSED`), native ENUM `complaint_status`; defaults to `OPEN` on create. **Declaration order is the workflow order** and is part of the contract — the service derives legal transitions from it. Prefer adding a new stage at the end of the enum over reordering it.
- **Assignment is a membership, not a user** — `assigned_to_member_id` → `organization_members.id`, not `users.id`. A user can belong to several organizations, so a bare user id would be ambiguous about which org the assignment was made in.
- **`resolved_at` is never written in this milestone** — the column exists per DATABASE.md §19, but stamping it belongs to the workflow milestone alongside `complaint_comments` (§20) and the reopen audit. A complaint can reach `RESOLVED` with `resolved_at` still null.
- **Repository** — `ComplaintRepository` (`app/repositories/complaint.py`): `get_by_id`, `list_for_org`, `create`. `list_for_org` takes optional `status` / `priority` / `resident_profile_id` filters applied in SQL; ordering is always `created_at DESC`. Every read is scoped by complaint id or organization — no unscoped read path.
- **Schemas** — `Complaint{Base,Create,Read}` (`app/schemas/complaint.py`), strict with `extra="forbid"`; `title` bounded at 200 chars and `description` at 2000, both stripped, and an all-whitespace payload is rejected (the bound is enforced here because the columns are `TEXT` and PostgreSQL does not length-check them).
- **Models** — `Complaint` (`app/models/complaint.py`) with bidirectional `organization` / `property` / `resident_profile` / `assigned_to_member` ↔ `complaints` relationships, plus `comments` ↔ `complaint_comments`.
- **complaint_comments** — one immutable message in a complaint's discussion thread. `complaint_id`, `user_id`, `comment`, `is_internal` (default false), `created_at`; index on `complaint_id`. Per DATABASE.md §20 it carries **no** `organization_id` (scope is authoritative on the parent complaint) and **no** `updated_at` (comments are immutable, so the timestamp would never move), and it has no delete cascade — a complaint delete fails on the foreign key instead of silently erasing audit history.

### Complaint API

Org-scoped CRUD over resident complaints. A complaint is triage state, so every reference on it is resolved and ownership-checked before it is stored and every operation is gated on the caller's membership in the complaint's organization. Authorization mirrors the Property/Building/Floor/Room/Bed/Resident Profile/Tenant Stay APIs: it derives from `OrganizationMember.role` (**not** `users.role`), except the platform-wide SUPER_ADMIN bypass. A complaint's organization is never taken from a body field beyond `organization_id` on create; single-complaint routes derive it from the row itself.

| Role        | Read | Write |
| ----------- | ---- | ----- |
| OWNER       | Yes  | Yes   |
| MANAGER     | Yes  | Yes   |
| STAFF       | Yes  | No    |
| SUPER_ADMIN | Yes  | Yes   |

- **Endpoints** — `POST /api/v1/complaints` (201), `GET /api/v1/complaints?organization_id=<uuid>[&status=&priority=&resident_profile_id=]`, `GET /api/v1/complaints/{id}`, `PATCH /api/v1/complaints/{id}` (`app/api/v1/routes/complaints.py`).
- **Guard** — `require_org_roles(...)` (`app/api/permissions.py`), the org-scoped helper shared with every org-scoped API.
- **Service** — `ComplaintService` (`app/services/complaint_service.py`) composes membership resolution, property/resident/assignee existence + ownership checks (`PropertyRepository`, `ResidentProfileRepository`, `OrganizationMemberRepository`), and complaint data access (`ComplaintRepository`).
- **Create** (`ComplaintCreate`) — requires OWNER/MANAGER membership; the referenced property, resident profile, and (when given) assignee must each exist and belong to the same organization.
- **Update** (`ComplaintUpdate`) — only `title`, `description`, `status`, `priority`, and `assigned_to_member_id` are editable; `organization_id`, `property_id`, `resident_profile_id`, and `category` are structurally immutable (not even accepted in the request body), which is what keeps "what/where/who raised it" fixed. Omitted fields are left unchanged; `null` never clears a value.
- **Status lifecycle** — a complaint may stay put, step **one** stage forward, or step **one** stage backward along `OPEN ↔ IN_PROGRESS ↔ ON_HOLD ↔ RESOLVED → CLOSED`; a jump of two or more stages is a 409, and `CLOSED` is terminal (no reopen, not even one stage back).
- **Read** — any member may list/get. Listing takes required `organization_id` plus optional `status`, `priority`, and `resident_profile_id`; results are ordered by `created_at DESC`. The resident filter is org-checked first so a foreign-org id returns 404 rather than leaking rows.
- **Errors** — 401 unauthenticated/inactive · 403 `insufficient permissions` · 404 `complaint not found` / `resident profile not found` / `property not found` / `organization member not found` · 409 `invalid complaint status transition` / `a closed complaint cannot be reopened` / resident-, property-, or member-organization conflict · 422 validation (including `category` and `resolved_at` on PATCH).
- **Not here (future work)** — resident-facing complaint submission, the reopen audit, `resolved_at` stamping and notification on transition, SLA/escalation timers, assignment history, complaint dashboards, and no soft delete or `DELETE`.

| Method | Path                      | Success | Errors                                                                                      |
| ------ | ------------------------- | ------- | ------------------------------------------------------------------------------------------- |
| POST   | `/api/v1/complaints`      | 201     | 403 insufficient permissions · 404 property/resident/member not found · 409 ownership · 422 |
| GET    | `/api/v1/complaints`      | 200     | 403 insufficient permissions · 404 resident profile not found · 422 missing/invalid query   |
| GET    | `/api/v1/complaints/{id}` | 200     | 403 insufficient permissions · 404 complaint not found                                      |
| PATCH  | `/api/v1/complaints/{id}` | 200     | 403 insufficient permissions · 404 complaint/member not found · 409 lifecycle · 422         |

```json
// Create (log an issue on a resident's behalf)
POST /api/v1/complaints
Authorization: Bearer <access token>
{ "organization_id": "…", "property_id": "…", "resident_profile_id": "…", "title": "Tap leaking", "description": "The bathroom tap drips constantly.", "category": "PLUMBING" }
// Response 201
{ "id": "…", "organization_id": "…", "property_id": "…", "resident_profile_id": "…", "title": "Tap leaking", "description": "The bathroom tap drips constantly.", "category": "PLUMBING", "priority": "MEDIUM", "status": "OPEN", "assigned_to_member_id": null, "resolved_at": null, "created_at": "…", "updated_at": "…" }
```

```json
// Update (triage) — one step forward, and assign a handler
PATCH /api/v1/complaints/{id}
Authorization: Bearer <access token>
{ "status": "IN_PROGRESS", "priority": "HIGH", "assigned_to_member_id": "…", "title": "  Tap leaking badly  " }
// Response 200
{ "id": "…", "…": "…", "title": "Tap leaking badly", "status": "IN_PROGRESS", "priority": "HIGH", "assigned_to_member_id": "…", "resolved_at": null }
```

```json
// List (any member); optional status / priority / resident_profile_id narrow the result
GET /api/v1/complaints?organization_id=…&status=OPEN
Authorization: Bearer <access token>
// Response 200
[ { "id": "…", "property_id": "…", "resident_profile_id": "…", "category": "PLUMBING", "status": "OPEN", "priority": "MEDIUM", "…": "…" } ]
```

### Complaint Comment API

The discussion thread hanging off a complaint. Comments are **immutable**: POST and GET only, no edit, no delete, no `updated_at`. Authorization is inherited rather than reimplemented — `ComplaintCommentService` calls `ComplaintService.get_complaint` first, so a comment can never be read or written against a complaint the caller could not already reach, and there is no second role check to drift out of sync. Posting and reading are the same permission set (every org member), and `user_id` always comes from the authenticated caller, never the body.

| Role        | Read | Write |
| ----------- | ---- | ----- |
| OWNER       | Yes  | Yes   |
| MANAGER     | Yes  | Yes   |
| STAFF       | Yes  | Yes   |
| SUPER_ADMIN | Yes  | Yes   |

- **Endpoints** — `GET /api/v1/complaints/{complaint_id}/comments` (200), `POST /api/v1/complaints/{complaint_id}/comments` (201) (`app/api/v1/routes/complaints.py`). Kept off `ComplaintRead`, so reading a complaint does not pull the thread.
- **`body` on the wire, `comment` in the column** — the API field is `body` in both directions; `ComplaintCommentRead` maps it from `comment` so the column name never leaks. Bounded at 2000 chars, stripped, all-whitespace rejected, `extra="forbid"`.
- **Ordering** — `created_at ASC` (conversation order), unpaginated.
- **Org scope** — there is no `organization_id` to filter on, so every read is scoped by complaint id, and the service resolves and authorizes the parent complaint first. No "list all comments" method exists, so there is no unscoped read path.
- **`is_internal` is stored but not filtered (yet)** — the flag is persisted, validated, returned, and tested, but nothing hides internal notes from a reader. Every caller who can reach this endpoint is a staff-side role, and `OrganizationRoleEnum` has no `TENANT` member, so a visibility branch would be unreachable and untestable today. **This is the one behaviour to revisit when tenant-facing complaint access lands** — internal notes must then be invisible to residents. The filter is a `.where()` on `list_for_complaint`.
- **Errors** — 401 unauthenticated/inactive · 403 `insufficient permissions` (caller is not a member of the complaint's organization) · 404 `complaint not found` · 422 validation (blank or >2000 char `body`, or any `complaint_id` / `user_id` / `updated_at` in the body).

| Method | Path                                         | Success | Errors                                                       |
| ------ | -------------------------------------------- | ------- | ------------------------------------------------------------ |
| GET    | `/api/v1/complaints/{complaint_id}/comments` | 200     | 403 insufficient permissions · 404 complaint not found       |
| POST   | `/api/v1/complaints/{complaint_id}/comments` | 201     | 403 insufficient permissions · 404 complaint not found · 422 |

```json
// Post a note on the thread
POST /api/v1/complaints/{id}/comments
Authorization: Bearer <access token>
{ "body": "Plumber booked for Thursday.", "is_internal": false }
// Response 201
{ "id": "…", "complaint_id": "…", "user_id": "…", "body": "Plumber booked for Thursday.", "is_internal": false, "created_at": "…" }
```

```json
// Read the thread (oldest first)
GET /api/v1/complaints/{id}/comments
Authorization: Bearer <access token>
// Response 200
[ { "id": "…", "complaint_id": "…", "user_id": "…", "body": "Plumber booked for Thursday.", "is_internal": false, "created_at": "…" } ]
```

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
├── api/v1/     versioned HTTP routes (health, auth/register, auth/me, auth/onboard, properties, buildings, floors, rooms, beds, resident profiles, tenant stays, complaints, complaint comments)
├── core/       config (pydantic-settings), logging, lifespan, exceptions, security (JWT verification + JWKS, password hashing)
├── db/         declarative Base (naming conventions), engine/session, mixins, health
├── models/     SQLAlchemy models (users, orgs, memberships, properties, buildings, floors, rooms, beds, resident profiles, tenant stays, complaints, complaint comments, enums)
├── repositories/  data access (users, orgs, memberships, properties, buildings, floors, rooms, beds, resident profiles, tenant stays, complaints, complaint comments)
├── schemas/    Pydantic request/response models (users, auth, orgs, properties, buildings, building_api, floors, floor_api, rooms, room_api, beds, bed_api, resident profiles, resident_profile_api, tenant stays, tenant_stay_api, complaints, complaint_api, complaint comments)
├── services/   business logic (auth service — registration; onboarding service; property service; building service; floor service; room service; bed service; resident profile service; tenant stay service; complaint service; complaint comment service)
└── main.py     create_application() factory, exposes `app`
alembic/        migration structure (schema change ships with a migration)
tests/          pytest suite
```

## Conventions

- All imports are absolute from the `app` package: `from app.core.config import settings`.
- Every request/response is validated by a Pydantic model.
- Config comes from environment variables only; no secrets in code or commits.
- The app is built by `create_application()`; routers, exception handlers, logging, and lifespan are registered there, keeping `main.py` small.
