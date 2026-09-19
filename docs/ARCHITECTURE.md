# Nestro Architecture

## Technology Stack

| Layer          | Technology                     | Notes                                                |
| -------------- | ------------------------------ | ---------------------------------------------------- |
| Mobile         | Expo React Native + TypeScript | Resident-facing app (`apps/mobile`)                  |
| Dashboard      | Next.js + TypeScript           | Owner/manager-facing web app (`apps/dashboard`)      |
| Backend        | FastAPI + Python               | REST API and business logic (`backend`)              |
| Database       | Supabase PostgreSQL            | Managed exclusively through the backend              |
| Storage        | Supabase Storage               | User-uploaded files and media                        |
| Authentication | Supabase Auth                  | Auth tokens issued and validated by Supabase         |
| Payments       | Razorpay                       | Rent collection and payments                         |
| Notifications  | Firebase Cloud Messaging       | Push notifications to mobile                         |
| AI             | OpenAI API                     | AI assistant layered on the backend                  |
| Deployment     | Vercel + Railway + Supabase    | Dashboard (Vercel), backend (Railway), DB (Supabase) |

## System Architecture

Clients communicate only with the FastAPI backend. The backend is the single owner of business logic and the only client of the database. Auth lives with Supabase; the backend validates tokens on every request. External services (Razorpay, FCM, OpenAI) are reached only through the backend.

The platform is multi-tenant. `organizations` is the tenant boundary: every business row carries `organization_id`, and the backend scopes every query with `WHERE organization_id = $org`. Organization-level identity and roles come from `organization_members` (owner / manager / staff); a user without a membership row sees nothing in that org. `SUPER_ADMIN` is the only platform-wide role. All business rules and isolation live in the backend, never in the UI.

```mermaid
flowchart TB
    subgraph Clients
        Mobile["Mobile App<br/>Expo React Native / TypeScript"]
        Dashboard["Owner Dashboard<br/>Next.js / TypeScript"]
    end

    Backend["FastAPI Backend<br/>(backend/)"]
    AI["AI Assistant<br/>(backend layer)"]

    subgraph Supabase
        DB[("PostgreSQL")]
        Storage["Storage"]
        Auth["Auth"]
    end

    Razorpay["Razorpay"]
    FCM["Firebase Cloud Messaging"]
    OpenAI["OpenAI API"]

    Mobile <-->|HTTPS| Backend
    Dashboard <-->|HTTPS| Backend
    Backend <-->|validated requests| Auth
    Backend <-->|reads/writes| DB
    Backend <-->|files| Storage
    Backend <-->|payments| Razorpay
    Backend <-->|push| FCM
    Mobile <-->|push tokens| FCM
    Backend <-->|prompts/responses| OpenAI

    Backend --- AI
```

## Data Flow

All data access routes through the backend: frontends never hold database credentials or issue SQL. Requests come in as Pydantic-validated payloads, business logic runs in the backend, and results are returned as typed responses. Media goes to Supabase Storage via backend-managed signed URLs.

```mermaid
sequenceDiagram
    participant C as Client (Mobile / Dashboard)
    participant B as FastAPI Backend
    participant S as Supabase (DB / Storage)
    participant P as Razorpay

    C->>B: HTTPS request (JSON)
    B->>B: Authenticate + validate (Pydantic)
    B->>S: Query / write with service role
    S-->>B: Result set
    alt Payment flow
        B->>P: Create order
        P-->>C: Payment gateway (redirect/PG SDK)
        P-->>B: Webhook (server-to-server)
        B->>S: Update payment status
    end
    B-->>C: Typed response
```

## Authentication Flow

Supabase Auth issues a JWT. The mobile app and dashboard obtain the token from Supabase Auth and attach it to every backend request. The backend verifies each token against Supabase and maps it to the requesting user's organization-membership roles (owner / manager / staff / resident) via a middleware; route-level guards then enforce org-scoped authorization per endpoint. A user with no membership row in an organization sees nothing in it.

```mermaid
sequenceDiagram
    participant U as User
    participant A as Client App
    participant SA as Supabase Auth
    participant B as FastAPI Backend

    U->>A: Sign in (email / social)
    A->>SA: POST /auth (credentials)
    SA-->>A: Session + JWT access token
    A->>B: API request + Authorization: Bearer <JWT>
    B->>SA: Verify token (JWKS / introspect)
    SA-->>B: Valid + claims (sub, role)
    B->>B: Enforce org role (owner / manager / staff / resident)
    B-->>A: Authorized response
```

## API Communication

The backend exposes a documented REST API. Every request and response is validated by Pydantic. Frontends use generated/typed clients. The API contract (schemas, endpoints) is the boundary between the backend and its consumers, and is kept current in the backend docs (`backend/README.md`).

```mermaid
flowchart LR
    subgraph Contract
        OpenAPI["OpenAPI / docs"]
        Pydantic["Pydantic models<br/>request + response"]
    end

    FE["Frontend (typed client)"] -->|JSON + Bearer JWT| EP["FastAPI endpoints"]
    EP --> M["Middleware: auth + validation"]
    M --> S["Services: business logic"]
    S --> SD["Supabase client"]
    SD --> DB[("PostgreSQL")]

    OpenAPI --> EP
    Pydantic --> EP
```

## Security Model

```mermaid
flowchart TB
    Client["Client"] -->|"TLS + Bearer JWT"| Gateway["Backend edge: verify JWT"]
    Gateway -->|"role: org-scoped (owner / manager / staff / resident)"| AuthZ["Route-level authorization<br/>org-scoped"]
    AuthZ --> Logic["Business logic"]
    Logic -->|"service role (server-only)"| Supabase

    Key["No DB credentials in frontends"]
    Secret["Secrets only in backend env / infra"]
    Valid["All inputs validated by Pydantic"]
    Doc["APIs documented before ship"]
    Test["Features ship with tests"]

    Logic --- Key
    Logic --- Secret
    Logic --- Valid
    Logic --- Doc
    Logic --- Test
```

Security principles:

- **Tenant isolation** — `organizations` is the tenant boundary; a user without an `organization_members` row in an org sees nothing in it.
- **Transport** — all client↔backend traffic over HTTPS with TLS.
- **Authentication** — Supabase Auth JWT verified by the backend on every request.
- **Authorization** — role-based guards on endpoints; business rules never live in the UI.
- **Credential boundaries** — frontends never access the database; only the backend holds database access.
- **Secret management** — keys and tokens exist only in backend environment variables and infrastructure config; never in code, config, or commits.
- **Payment integrity** — Razorpay order status is confirmed server-side via webhooks, never trusted from the client.
- **Validation** — every request and response passes through Pydantic models.
- **AI boundary** — the AI assistant calls the backend's own data services under the same auth and role rules; it never receives database access.
