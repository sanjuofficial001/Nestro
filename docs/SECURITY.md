# Nestro Security Specification

Security is implemented in the FastAPI backend using OWASP guidance (OWASP Top 10, OWASP API Security Top 10, and ASVS-informed controls). Every item below is enforced server-side; frontends only present capabilities already backed by backend rules.

## 1. JWT Authentication

**Model:** Supabase Auth issues JWTs. The backend is stateless — no session store — and validates the token on every request before any business logic runs.

**FastAPI implementation**

- A single `HTTPBearer` security scheme is registered once (`security = HTTPBearer(auto_error=False)`).
- A `get_current_user` dependency parses the token, verifies signature against Supabase JWKS, checks `exp`, `aud`, and `iss`, and resolves the `sub` to a `User` row.
- Endpoints declare `user: User = Depends(get_current_user)`; rate-limited and logged centrally.
- Tokens are never reflected in responses, logs, or error messages.

```python
from fastapi import Depends, FastAPI, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer(auto_error=False)

app = FastAPI()
```

- JWT decoding uses `PyJWT` with `algorithms=["RS256"]`, the only algorithm Supabase signs with — `none` and HS-family algorithms are never accepted.
- `exp`, `aud`, and `iss` are validated; a token failing any check yields `401`, identical for expired and malformed tokens so the client cannot distinguish causes to probe.
- Failed-auth responses are uniform minimal bodies (`{"detail": "..."}`) with no stack traces (ASVS V3: error handling leaks nothing).

See `AUTHENTICATION_SPEC.md` for the full flow and role model.

## 2. Role-Based Access Control (RBAC)

**Model:** Roles — `SUPER_ADMIN`, `PG_OWNER`, `MANAGER`, `STAFF`, `TENANT` — and per-PG membership are the authority. The JWT identity is a fast path, never the authority.

**FastAPI implementation**

- Role comes from the authenticated `User` (re-read from DB for sensitive operations), never from client-supplied claims.
- One reusable dependency per permission, composed per route:

```python
def require_owner(user: User = Depends(get_current_user)) -> User:
    if user.role not in {"SUPER_ADMIN", "PG_OWNER"}:
        raise HTTPException(status_code=403, detail="Forbidden")
    return user
```

- PG-scoped data uses a `pg_scope` dependency that verifies the user is a member of the target PG before the query runs:

```python
def require_pg_scope(
    pg_id: UUID, user: User = Depends(get_current_user)
) -> User:
    if not is_member(pg_id, user):   # DB check, not JWT claim
        raise HTTPException(status_code=403, detail="Forbidden")
    return user
```

- Every tenant/PG-sensitive query filters by membership; there are no unscoped read paths.
- Permission dependencies are pure functions of `(user, resource)`, composes with `fastapi.Depends`, and reads the DB as the source of truth.

See `AUTHENTICATION_SPEC.md` → _Authorization Rules_ and _Role Permissions_.

## 3. Input Validation

**Every** request body, query parameter, and path parameter is validated by Pydantic before it reaches business logic.

**FastAPI implementation**

- All schemas use strict `BaseModel` with explicit types.
- Reject unexpected fields with `model_config = ConfigDict(extra="forbid")` so clients cannot smuggle keys the contract does not declare.
- Tighten types: `conint`, `constr`, `EmailStr`, `PhoneNumber`, `str` with `min_length`/`max_length`.
- Query parameters that accept dates use `datetime`; anything unbounded is rejected.

```python
from pydantic import BaseModel, ConfigDict, Field

class CreateComplaint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str = Field(min_length=1, max_length=50)
    description: str = Field(min_length=1, max_length=2000)
    photo_url: HttpUrl | None = None
```

**Additional rules**

- All string fields strip whitespace and enforce length bounds — mitigates oversized payloads and silent `\0`/leading-space injection.
- SQL access uses parameterized queries via the Supabase client / SQLAlchemy; string concatenation into SQL is banned outright (OWASP A03 — Injection).
- Rich text in notices/complaints is stored and rendered as plain text or through a sanitizer on the client; the backend accepts no arbitrary HTML at this phase.

