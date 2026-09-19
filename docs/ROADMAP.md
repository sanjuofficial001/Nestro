# Nestro Roadmap

Sequenced build plan from documentation through multi-vertical expansionholidays. Baseline: **one full-time engineer**; weeks are relative to kickoff. Everything below is a timeline from the existing specs (`ARCHITECTURE.md`, `PRODUCT_SPEC.md`, `DATABASE.md`, `AUTHENTICATION_SPEC.md`, `API_SPEC.md`, `SECURITY.md`); none of them are invented here.

## Phase Guide

| Phase | Theme                 | Window   | Key output                   | Exit document                        |
| ----- | --------------------- | -------- | ---------------------------- | ------------------------------------ |
| 0     | Documentation & setup | Wk 1-4   | Closed spec + infra debt, CI | Specs + `.github`, `infrastructure/` |
| 1     | Backend foundation    | Wk 5-14  | Working read/write API       | `API_SPEC.md` implemented, tests     |
| 2     | Owner dashboard       | Wk 15-22 | Management console           | Dashboard feature set                |
| 3     | Resident mobile app   | Wk 23-32 | Resident-facing app          | Mobile feature set                   |
| 4     | AI assistant          | Wk 33-40 | Assistant layered on backend | `/assistant/chat` in API_SPEC        |
| 5     | PG discovery          | Wk 41-46 | Browse + enquiry             | Discovery feature set                |
| 6     | Marketplace           | Wk 47-54 | Products, shop, orders       | Marketplace feature set              |
| 7     | Hotel & apartment     | Wk 55-64 | Second vertical on same core | Horizontal expansion                 |

## Cross-Cutting Conventions (apply to every phase)

- Ship **vertical slices** per milestone — a working, testable path end to end — never a horizontal layer ("all the models", then "all the endpoints").
- Every schema change ships with its migration in the same change. Never mutate live schema ad hoc (AGENTS.md).
- Every API ships documented; every feature ships with tests (AGENTS.md).
- Never expose secrets; the backend is the only database client (SECURITY.md).
- Metrics below are **report-only** on a phase's dashboards except where a row is marked "gate" — gates block entry into the next phase(Checks A in Phase 1).
- Money and timestamps follow `API_SPEC.md` conventions; never float money.

## Phase 0 — Documentation & Setup

**Goal:** make the repo buildable, testable, and documented from day one; close spec and infra debt before any feature work.

**Scope:** freeze the Phase 1 contract surface (the 14 API groups + 18-entity schema in `DATABASE.md`), scaffold the three workspaces, CI/CD, environments, and the `ponytail`-reviewed baseline. No product features (that is Phase 1+).

**Timeline (4 weeks):**

| Task                       | Wk  | Exit state                                                         | depends on |
| -------------------------- | --- | ------------------------------------------------------------------ | ---------- |
| Repo + workspace scaffold  | 1   | `apps/*`, `backend/` runnable; TS strict + mypy in place           | --         |
| Env/secret/CI baseline     | 1-2 | `.github` CI green; secrets only via env, gitleaks gate            | 1          |
| Migration v0 + seed writer | 2   | `backend` migrations + seed fixtures match DATABASE.md             | 1          |
| Contract freeze            | 3   | `API_SPEC` route/field list locked; Pydantic skeleton generated    | 2          |
| Security review pass       | 4   | SECURITY.md controls wired into skeleton (deps, rate-limit, audit) | 2          |

**Milestones (gates out of Phase 0):**

1. Fresh clone → `backend` boots, `/health` returns 200, one seeded PG has 1 building / 1 floor / 1 room / 1 bed.
2. Fresh clone → `apps/dashboard` dev server renders a page that talks to backend `/api/v1/auth/me` and gets a typed `401/403` on bad/missing token.
3. CI runs build, lint (strict TS + mypy), and at least one `pytest` on every push; secrets scanned by gitleaks.
4. `docs/DATABASE.md` matches the v0 migration diff-for-diff (no drift).

