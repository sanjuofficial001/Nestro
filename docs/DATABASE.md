# DATABASE.md

# 1. Overview

Nestro uses PostgreSQL (Supabase) as its primary database.

The system is designed as a **multi-tenant SaaS platform** where:

- One organization can manage multiple properties
- One property can be a PG, Hostel, Apartment, Hotel, or Co-living space
- Users belong to organizations through memberships
- All business data is isolated by organization
- The FastAPI backend is the only component allowed to access the database

---

# 2. Design Principles

## Multi-Tenant First

Every business table contains:

```sql
organization_id UUID NOT NULL
```

All queries must be scoped by organization:

```sql
WHERE organization_id = :organization_id
```

No cross-organization access is permitted.

## UUID Primary Keys

All primary keys use:

```sql
UUID
```

Generated with:

```sql
gen_random_uuid()
```

## Timestamps

Every table contains:

```sql
created_at TIMESTAMPTZ
updated_at TIMESTAMPTZ
```

Stored in UTC.

## Soft Deletes

Tables containing historical business data use:

```sql
deleted_at TIMESTAMPTZ NULL
```

Records are archived rather than removed.

Examples:

- properties
- rooms
- users

## Hard Deletes

Allowed only for:

- temporary records
- cache records
- device tokens

## Auditability

Business actions are tracked through:

```text
audit_logs
```

## File Storage

Files are stored in:

```text
Supabase Storage
```

Metadata is stored in:

```text
files
```

---

# 3. Multi-Tenant Architecture

```text
Organization
│
├── Members
│
├── Properties
│   ├── Buildings
│   │   ├── Floors
│   │   │   ├── Rooms
│   │   │   │   ├── Beds
│
│   ├── Resident Profiles
│   ├── Rent Plans
│   ├── Rent Invoices
│   ├── Payments
│   ├── Complaints
│   ├── Notices
│
│   ├── Files
│   ├── Audit Logs
│   └── Settings
│
└── Notifications
```

---

# 4. Entity Relationship Diagram

```mermaid
erDiagram

    ORGANIZATIONS ||--o{ ORGANIZATION_MEMBERS : contains

    USERS ||--o{ ORGANIZATION_MEMBERS : joins

    ORGANIZATIONS ||--o{ PROPERTIES : owns

    PROPERTIES ||--o{ BUILDINGS : contains

    BUILDINGS ||--o{ FLOORS : contains

    FLOORS ||--o{ ROOMS : contains

    ROOMS ||--o{ BEDS : contains

    ORGANIZATION_MEMBERS ||--o{ RESIDENT_PROFILES : becomes

    RESIDENT_PROFILES ||--o{ TENANT_STAYS : occupies

    BEDS ||--o{ TENANT_STAYS : assigned

    TENANT_STAYS ||--o{ RENT_PLANS : billed

    RENT_PLANS ||--o{ RENT_INVOICES : generates

    RENT_INVOICES ||--o{ PAYMENTS : settled

    RESIDENT_PROFILES ||--o{ COMPLAINTS : creates

    COMPLAINTS ||--o{ COMPLAINT_COMMENTS : contains

    USERS ||--o{ NOTIFICATIONS : receives

    ORGANIZATIONS ||--o{ AUDIT_LOGS : owns

    ORGANIZATIONS ||--|| ORGANIZATION_SETTINGS : configures
```

---

# 5. organizations

## Purpose

Top-level tenant boundary.

Represents a business/customer account using Nestro.

Examples:

```text
ABC Mall
Sunrise Apartments
Tech Park Chennai
```

Each organization owns:

```text
Properties
Residents
Staff
Invoices
Complaints
Settings
```

No data is shared across organizations.

## Columns

| Column     | Type         | Notes        |
| ---------- | ------------ | ------------ |
| id         | UUID PK      |              |
| name       | VARCHAR(255) | required     |
| slug       | VARCHAR(100) | unique       |
| is_active  | BOOLEAN      | default true |
| created_at | TIMESTAMPTZ  | mixin        |
| updated_at | TIMESTAMPTZ  | mixin        |