## 4. Rate Limiting

**Model:** Per-client throttling on authentication and abuse-prone endpoints; business endpoints rate limited per user.

**FastAPI implementation**

- `slowapi` wraps the app (`limiter = Limiter(key_func=get_remote_address)`) and applies per-endpoint limits defined in `backend/app/core/limits.py`.
- Auth endpoints are keyed by IP **and** identifier (email/phone) to delay enumeration while still hitting shared mobile networks.
- Returns `429` with `Retry-After`; enforced before the handler and before any DB work.

| Endpoint/group         | Window               | Budget |
| ---------------------- | -------------------- | ------ |
| Login / OTP request    | 15 min, per identity | 5      |
| OTP verify             | 15 min, per identity | 10     |
| Register               | 1 hour, per IP       | 10     |
| Reset password request | 1 hour, per identity | 3      |
| Complaint create       | 1 hour, per user     | 20     |
| General API            | 1 min, per user      | 120    |

# ponytail: full per-tenant keyed buckets; slowapi's remote-address key is the v1 carve-out, upgrade when multi-IP client behavior shows up.

## 5. Audit Logging

**Model:** Every sensitive or state-changing action is recorded with identity, action, resource, and outcome. Logs are append-only and go to a dedicated destination, never relative to the DB rows they describe.

**FastAPI implementation**

- A single `log_audit` helper writes a structured line: `actor_id`, `action`, `resource_type`, `resource_id`, `ip`, `outcome`, `ts` (JSON lines → stdout / centralized collector).
- Called from dependencies and at the end of mutating handlers; never logs bodies, tokens, or secrets.
- Audit events cover every mutating phase-1 feature: rent plan/invoice changes, payments, complaint status changes, notices, PG/tenant/room/bed mutations, role grants, and login/refresh/revoke.

```python
from logging import getLogger

audit = getLogger("nestro.audit")

def log_audit(*, actor: str, action: str, resource: str,
              outcome: str, ip: str | None) -> None:
    audit.info({"actor": actor, "action": action,
                "resource": resource, "outcome": outcome,
                "ip": ip})
```

**Rules**

- `PASSWORD`, `token`, `authorization` headers never logged.
- Audit writes are fire-and-forget but failure is non-blocking via a dedicated logger handler; no end-to-end path depends on the log write.
- Logs are retained per deployment policy in `infrastructure/` and are tamper-evident in production (centralized, append-only).

## 6. Password Policy

Enforced at the Supabase Auth edge plus the backend's Pydantic layer.

**FastAPI implementation**

- Backend schema enforces minimums before the request reaches Supabase:

| Rule                  | Value                                            |
| --------------------- | ------------------------------------------------ |
| Minimum length        | 8 chars                                          |
| Require upper + lower | yes                                              |
| Require digit         | yes                                              |
| Require symbol        | yes (OWASP says optional; we accept both)        |
| Rotation / expiry     | none — superseded by long passwords + MFA/OTP    |
| Storage               | never in backend; Supabase hashes (bcrypt/argon) |

- Passwords travel only to Supabase Auth over TLS; the backend never receives or stores a plaintext password.
- Reset flows use Supabase recovery links; force re-authentication (step-up) before role or payment-critical actions.

```python
from pydantic import BaseModel, Field

PASSWORD_RE = r"(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\w]).{8,}"

class SignupPayload(BaseModel):
    email: EmailStr
    password: str = Field(pattern=PASSWORD_RE)
```

## 7. File Upload Validation

**Model:** Uploads go to Supabase Storage and are validated before and after transfer; no arbitrary executable content is ever stored where it could be served as code.

**FastAPI implementation**

- Multipart endpoints accept `UploadFile`, validate on the stream (not the filename), and never trust client-provided content type or extension.
- Use `python-multipart`; enforce **allow-listed** extensions and MIME via real sniffing of the first bytes.

