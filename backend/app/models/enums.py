"""Platform-wide application enums."""

from enum import StrEnum


class RoleEnum(StrEnum):
    """Platform roles. Matching the role model in SECURITY.md.

    PostgreSQL stores these as native ENUM values (`user_role`); org-scoped
    roles arrive with `organization_members` in the auth milestone.
    """

    SUPER_ADMIN = "SUPER_ADMIN"
    PG_OWNER = "PG_OWNER"
    MANAGER = "MANAGER"
    STAFF = "STAFF"
    TENANT = "TENANT"


class OrganizationRoleEnum(StrEnum):
    """Organization-scoped membership roles.

    PostgreSQL stores these as a native ENUM (`organization_role`). Matches
    the roles documented in DATABASE.md; resident/scoped permissions arrive
    with later milestones.
    """

    OWNER = "OWNER"
    MANAGER = "MANAGER"
    STAFF = "STAFF"


class PropertyTypeEnum(StrEnum):
    """Venue kinds. PostgreSQL stores these as a native ENUM (`property_type`)."""

    PG = "PG"
    HOSTEL = "HOSTEL"
    HOTEL = "HOTEL"
    APARTMENT = "APARTMENT"
    COLIVING = "COLIVING"


class PropertyStatusEnum(StrEnum):
    """Property lifecycle. PostgreSQL stores these as a native ENUM (`property_status`)."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    CLOSED = "CLOSED"


class RoomTypeEnum(StrEnum):
    """Room shapes (sharing categories). PostgreSQL stores these as a native ENUM (`room_type`).

    Capacity is not stored anywhere; the sharing names below only describe the
    configured bed count for a room (a double room is whatever number of beds
    the owner assigns it).
    """

    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    TRIPLE = "TRIPLE"
    FOUR_SHARE = "FOUR_SHARE"
    FIVE_SHARE = "FIVE_SHARE"
    CUSTOM = "CUSTOM"


class BedStatusEnum(StrEnum):
    """Bed lifecycle. PostgreSQL stores these as a native ENUM (`bed_status`)."""

    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    BLOCKED = "BLOCKED"
    MAINTENANCE = "MAINTENANCE"


class TenantStayStatusEnum(StrEnum):
    """Stay lifecycle. PostgreSQL stores these as a native ENUM (`tenant_stay_status`).

    `ACTIVE` stays are open (no `end_date`); `COMPLETED` / `CANCELLED` stays are
    closed and retain the occupancy record in the stay's history.
    """

    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ComplaintCategoryEnum(StrEnum):
    """What a complaint is about. PostgreSQL stores this as a native ENUM (`complaint_category`)."""

    MAINTENANCE = "MAINTENANCE"
    ELECTRICAL = "ELECTRICAL"
    PLUMBING = "PLUMBING"
    FOOD = "FOOD"
    HOUSEKEEPING = "HOUSEKEEPING"
    SECURITY = "SECURITY"
    INTERNET = "INTERNET"
    OTHER = "OTHER"


class ComplaintPriorityEnum(StrEnum):
    """Complaint urgency. PostgreSQL stores this as a native ENUM (`complaint_priority`)."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ComplaintStatusEnum(StrEnum):
    """Triage lifecycle. PostgreSQL stores this as a native ENUM (`complaint_status`).

    The order below is the workflow order: a complaint moves one step forward or
    backward at a time, and `CLOSED` is terminal — reopening is a future,
    audited workflow.
    """

    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    ON_HOLD = "ON_HOLD"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"