# Nestro Product Specification

## Overview

Nestro is a multi-tenant PG (paying guest) management and resident experience platform. The platform hosts many organizations (PG chains, hostels, apartments, hotels, co-living), each an independent tenant that owns its properties and residents; no two organizations share data. It connects PG residents with owners and managers through a mobile app and dashboard, covering operations from move-in to rent collection, daily living (complaints and notices), and food management.

**Platforms:** Mobile app (residents) and web dashboard (owners/managers).

**Tenant model:** `organizations` is the tenant boundary. Every business row belongs to exactly one organization, and a user only sees an organization's data through an `organization_members` membership row (role: owner / manager / staff). `SUPER_ADMIN` is the only platform-wide role. See ARCHITECTURE.md and SECURITY.md §9.

## User Roles

| Role     | Platform  | Description                                                                                                  |
| -------- | --------- | ------------------------------------------------------------------------------------------------------------ |
| Resident | Mobile    | Lives in a PG; pays rent, files complaints, receives notices, orders meals.                                  |
| Owner    | Dashboard | Owns PGs; creates properties, configures PGs, and monitors operations.                                       |
| Manager  | Dashboard | Runs day-to-day PG operations on behalf of the owner: tenants, rooms, beds, rent, complaints, notices, food. |
| Admin    | Dashboard | Platform-level operator; manages users, PGs, and system configuration.                                       |

Permissions summarized:

- **Resident** — view own PG and room/bed, view/raise complaints, view notices, track and pay own rent, manage own profile.
- **Owner** — manage own PGs end to end; assign managers.
- **Manager** — manage tenants, rooms, beds, rent, complaints, notices, and food within assigned PGs.
- **Admin** — everything owners see, plus PG and user administration across the platform.

## Phase 1 Features

1. Authentication
2. PG Management
3. Tenant Management
4. Room Management
5. Bed Management
6. Rent Tracking
7. Complaints
8. Notices
9. Notifications

---

### 1. Authentication

**User stories**

- As a resident, I want to sign up or sign in with my phone/email so I can access my PG account.
- As an owner/manager, I want to sign in to the dashboard so I can manage my PGs.
- As any user, I want to sign out and have my session end so my account stays secure.

**Acceptance criteria**

- User can sign up with email or phone and verify it.
- User can sign in and out; sessions persist across restarts until expiry.
- Passwords and tokens are handled securely (hashed credentials, short-lived tokens, no secrets client-side).
- Role is assigned and enforced on login: resident, owner, manager, or admin.
- Unauthenticated requests to protected endpoints are rejected.

---

### 2. PG Management

**User stories**

- As an owner, I want to create a PG with name, address, facilities, and rules so residents know what to expect.
- As an owner, I want to edit PG details so information stays current.
- As a manager, I want to view the list of PGs I manage so I can switch between properties.
- As an owner, I want to activate, deactivate, or close a PG so I can manage its lifecycle.

**Acceptance criteria**

- Owner can create a PG with required details (name, address, type/facilities, rules).
- Owner and assigned managers can edit PG details; edits are reflected immediately.
- PG can be active or inactive; only active PGs accept new tenants and show on resident apps.
- Owner can close a PG; closed is a terminal state that retains history.
- Manager can list only PGs assigned to them.

---

### 3. Tenant Management

**User stories**

- As a manager, I want to add a tenant to a PG and assign them to a room/bed so occupancy is recorded.
- As a manager, I want to view tenant profiles and stay history so I can manage occupancy.
- As a manager, I want to mark a tenant as moved-out so the bed becomes available.
- As a resident, I want to view my profile and move-in history.

**Acceptance criteria**

- Tenant record is created with name, contact, move-in date, and assigned PG + room + bed.
- Tenant is linked to a user account when available; otherwise an invitation is generated.
- Manager can view, update, and deactivate tenant records.
- Move-out marks the tenant inactive, frees the bed, and ends active rent and meal plans.
- No duplicate active tenant per bed.

---

### 4. Room Management

**User stories**

- As an owner/manager, I want to create rooms within a PG so I can organize space.
- As a manager, I want to update a room's type and rent so listings stay accurate.
- As a manager, I want to mark a room as unavailable so it cannot be assigned.

