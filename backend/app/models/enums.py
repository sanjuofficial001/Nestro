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