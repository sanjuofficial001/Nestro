# Nestro

PG management and resident experience platform.

Nestro manages paying-guest (PG) operations end to end — rent collection, tenants, complaints, notices, and food — for both residents and property owners.

## Apps

| Component           | Path             | Description                                    |
| ------------------- | ---------------- | ---------------------------------------------- |
| Resident Mobile App | `apps/mobile`    | Day-to-day experience for PG residents         |
| Owner Dashboard     | `apps/dashboard` | Operational console for PG owners and managers |
| FastAPI Backend     | `backend`        | REST API and business logic                    |
| AI Assistant        | `backend`        | Conversational layer over the platform         |

## Goals

- Manage PG operations
- Rent collection
- Tenant management
- Complaints
- Notices
- Food management

## Architecture Summary

Monorepo split by concern. Client apps talk to the FastAPI backend; the AI assistant sits on top of the same backend and data layer.

- **Resident Mobile App** (`apps/mobile`) — resident-facing: rent, complaints, notices, food.
- **Owner Dashboard** (`apps/dashboard`) — owner/manager-facing: tenants, collections, operations.
- **Backend** (`backend`) — FastAPI REST service with the AI assistant layered on it.
- **Infrastructure** (`infrastructure`) — infrastructure-as-code and deployment definitions.
- **Continuous integration** (`.github`) — GitHub Actions workflows for build, test, and deployment.

```
+------------------+     +------------------+
|  Mobile App       |     |  Owner Dashboard |
|  apps/mobile      |     |  apps/dashboard  |
+--------+---------+     +--------+---------+
         |                        |
         +----------+-------------+
                    |
            +-------v--------+
            |   FastAPI API   |
            |    backend/     |
            +-------+--------+
                    |
        +-----------+-----------+
        |  Data + AI Assistant  |
        +-----------------------+
```

## Setup Instructions

Prerequisites:

- Node.js (mobile and dashboard apps)
- Python 3.x (backend)
- A package manager for each workspace (`npm`/`pnpm`/`yarn`, `pip`/`poetry`)

There is no top-level build yet. To run each component, see its own README:

- `apps/mobile/README.md`
- `apps/dashboard/README.md`
- `backend/README.md`

## Development Workflow

- One repository, multiple workspaces — each app or service is self-contained under its folder.
- Feature work happens on a branch, then lands via a pull request.
- CI pipelines in `.github/workflows` run build and test checks on each PR before merge.
- Component-specific commands (lint, test, run) are documented in each workspace README.

## Deployment Overview

- Environment provisioning and service definitions live in `infrastructure/`.
- Delivery is automated through CI/CD in `.github/workflows`.
- The FastAPI backend is deployed as a service; the mobile app and dashboard ship as client artifacts.
- Provider- and environment-specific details are kept in the infrastructure workspace.

## Future

- Marketplace
- Roommate matching
- Hotel support
- Apartment support