## Slug

Lowercase, no spaces, 3–100 characters. Unique across organizations.

## Indexes

```sql
ix_organizations_slug (unique)
```

## Deferred Columns

The following organization fields are designed for a later milestone and are
not part of the current schema:

```text
organization_type      (PG_COMPANY, HOSTEL_OPERATOR, HOTEL_GROUP,
                        APARTMENT_MANAGER, COLIVING_OPERATOR)
contact_email
contact_phone
status                 (ACTIVE, INACTIVE, SUSPENDED, CLOSED)
deleted_at             (soft delete)
```

---

# 6. users

## Purpose

Platform-wide user accounts.

A user can belong to multiple organizations.

Examples:

```text
Owner
Manager
Staff
Resident
Super Admin
```

Authentication is managed through:

```text
Supabase Auth
```

## Columns

| Column      | Type        | Notes            |
| ----------- | ----------- | ---------------- |
| id          | UUID PK     |                  |
| email       | TEXT        | unique, NOT NULL |
| phone       | TEXT        | unique, nullable |
| full_name   | TEXT        | NOT NULL         |
| role        | user_role   | ENUM, NOT NULL   |
| is_active   | BOOLEAN     | NOT NULL         |
| is_verified | BOOLEAN     | NOT NULL         |
| created_at  | TIMESTAMPTZ |                  |
| updated_at  | TIMESTAMPTZ |                  |

No password or auth fields live on this table; credentials and hashes belong
to Supabase Auth only.

## role

Native PostgreSQL ENUM named `user_role`:

```text
SUPER_ADMIN
PG_OWNER
MANAGER
STAFF
TENANT
```

Org-scoped permissions are assigned through `organization_members` (see §7),
whose `role` column holds `OWNER`, `MANAGER`, `STAFF`.

## Constraints

```sql
UNIQUE(email)
UNIQUE(phone)
```

## Indexes

```sql
idx_users_role
```

---

# 7. organization_members

## Purpose

Connects users to organizations.

Defines permissions inside an organization.

This is the primary authorization table.

A user belongs to exactly one organization today.

Future multi-org support is intentionally deferred.

## Columns

| Column          | Type              |
| --------------- | ----------------- |
| id              | UUID PK           |
| organization_id | UUID FK           |
| user_id         | UUID FK           |
| role            | organization_role |
| created_at      | TIMESTAMPTZ       |
| updated_at      | TIMESTAMPTZ       |

## Roles

Native PostgreSQL ENUM named `organization_role`:

```text
OWNER
MANAGER
STAFF
```

`OWNER` is the organization owner; `MANAGER` and `STAFF` cover operational
members. Resident roles arrive with the resident-profile milestone.

## Constraints

```sql
UNIQUE (
organization_id,
user_id
)
```

A user cannot appear twice in the same organization.

## Indexes

```sql
ix_organization_members_organization_id
ix_organization_members_user_id
```

---

# 8. organization_settings

## Purpose

Stores organization-specific configuration.

Example:

```json
{
  "timezone": "Asia/Kolkata",
  "currency": "INR",
  "rent_reminders": true,
  "branding": {
    "logo": "logo.png"
  }
}
```

## Columns

| Column          | Type        |
| --------------- | ----------- |
| organization_id | UUID PK FK  |
| settings        | JSONB       |
| created_at      | TIMESTAMPTZ |
| updated_at      | TIMESTAMPTZ |

---

# 9. properties

## Purpose

Physical locations managed by an organization.

The first business entity scoped by `organization_id` — every property belongs
to exactly one organization, and reads are scoped by it (no unscoped read
paths).

Supports:

```text
PG
HOSTEL
HOTEL
APARTMENT
COLIVING
```

One organization can own many properties.

Example:

```text
ABC Living Pvt Ltd

├── PSG Boys PG
├── PSG Girls PG
├── Elite Hostel
├── Green Residency
```

In the client-facing API a "PG" is a `property` with `property_type = 'PG'`.