**Risks**

| Risk                       | L   | I   | Mitigation                                                  |
| -------------------------- | --- | --- | ----------------------------------------------------------- |
| Spec ∥ code drift          | H   | H   | v0 migration generated from DATABASE.md; diff-checked in CI |
| Secrets leak in scaffold   | L   | H   | env-only config, gitleaks gate, no `.env` committed         |
| CI flakiness eats days     | M   | M   | pinned deps + cache; keep CI under ~10 min                  |
| Workspaces half-scaffolded | M   | M   | Phase 0 exits only when all three boot                      |

**Success metrics (report-only until Phase 1 gates):** CI time median, migrations green on clean clone, secrets-canaries count, doc↔migration drift = 0.

## Phase 1 — Backend Foundation

**Goal:** a working, secure read/write API for every Phase-1 product concept — the entire `API_SPEC.md` surface minus AI. This is the trust base; almost every later feature sits on it.

**Scope:** all 14 API groups except the AI assistant layer, plus tenants/rent/payments/complaints/notices/notifications integrated. Includes in-memory fast paths (`scoped_ids` cache) and full audit coverage (SECURITY.md §1-6).

**Timeline (10 weeks):**

| Milestone                                | Wk    | Exit state (thin slices)                                             |
| ---------------------------------------- | ----- | -------------------------------------------------------------------- |
| Auth + users + membership                | 5-6   | onboard/me/users wired; RBAC deps in; 401/403/scope tests            |
| PG → building → floor → room → bed       | 6-8   | nested create/list, capacity & status rules, uniqueness, soft-delete |
| Tenants + stay lifecycle                 | 8-9   | move-in/out/move atomic; bed/tenant invariants; history              |
| Rent plans + invoices + Razorpay         | 9-11  | plans, invoice generation, settle webhook path, cash mark-paid       |
| Complaints, notices, notifications (FCM) | 11-13 | full lifecycle + push; audit on all state changes                    |
| Hardening + audit + rate-limit           | 12-14 | SECURITY.md §1-8 enforced; load smoke; contract freeze               |

**Gates (enter Phase 2 only when ALL green — these are the exception to report-only):**

1. 100% of mutating endpoints covered by tests asserting role gating (401/403/404-scope).
2. Payment confirmation can only come from a server-verified Razorpay webhook; no client path flips `payments.status` (`API_SPEC` note 46).
3. Rate-limiting active (SECURITY.md §4) and audit log non-empty on every audited action (SECURITY.md §5).
4. Frontends have zero DB creds anywhere in the monorepo (grep gate in CI).

**Risks**

| Risk                                       | L   | I   | Mitigation                                                            |
| ------------------------------------------ | --- | --- | --------------------------------------------------------------------- |
| Scope creep into AI/payments visuals       | M   | H   | Phase 1 is defined by the 14 API groups; nothing else                 |
| Webhook/signature bugs break payments      | M   | H   | server-side verify, invoice stays `issued` on failure                 |
| JWT cache vs DB drift grants/denies        | H   | M   | membership re-read from DB (SECURITY.md §1); scoped_ids is cache-only |
| Unique-index over-constraint churns schema | M   | M   | stay/bed invariants set once in DATABASE.md, not per-PG patches       |

**Success metrics:** P95 p95 API < 300ms on seeded data; payment settle 100% reconcile; rent invoice generation 0 drift (days), complaint `resolved` TAT median; crash-free sessions > 99.5%; audit coverage 100% of state-changing endpoints.

## Phase 2 — Owner Dashboard

**Goal:** the management console where owners/managers run PGs — scoped, typed, read-mostly-cached, every action hitting the Phase 1 API.

**Scope:** Next.js dashboard feature set (PG list/detail, buildings/floors/rooms/beds, tenants + stays, rent/invoices/payments with Razorpay redirect, complaints triage, notices editor, notifications preferences). No business logic in UI (AGENTS.md).

