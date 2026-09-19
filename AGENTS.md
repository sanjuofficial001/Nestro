# AGENTS.md

Guidance for AI agents and developers working in the Nestro repository.

## Project

Nestro is a PG (paying guest) management and resident experience platform.

- **Mobile app** — Expo React Native (`apps/mobile`)
- **Dashboard** — Next.js (`apps/dashboard`)
- **Backend** — FastAPI (`backend`)
- **Database** — Supabase PostgreSQL

## Architecture

The platform is a monorepo split by concern. Client apps never touch the database directly — all access goes through the FastAPI backend.

```
+------------------+     +------------------+
|  Mobile App       |     |  Owner Dashboard |
|  Expo RN          |     |  Next.js         |
+--------+---------+     +--------+---------+
         |                        |
         +----------+-------------+
                    |
            +-------v--------+
            |   FastAPI API   |
            |      Pydantic   |
            +-------+--------+
                    |
            +-------v--------+
            | Supabase PgSQL  |
            +-----------------+
```

- **Mobile app** (`apps/mobile`) — Expo React Native, resident-facing.
- **Dashboard** (`apps/dashboard`) — Next.js, owner/manager-facing.
- **Backend** (`backend`) — FastAPI REST service; the single access point for data.
- **Database** — Supabase PostgreSQL; managed exclusively through the backend.
- **AI Assistant** — layered on the backend; follows the same data access rules.

## Non-Negotiable Rules

### Code style

- **TypeScript strict mode** — required in all frontends. No `any`, no untyped escapes.
- **Python type hints** — required on all backend functions, including parameters and return types.
- **No business logic in UI** — components render and dispatch; business rules live in the backend.
- **Keep code modular** — small, focused modules over large monoliths.
- **Prefer composition over inheritance** — compose behavior; avoid deep inheritance chains.
- **Never modify unrelated files** — a change touches only the files it is about.

### Backend & data

- **API validation through Pydantic** — every request and response is validated by Pydantic models.
- **Database migrations mandatory** — schema changes require a migration. Never mutate the live schema ad hoc.
- **Never access the database directly from the frontend** — the FastAPI backend is the only database client.
- **Never expose secrets** — no keys, tokens, or credentials in code, configs, or commits.

### Deliverables

- **All APIs documented** — every endpoint documented (OpenAPI/descriptions) before it ships.
- **Every feature requires tests** — new features ship with tests covering their behavior.

## Architecture Principles

- **Follow clean architecture** — separate concerns: presentation, application logic, domain, and infrastructure. Dependencies point inward; the UI depends on interfaces, not database implementations.
- **Build for long-term scale** — structure code so it scales in size and traffic without rework: modular boundaries, typed contracts, documented APIs, and test coverage from day one.

## Development Workflow

1. Work on a branch; land changes via pull request.
2. CI (`.github/workflows`) runs build, lint, type checks, and tests on every PR.
3. Run component-specific commands from the workspace READMEs (`apps/mobile/README.md`, `apps/dashboard/README.md`, `backend/README.md`).
4. Schema or API changes update the corresponding migrations and API docs in the same change; never split a feature from its tests or its migration.