```python
from fastapi import UploadFile

ALLOWED = {"image/jpeg", "image/png", "image/webp"}

async def validate_upload(file: UploadFile) -> None:
    if file.content_type not in ALLOWED:
        raise HTTPException(status_code=415,
                            detail="Unsupported media type")
    head = await file.read(32)
    if head[:3] != b"\xff\xd8\xff" and not (
        head[:8] == b"\x89PNG\r\n\x1a\n"
        or head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    ):
        raise HTTPException(status_code=415,
                            detail="Content not an allowed image")
    await file.seek(0)
```

**Additional rules**

- Per-user and per-file size limits (e.g. 5 MB upload) enforced at the endpoint and, when available, at the object store.
- Uploaded names are replaced with server-generated opaque keys (`<uuid>.<ext>`); user content is stored in private Supabase Storage buckets and served only via backend-generated signed URLs. No direct public CDN exposure of user files.
- Object content-type stored as the validated MIME, not the user-claimed one, to prevent HTML/script being served as `text/html`.
- SVG and executable extensions are excluded from the allow-list; display of user HTML is deferred to a sanitizer phase.

## 8. Secure Secret Management

**Model:** Secrets never reach code, config, or commits. They exist only in backend environment variables and are injected by the deployment platform.

**FastAPI implementation**

- `.env` files are git-ignored; committed sample files use placeholders only (`.env.example`).
- Runtime loads environment variables with a typed settings object (`pydantic-settings`); missing required settings fail fast at boot rather than at first use.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    razorpay_key_id: str
    razorpay_key_secret: str
    openai_api_key: str
    fcm_server_key: str

    model_config = {"env_file": ".env", "extra": "forbid"}

settings = Settings()
```

**Rules**

- Service Role key, Razorpay key, OpenAI key, and FCM server key exist only server-side.
- Never expose `SUPABASE_SERVICE_KEY` (or any secret) to frontends; the dashboard/mobile can never act as the DB client.
- No secrets in Dockerfiles, CI config, or workflow files; in CI they come from GitHub Actions encrypted secrets.
- Key rotation policy documented in `infrastructure/`; a leaked key is rotated and revoked immediately, never "cleaned up later".
- Files containing hard-coded secrets fail a CI secret-scan step (gitleaks) in `.github/workflows/security.yml`.

## 9. Tenant Isolation

**Boundary:** `organizations` is the tenant boundary. Every business table carries `organization_id`; `WHERE organization_id = $org` is the universal isolation filter, applied by the backend on every org-scoped query. A user without an `organization_members` row in an organization sees nothing in it; there are no unscoped read paths. `SUPER_ADMIN` is the only platform-wide role. See `DATABASE.md` _Conventions_ and the multi-tenant notes in `ARCHITECTURE.md`.

- Full-DB access belongs only to the backend; frontends never hold database credentials (see §2).
- All tenant-sensitive queries are scoped by membership in the backend — JWT claims are a fast path, never the authority.
- No two organizations share data; rows are never merged across the boundary.

## Threat Model Summary (OWASP Top 10 alignment)

| OWASP A (2021)                   | Control in Nestro                                   | Section |
| -------------------------------- | --------------------------------------------------- | ------- |
| A01 Access control               | Server-side RBAC + PG-membership scoping            | 2       |
| A02 Crypto failures              | TLS everywhere; no custom crypto                    | —       |
| A03 Injection                    | Parameterized SQL/Pydantic-typed inputs             | 3       |
| A04 Insecure design              | Least privilege; backend-only DB access             | 2, 8    |
| A05 Security misconfig           | Pydantic-settings fail-fast; no debug               | 8       |
| A06 Vulnerable components        | Pinned deps + CI scorecard/scan                     | 8, CI   |
| A07 Auth failures                | Supabase Auth + JWT validation                      | 1       |
| A08 Integrity (signed/soft-miss) | Razorpay webhooks verified server-side              | 1       |
| A09 Logging/monitoring           | Structured audit log; rate limiting                 | 4, 5    |
| A10 SSRF                         | Outbound calls allow-listed (Razorpay, OpenAI, FCM) | 8       |