## Columns

| Column          | Type              | Notes                  |
| --------------- | ----------------- | ---------------------- |
| id              | UUID PK           |                        |
| organization_id | UUID FK           | NOT NULL, indexed      |
| name            | VARCHAR(255)      | required               |
| property_type   | `property_type`   | native ENUM, NOT NULL  |
| address         | TEXT              | nullable               |
| contact_phone   | VARCHAR(20)       | nullable               |
| rules           | TEXT              | nullable               |
| status          | `property_status` | native ENUM, NOT NULL  |
| created_at      | TIMESTAMPTZ       | mixin                  |
| updated_at      | TIMESTAMPTZ       | mixin                  |
| deleted_at      | TIMESTAMPTZ       | nullable (soft delete) |

## property_type

Native PostgreSQL ENUM named `property_type`:

```text
PG
HOSTEL
HOTEL
APARTMENT
COLIVING
```

## status

Native PostgreSQL ENUM named `property_status`:

```text
ACTIVE
INACTIVE
CLOSED
```

## Indexes

```sql
ix_properties_organization_id
ix_properties_property_type
ix_properties_status
```

## Constraints

The enum columns are enforced by the database via the native ENUM types
(`property_type`, `property_status`) above.

Soft-delete filtering behavior (excluding `deleted_at IS NOT NULL` rows) ships
with the properties CRUD milestone; the column exists now.

---

# 10. buildings

## Purpose

Represents physical buildings within a property.

A property can have one or many buildings.

Example:

```text
PSG Boys PG

Building A
Building B
Building C
```

## Columns

| Column          | Type        |
| --------------- | ----------- |
| id              | UUID PK     |
| organization_id | UUID FK     |
| property_id     | UUID FK     |
| name            | TEXT        |
| description     | TEXT        |
| created_at      | TIMESTAMPTZ |
| updated_at      | TIMESTAMPTZ |

## Relationships

```text
Property
 └── Buildings
```

## Indexes

```sql
ix_buildings_organization_id
ix_buildings_property_id
```

## Constraints

```sql
UNIQUE(property_id, name)
```

---

# 11. floors

## Purpose

Represents floors within a building.

## Columns

| Column          | Type        |
| --------------- | ----------- |
| id              | UUID PK     |
| organization_id | UUID FK     |
| building_id     | UUID FK     |
| floor_number    | INTEGER     |
| name            | TEXT        |
| created_at      | TIMESTAMPTZ |
| updated_at      | TIMESTAMPTZ |

## Example

```text
Building A

Floor 0
Floor 1
Floor 2
Floor 3
```

## Indexes

```sql
ix_floors_organization_id
ix_floors_building_id
```

## Constraints

```sql
UNIQUE(building_id, floor_number)
```

---

# 12. rooms

## Purpose

Represents rentable rooms.

Room capacity is **not stored**. Capacity is always derived from the number of
`Bed` records associated with a Room (`COUNT(beds.id)`). This allows rooms to
support any number of beds without schema changes: a single room has 1 bed, a
double has 2, a four-share PG room has 4, a dorm has 20+.

## Columns

| Column          | Type        |
| --------------- | ----------- |
| id              | UUID PK     |
| organization_id | UUID FK     |
| floor_id        | UUID FK     |
| room_number     | TEXT        |
| room_type       | TEXT        |
| created_at      | TIMESTAMPTZ |
| updated_at      | TIMESTAMPTZ |

There is deliberately no `capacity`, `max_beds`, `bed_count`, or equivalent
derived-count column.

## room_type

Native PostgreSQL ENUM named `room_type`:

```text
SINGLE
DOUBLE
TRIPLE
FOUR_SHARE
FIVE_SHARE
CUSTOM
```

## Relationships

```text
Floor
 └── Rooms
     └── Beds
```

## Indexes

```sql
ix_rooms_organization_id
ix_rooms_floor_id
ix_rooms_room_number
```

## Constraints

```sql
UNIQUE(floor_id, room_number)
```

---

# 13. beds

## Purpose