**Timeline (8 weeks):**

| Milestone                          | Wk    | Exit state                                                         |
| ---------------------------------- | ----- | ------------------------------------------------------------------ |
| Auth shell + role hydration        | 15    | `/auth/me` hydrate, route guards, minimal chrome                   |
| PG + physical tree CRUD            | 16-17 | buildings→floors→rooms→beds management screens                     |
| Tenants + stays                    | 18-19 | move-in/out/move flows, tenant profile, history                    |
| Rent + payments                    | 19-21 | plans/invoices list, Razorpay redirect, mark-paid, collection view |
| Complaints + notices + notif prefs | 22-23 | triage board, notice composer, snapshot toggles                    |
| Polish + dashboard-only AI peek    | 24    | oversight stats; empty-state/error/test pass                       |

**Milestones:** dashboard authenticated flow toggles a tenant bed `available→occupied` end-to-end (16); a manager marks a complaint resolved and tenant sees the notice (22).

**Risks**

| Risk                            | L   | I   | Mitigation                                                        |
| ------------------------------- | --- | --- | ----------------------------------------------------------------- |
| Reusing Next.js jams vs backend | M   | M   | typed client generated from API_SPEC; no hand-rolled fetch lean   |
| Payment UI misleads status      | M   | H   | status comes only from webhook; UI shows "pending until verified" |
| Empty-state pressure cuts scope | M   | M   | feature ownership per milestone; ship vertical slices             |

## Phase 3 — Resident Mobile App

**Goal:** the resident-facing Expo app — self-service for rent, complaints, notices, food, and notifications, with the AI assistant as the primary entry point to it all.

**Scope:** Expo React Native (TypeScript strict) feature set — register/OTP login/`auth/me` hydration, stay + rent + payments (Razorpay), complaints raise/track, notices, food plans/orders (Phase 2 integration), FCM notifications with per-category toggles, AI assistant chat, offline-cache of own tenant snapshot. No business logic in UI; no direct DB access (AGENTS.md).

**Timeline (10 weeks):**

| Milestone                            | Wk    | Exit state                                                                                 |
| ------------------------------------ | ----- | ------------------------------------------------------------------------------------------ |
| Auth shell + hydration + tabs        | 25    | OTP login, `/auth/me` hydration, guarded tab shell                                         |
| Stay + rent + payments               | 26-28 | own stay view, invoice list, Razorpay redirect + status from webhook, rent history         |
| Complaints + notices + notifications | 29-31 | raise/track complaint, notice list, FCM with category toggles, share/screenshot compliance |
| Food (order + plan)                  | 31-33 | menu list, order flow, active meal plan view                                               |
| AI assistant + onboarding polish     | 33-35 | chat UI, onboarding completion, empty/error/offline states                                 |

**Milestones:** a tenant completes a payment with the iOS/resident app and the dashboard shows `paid` via webhook within 30s (28); a resident raises a complaint and gets a push notification (31).

**Risks**

| Risk                                    | L   | I   | Mitigation                                                                                         |
| --------------------------------------- | --- | --- | -------------------------------------------------------------------------------------------------- |
| FCM deliverability varies by OEM        | M   | M   | webhooks? no — FCM via `notifications` + fallback inbox; tokens kept fresh by RLS-scoped keepalive |
| Payment redirect → webhook gap confuses | H   | M   | UI shows "pending until verified"; never trust client (SECURITY.md)                                |
| Offline cache drifts from truth         | M   | M   | cache is display-only; write path always server-backed                                             |

## Phase 4 — AI Assistant

**Goal:** a conversational layer on top of the Phase 1 backend — read-first, scope-bound, tool-calling assistant with careful write affordances. Ships after Phase 1-3 so users/code and the API it calls are real.