**Acceptance criteria**

- Room can be created with number, type (single/shared), capacity, and rent.
- Renaming or updating room details reflects across the PG instantly.
- Room status: available, partially occupied, full, unavailable.
- Rooms belong to exactly one PG; deleting is not allowed once tenants have history (archive instead).

---

### 5. Bed Management

**User stories**

- As a manager, I want to assign and release beds so occupancy is accurate.
- As a resident, I want to see which bed I occupy so I know where I stay.

**Acceptance criteria**

- Each room has beds equal to its capacity.
- Bed has status: available, occupied, or blocked.
- Assigning/blocking/releasing a bed updates the room occupancy status.
- A tenant can occupy exactly one active bed.
- Bed holds history of past occupants.

---

### 6. Rent Tracking

**User stories**

- As a manager, I want to set rent for a tenant (amount, due date, cycle) so collection is predictable.
- As a resident, I want to view my rent due and past payments so I can budget.
- As a resident, I want to pay rent online so I don't have to pay in person.
- As an owner, I want to see collection status per PG so I can manage cash flow.

**Acceptance criteria**

- Rent is set per tenant with amount, cycle, and due date; can be adjusted only by manager/owner.
- Payments can be recorded as received or made via online payment gateway (Razorpay).
- Online payment status is confirmed server-side via webhook; never trusted from the client.
- Tenant sees current outstanding, due date, and full payment history.
- Owner/manager sees collection summary (collected, overdue, outstanding) per PG.
- Overdue rent is flagged and surfaced to manager and tenant.

---

### 7. Complaints

**User stories**

- As a resident, I want to file a complaint (category, description, photo) so issues are reported.
- As a resident, I want to track my complaint's status so I know it's being handled.
- As a manager, I want to view and update complaint status so issues get resolved.

**Acceptance criteria**

- Resident can raise a complaint with category, description, and optional photo; assigned to their PG.
- Complaint statuses: open, in-progress, resolved, closed.
- Manager can update status and add internal notes (not shown to residents).
- Resident is notified on status changes to their complaint.
- History of each complaint is preserved.

---

### 8. Notices

**User stories**

- As an owner/manager, I want to publish a notice to all residents of a PG so everyone stays informed.
- As a resident, I want to read notices for my PG so I don't miss updates.

**Acceptance criteria**

- Owner/manager can publish notices targeted at one or more PGs (or all).
- Notice has title, body, publish date, optional expiry.
- Residents see only notices for their own PG, newest first.
- Residents receive a push notification when a relevant notice is published.

---

### 9. Notifications

**User stories**

- As a resident, I want to receive push notifications about my rent, complaints, and notices so I stay updated.
- As a manager, I want to receive notifications for new complaints so I can respond promptly.

**Acceptance criteria**

- Notifications are delivered via Firebase Cloud Messaging to mobile devices.
- Notification preferences can be toggled by the user (per category: rent, complaints, notices, food).
- Generated for: new/updated complaint, dues/overdue rent, published notice, payment confirmation.
- Delivery failures are non-blocking; core features work without notification permission.
- Notification history and read state are stored per user.

---

## Future Roadmap

| Phase   | Focus                    | Highlights                                              |
| ------- | ------------------------ | ------------------------------------------------------- |
| Phase 2 | Food management          | Meal plans, daily menu, ordering, billing               |
| Phase 2 | Payments & reports       | Gateway reconciliation, owner payout dashboards, export |
| Phase 3 | Marketplace              | Essentials/products posted by owners and vendors        |
| Phase 3 | Community                | Roommate matching based on preferences                  |
| Phase 4 | Multi-vertical expansion | Hotel and apartment support on the same platform        |

## Success Criteria (Phase 1)

- A resident can sign up, move into a PG, track and pay rent, raise complaints, and receive notices on mobile.
- An owner/manager can onboard a PG, manage tenants/rooms/beds, run rent collection, and resolve complaints from the dashboard.
- All features are covered by tests, all APIs are documented, and no client ever accesses the database directly.