Represents occupancy units — the atomic seat inside a room.

A room can contain any number of beds; the bed rows owned by a room define its
capacity (see §12).

## Columns

| Column          | Type        |
| --------------- | ----------- |
| id              | UUID PK     |
| organization_id | UUID FK     |
| room_id         | UUID FK     |
| bed_number      | TEXT        |
| status          | TEXT        |
| created_at      | TIMESTAMPTZ |
| updated_at      | TIMESTAMPTZ |

## Example

```text
Room 101

Bed A
Bed B
Bed C
Bed D
```

## status

Native PostgreSQL ENUM named `bed_status`:

```text
AVAILABLE
OCCUPIED
BLOCKED
MAINTENANCE
```

## Indexes

```sql
ix_beds_organization_id
ix_beds_room_id
ix_beds_status
```

## Constraints

```sql
UNIQUE(room_id, bed_number)
```

---

# 14. resident_profiles

## Purpose

Stores resident-specific information.

A resident must first be:

```text
User
    ↓
Organization Member
         ↓
Resident Profile
```

This avoids duplicating identity information: names, phone, and email live on
`users`; the profile only adds residency data. The profile references the
membership (`organization_member_id`), not the raw user, so a user can hold a
resident profile in every organization they are a member of.

## Columns

| Column                  | Type        |
| ----------------------- | ----------- |
| id                      | UUID PK     |
| organization_id         | UUID FK     |
| organization_member_id  | UUID FK     |
| property_id             | UUID FK     |
| emergency_contact_name  | TEXT        |
| emergency_contact_phone | TEXT        |
| address                 | TEXT        |
| notes                   | TEXT        |
| is_active               | BOOLEAN     |
| created_at              | TIMESTAMPTZ |
| updated_at              | TIMESTAMPTZ |

`property_id` is nullable: a profile can exist before assignment to a property
and before bed assignment (stays). Lifecycle details that will carry move-in /
move-out history are deferred to §15 `tenant_stays`, which owns occupancy
history; `occupation_type`, `occupation_name`, `emergency_contact_relationship`,
and `moved_in_at` / `moved_out_at` columns arrive with that (stays) milestone if
still needed.

## Relationships

```text
Organization ──┬── Member ── User (via organization_members)
               └── Resident Profile
Property ── Resident Profiles
```

## Indexes

```sql
ix_resident_profiles_organization_id
ix_resident_profiles_property_id
```

## Constraints

```sql
UNIQUE (organization_member_id)
```

One resident profile per membership.

---

# 15. tenant_stays

## Purpose

Tracks bed occupancy history:

```text
Resident Profile → Tenant Stay → Bed
```

This table is extremely important.

Never store:

```text
resident → bed
```

directly.

Use stays.

This preserves historical occupancy.

## Columns

| Column              | Type        |
| ------------------- | ----------- |
| id                  | UUID PK     |
| organization_id     | UUID FK     |
| resident_profile_id | UUID FK     |
| property_id         | UUID FK     |
| bed_id              | UUID FK     |
| start_date          | DATE        |
| end_date            | DATE        |
| status              | ENUM        |
| notes               | TEXT        |
| created_at          | TIMESTAMPTZ |
| updated_at          | TIMESTAMPTZ |

`property_id` is stored on the stay (not just reached through the bed chain) so
occupancy is queryable per venue without joining. `end_date` and `notes` are
nullable; an open stay has no `end_date` yet.

## status

Native SQL enum: `tenant_stay_status`

```text
ACTIVE
COMPLETED
CANCELLED
```

- **ACTIVE** — an open stay: the resident currently occupies the bed (`end_date`
  is `NULL`).
- **COMPLETED** — the stay ended on its own; the row stays as history.
- **CANCELLED** — the stay was terminated early; the row stays as history.

The `ACTIVE` status is the only one that makes a bed "occupied".

## Example

```text
Resident

Jan 2025 → Bed A
Jul 2025 → Bed C
Nov 2025 → Bed B
```

Full history retained.

## Constraints