**Scope:** backend `/assistant/chat` (streamed), RAG over PG rules/notices/documents, tool calls into read endpoints with role scoping, memory per user with consent prompt, complaint/rent Q&A, notice drafting from owner intent. Guarded writes (clear intent + confirmation) for small state changes (e.g. mark complaint in-progress) — always through the same authorization checks.

**Timeline (8 weeks):**

| Milestone                          | Wk    | Exit state                                        |
| ---------------------------------- | ----- | ------------------------------------------------- |
| Streaming chat + auth + scoping    | 36    | `/assistant/chat` streams, 401/403, role scope    |
| RAG over notices/rules + citations | 37-39 | retrieval over PG docs; every answer cites source |
| Tool calls + read-path tooling     | 39-41 | tools call read endpoints with membership gates   |
| Guarded writes + consent memory    | 41-43 | write actions confirm; memory opt-in gated        |

**Milestones:** a tenant asks "how much rent do I owe" and the assistant answers from their own scoped invoices with citation (40); an owner drafts a notice in words and it becomes a draft notice (43).

**Risks**

| Risk                              | L   | I   | Mitigation                                                                                             |
| --------------------------------- | --- | --- | ------------------------------------------------------------------------------------------------------ |
| Prompt injection via resident msg | H   | H   | system prompt immutable; tool calls only via allow-listed API; no raw SQL/token exposure (SECURITY.md) |
| Hallucinated money/rent numbers   | H   | H   | assistant never computes money; reads invoices; answers "I don't have that" over guessing              |
| Scope leak across PGs             | H   | H   | every tool call re-validates membership server-side; scope from token is cache only                    |
| Cost run-away                     | M   | M   | budget caps, streaming, turn limits; no persistence of raw prompt bodies                               |

## Phase 5 — PG Discovery

**Goal:** resdents find a PG and start a conversation — a browse layer over the existing PG/tent structures, with zero cut into the vertical feature set.

**Scope:** public/authenticated discovery — browse PGs by city/location/facilities/rent band, PG detail with photos + facilities + rules, enquiry/complaint path to "book a visit", owner listing toggles visibility, sentiment-safe snippet (no fabricated facilities). Reuses Rooms/Beds/Tenants machinery; adds no new business logic outside discovery.

**Timeline (6 weeks):**

| Milestone                       | Wk    | Exit state                                          |
| ------------------------------- | ----- | --------------------------------------------------- |
| Search + filters + list         | 45    | browse by city/facilities/rent; paginated           |
| PG detail + media               | 46-47 | photos (storage signed), facilities, rules, contact |
| Enquiry + visits + lead capture | 47-50 | enquiry → owner notified; visit slots; lead funnel  |

**Milestones:** a tenant-finder browses to a PG and sends an enquiry that appears on the owner dashboard (48).

**Risks**

| Risk                         | L   | I   | Mitigation                                                                    |
| ---------------------------- | --- | --- | ----------------------------------------------------------------------------- |
| Stale availability in browse | M   | H   | availability is derived from live beds, shown as "approx"; contact then lease |
| Lead spam                    | M   | M   | per-identity rate limit + verification before owner contact shared            |
| Photos without authz         | M   | M   | signed URLs short TTL; private bucket; never public CDN (SECURITY.md)         |

## Phase 6 — Marketplace

**Goal:** transactions between residents and local sellers — a restrained marketplace on the same multi-tenant core, reusing users, PGs, payments, notifications, and addresses.

**Scope:** sellers (owners/staff or local vendors), product catalog, marketplace orders + checkout via the existing payment surface, delivery/collection windows, ratings. Every arm reuses the payment webhook + notifications; no second database.

**Timeline (8 weeks):**

| Milestone                    | Wk    | Exit state                                            |
| ---------------------------- | ----- | ----------------------------------------------------- |
| Seller + catalog             | 52    | seller onboarding, products with media + inventory    |
| Orders + checkout + payments | 53-56 | cart, checkout, Razorpay, webhook reconcile, statuses |
| Fulfilment + ratings         | 56-59 | collection/delivery, pickup confirm, buyer ratings    |

