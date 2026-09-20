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