```sql
-- at most one ACTIVE stay per bed (partial unique index)
CREATE UNIQUE INDEX uq_tenant_stays_active_bed
  ON tenant_stays (bed_id)
  WHERE status = 'ACTIVE';
```

Implemented as a partial unique index — a whole-table `UNIQUE (bed_id, status)`
would allow only one row per status value and block re-occupying a bed ever.

Deferred to the billing/stays milestone: `security_deposit NUMERIC(12,2)` and
the `one active stay per resident` rule (DATABASE.md §15 history note).

## Indexes

```sql
ix_tenant_stays_organization_id
ix_tenant_stays_resident_profile_id
ix_tenant_stays_bed_id
```

---

# 16. rent_plans

## Purpose

Defines recurring billing rules.

## Columns

| Column              | Type          |
| ------------------- | ------------- |
| id                  | UUID PK       |
| organization_id     | UUID FK       |
| resident_profile_id | UUID FK       |
| amount              | NUMERIC(12,2) |
| billing_cycle       | TEXT          |
| due_day             | INTEGER       |
| deposit_amount      | NUMERIC(12,2) |
| is_active           | BOOLEAN       |
| created_at          | TIMESTAMPTZ   |
| updated_at          | TIMESTAMPTZ   |

## billing_cycle

```text
MONTHLY
QUARTERLY
HALF_YEARLY
YEARLY
```

## Constraints

```sql
CHECK (due_day BETWEEN 1 AND 31)
```

## Indexes

```sql
idx_rent_plan_org
idx_rent_plan_resident
```

---

# 17. rent_invoices

## Purpose

Generated billing records.

Each billing cycle creates one invoice.

## Columns

| Column              | Type          |
| ------------------- | ------------- |
| id                  | UUID PK       |
| organization_id     | UUID FK       |
| rent_plan_id        | UUID FK       |
| resident_profile_id | UUID FK       |
| invoice_number      | TEXT          |
| billing_start_date  | DATE          |
| billing_end_date    | DATE          |
| due_date            | DATE          |
| amount              | NUMERIC(12,2) |
| late_fee            | NUMERIC(12,2) |
| total_amount        | NUMERIC(12,2) |
| status              | TEXT          |
| created_at          | TIMESTAMPTZ   |
| updated_at          | TIMESTAMPTZ   |

## status

```text
DRAFT
ISSUED
PAID
PARTIALLY_PAID
OVERDUE
VOID
```

## Constraints

```sql
UNIQUE(invoice_number)
```

## Indexes

```sql
idx_invoice_org
idx_invoice_status
idx_invoice_due_date
idx_invoice_resident
```

---

# 18. payments

## Purpose

Stores payment transactions.

Supports:

```text
Razorpay
UPI
Cash
Bank Transfer
Card
```

## Columns

| Column                 | Type          |
| ---------------------- | ------------- |
| id                     | UUID PK       |
| organization_id        | UUID FK       |
| invoice_id             | UUID FK       |
| amount                 | NUMERIC(12,2) |
| payment_method         | TEXT          |
| gateway_transaction_id | TEXT          |
| gateway_order_id       | TEXT          |
| status                 | TEXT          |
| paid_at                | TIMESTAMPTZ   |
| created_at             | TIMESTAMPTZ   |
| updated_at             | TIMESTAMPTZ   |

## status

```text
PENDING
SUCCESS
FAILED
REFUNDED
PARTIAL_REFUND
```

## Constraints

```sql
CHECK (amount > 0)
```

## Indexes

```sql
idx_payments_org
idx_payments_invoice
idx_payments_status
idx_payments_paid_at
```

---

---

# 19. complaints

## Purpose

Allows residents to raise issues related to accommodation, facilities, maintenance, food, housekeeping, security, or other services.

## Columns