**Milestones:** a resident orders from a local seller and the seller dashboard shows the paid order that the backend verified (55).

**Risks**

| Risk                       | L   | I   | Mitigation                                                                               |
| -------------------------- | --- | --- | ---------------------------------------------------------------------------------------- |
| Marketplace drags monolith | M   | H   | bounded by marketplace module; payments only through existing webhook                    |
| Seller trust / fraud       | M   | M   | payout via owner-arranged flow; complaints + ratings surface; audit on all state changes |
| Inventory edge cases       | M   | M   | stock is decremented server-side at order confirm only; no client override               |

## Phase 7 — Hotel & Apartment Expansion

**Goal:** prove the "many verticals, one core" thesis — Nestro runs a second (hotel) and third (apartment) vertical without new core tables, reusing PG building/room/bed, rent, complaints, notices, payments, notifications, and the AI assistant.

**Scope:** renaming/skinning of vertical concepts (PG → property), hotel-specific stays (short stays, daily rates), apartment-specific lease cycles, plus shared SaaS-ification hooks (already in SECURITY.md/API). Revenue: cut of processed rent for these verticals.

**Timeline (10 weeks):**

| Milestone                | Wk    | Exit state                                                |
| ------------------------ | ----- | --------------------------------------------------------- |
| Vertical config sketch   | 61    | `type`-driven property config; schema carve-out validated |
| Hotel stays              | 62-65 | night-based stays + daily rate + checkout                 |
| Apartment leases         | 65-68 | lease cycles reuse rent; different term length            |
| Multi-vertical dashboard | 68-70 | owner switches verticals within one surface               |

**Milestones:** a hotel runs a check-in→check-out with nightly revenue on the dashboard (65); an apartment lease rents month-to-month alongside a PG (68).

**Risks**

| Risk                              | L   | I   | Mitigation                                                                         |
| --------------------------------- | --- | --- | ---------------------------------------------------------------------------------- |
| Vertical config becomes spaghetti | H   | H   | `type` column only; behaviour via services keyed on type; no per-type table sprawl |
| Rent model doesn't fit hotels     | M   | H   | nightly stays modelled as short rent-cycle; keep invoice set; no new money table   |
| Revenue cut bookkeeping           | M   | M   | cut computed server-side on settled payments only; audited                         |

## Cross-Cutting Risks

Running themes that apply to every phase, refreshed each quarter:

| Risk                                      | L   | I   | Mitigation                                                       |
| ----------------------------------------- | --- | --- | ---------------------------------------------------------------- |
| Schema drift between docs and DB          | H   | H   | migrations generated from DATABASE.md; CI diff gate              |
| Payment webhook/trust boundary regression | H   | H   | webhook-only status; settle tests per phase; SECURITY.md §1      |
| Type drift between frontends and API      | M   | H   | typed client generated from API_SPEC; contract tests             |
| Notification reliability                  | M   | M   | FCM fallback inbox + per-category toggles; surfaced on dashboard |
| Secrets leak at any phase                 | M   | H   | gitleaks gate in CI; env-only; never commit `.env`               |

## Success Metrics (Product-wide)

| Metric                                       | Phase 1 target | Long-term target      |
| -------------------------------------------- | -------------- | --------------------- |
| API p95 latency (seeded data)                | < 300 ms       | < 250 ms              |
| Payment reconciliation (settled vs invoiced) | 100%           | 100%                  |
| Rent invoice generation drift (days)         | 0              | 0                     |
| Complaint median time-to-resolved            | 48 h           | 24 h                  |
| Crash-free sessions (mobile)                 | ≥ 99.5%        | ≥ 99.9%               |
| Weekly active residents using AI             | Phase 4+       | ≥ 60% of active stays |
| Owner retention (still operating a PG)       | Phase 2+       | ≥ 85%                 |
| Marketplace GMV (settled)                    | Phase 6+       | $M per region         |