| Column                | Type        |
| --------------------- | ----------- |
| id                    | UUID PK     |
| organization_id       | UUID FK     |
| property_id           | UUID FK     |
| resident_profile_id   | UUID FK     |
| title                 | TEXT        |
| description           | TEXT        |
| category              | TEXT        |
| priority              | TEXT        |
| status                | TEXT        |
| assigned_to_member_id | UUID FK     |
| resolved_at           | TIMESTAMPTZ |
| created_at            | TIMESTAMPTZ |
| updated_at            | TIMESTAMPTZ |

## Categories

```text
MAINTENANCE
ELECTRICAL
PLUMBING
FOOD
HOUSEKEEPING
SECURITY
INTERNET
OTHER
```

## Priority

```text
LOW
MEDIUM
HIGH
URGENT
```

## Status

```text
OPEN
IN_PROGRESS
ON_HOLD
RESOLVED
CLOSED
```

## Indexes

```sql
idx_complaints_org
idx_complaints_property
idx_complaints_status
idx_complaints_priority
idx_complaints_resident
```

---

# 20. complaint_comments

## Purpose

Tracks discussion and updates related to complaints.

Allows staff and residents to communicate within a complaint thread.

## Columns

| Column       | Type        |
| ------------ | ----------- |
| id           | UUID PK     |
| complaint_id | UUID FK     |
| user_id      | UUID FK     |
| comment      | TEXT        |
| created_at   | TIMESTAMPTZ |

## Indexes

```sql
idx_complaint_comments_complaint
idx_complaint_comments_user
```

---

# 21. notices

## Purpose

Organization-wide announcements.

Examples:

```text
Rent Due Reminder
Water Shutdown Notice
Maintenance Schedule
Festival Announcement
Emergency Communication
```

## Columns

| Column          | Type         |
| --------------- | ------------ |
| id              | UUID PK      |
| organization_id | UUID FK      |
| property_id     | UUID FK NULL |
| title           | TEXT         |
| content         | TEXT         |
| published_by    | UUID FK      |
| publish_at      | TIMESTAMPTZ  |
| expires_at      | TIMESTAMPTZ  |
| created_at      | TIMESTAMPTZ  |
| updated_at      | TIMESTAMPTZ  |

## Indexes

```sql
idx_notices_org
idx_notices_property
idx_notices_publish_at
```

---

# 22. notifications

## Purpose

Stores in-app notifications delivered to users.

Examples:

```text
Rent invoice generated
Payment received
Complaint updated
New notice published
Bed allocation changed
```

## Columns

| Column            | Type        |
| ----------------- | ----------- |
| id                | UUID PK     |
| organization_id   | UUID FK     |
| user_id           | UUID FK     |
| title             | TEXT        |
| message           | TEXT        |
| notification_type | TEXT        |
| is_read           | BOOLEAN     |
| read_at           | TIMESTAMPTZ |
| created_at        | TIMESTAMPTZ |

## notification_type

```text
SYSTEM
PAYMENT
COMPLAINT
NOTICE
RENT
BOOKING
GENERAL
```

## Indexes

```sql
idx_notifications_org
idx_notifications_user
idx_notifications_read
idx_notifications_created
```

---

# 23. device_tokens

## Purpose

Stores push notification device tokens.

Used with:

```text
Firebase Cloud Messaging (FCM)
```

## Columns

| Column       | Type        |
| ------------ | ----------- |
| id           | UUID PK     |
| user_id      | UUID FK     |
| device_id    | TEXT        |
| token        | TEXT        |
| platform     | TEXT        |
| last_seen_at | TIMESTAMPTZ |
| created_at   | TIMESTAMPTZ |

## platform

```text
ANDROID
IOS
WEB
```

## Constraints

```sql
UNIQUE(token)
```

## Indexes

```sql
idx_device_tokens_user
idx_device_tokens_platform
```

---

# 24. files

## Purpose

Centralized file management.

Stores metadata for files uploaded to Supabase Storage.

Supports:

```text
Resident Documents
Property Photos
Complaint Attachments
Notice Attachments
Invoices
Reports
```

## Columns

| Column            | Type        |
| ----------------- | ----------- |
| id                | UUID PK     |
| organization_id   | UUID FK     |
| uploaded_by       | UUID FK     |
| storage_path      | TEXT        |
| original_filename | TEXT        |
| mime_type         | TEXT        |
| file_size_bytes   | BIGINT      |
| entity_type       | TEXT        |
| entity_id         | UUID        |
| created_at        | TIMESTAMPTZ |

## Example

```text
entity_type = complaint
entity_id = complaint_uuid

entity_type = resident_profile
entity_id = resident_uuid
```

## Indexes

```sql
idx_files_org
idx_files_entity
idx_files_uploaded_by
```

---

# 25. audit_logs

## Purpose

Tracks all critical actions performed in the system.

Essential for:

```text
Security
Compliance
Debugging
Dispute Resolution
Analytics
```

## Columns

| Column          | Type        |
| --------------- | ----------- |
| id              | UUID PK     |
| organization_id | UUID FK     |
| actor_user_id   | UUID FK     |
| action          | TEXT        |
| entity_type     | TEXT        |
| entity_id       | UUID        |
| metadata        | JSONB       |
| created_at      | TIMESTAMPTZ |

## Examples

```text
RESIDENT_CREATED
BED_ASSIGNED
INVOICE_GENERATED
PAYMENT_RECORDED
COMPLAINT_RESOLVED
NOTICE_PUBLISHED
USER_INVITED
```

## Indexes

```sql
idx_audit_org
idx_audit_actor
idx_audit_entity
idx_audit_created
```

---

# 26. Referential Integrity Rules

## Organization Isolation

Every business entity must belong to:

```text
organization_id
```

No entity may exist without an organization.

---

## Property Isolation

Properties belong to organizations.

Buildings belong to properties.

Floors belong to buildings.

Rooms belong to floors.

Beds belong to rooms.

---

## Resident Lifecycle

```text
User
    ↓
Organization Member
    ↓
Resident Profile
    ↓
Tenant Stay
    ↓
Rent Plan
    ↓
Rent Invoice
    ↓
Payment
```

---

## Complaint Lifecycle

```text
Resident
    ↓
Complaint
    ↓
Comments
    ↓
Resolution
```

---

# 27. Indexing Strategy

Every table containing:

```sql
organization_id
```

must have an index.

Examples:

```sql
CREATE INDEX ix_rooms_organization_id
ON rooms(organization_id);

CREATE INDEX idx_payments_org
ON payments(organization_id);

CREATE INDEX idx_complaints_org
ON complaints(organization_id);
```

---

# 28. Multi-Tenant Query Rule

All application queries must include:

```sql
WHERE organization_id = :organization_id
```

Example:

```sql
SELECT *
FROM rooms
WHERE organization_id = :organization_id;
```

Never expose data across organizations.

---

# 29. Future Expansion Tables (Phase 2+)

These tables are intentionally excluded from MVP.

### bookings

For hotel-style reservations.

### housekeeping_tasks

For cleaning workflows.

### maintenance_requests

Advanced maintenance tracking.

### visitor_logs

Guest entry and exit management.

### inventory

Consumables and stock tracking.

### vendor_management

External service providers.

### ai_conversations

AI assistant chat history.

### marketplace_listings

Marketplace expansion.

### roommate_matching

Resident matching system.

### analytics_snapshots

Precomputed analytics data.

---

# 30. Final Architecture Summary

```text
Organization
│
├── Organization Members
│
├── Properties
│   ├── Buildings
│   │   ├── Floors
│   │   │   ├── Rooms
│   │   │   │   ├── Beds
│
│   ├── Resident Profiles
│   │   ├── Tenant Stays
│   │   ├── Rent Plans
│   │   ├── Rent Invoices
│   │   └── Payments
│
│   ├── Complaints
│   │   └── Complaint Comments
│
│   ├── Notices
│   ├── Files
│   └── Audit Logs
│
├── Notifications
├── Device Tokens
└── Organization Settings
```

This schema is designed to support:

- PGs
- Hostels
- Co-living Spaces
- Apartments
- Hotels

while maintaining strict multi-tenant isolation and production-grade scalability.
