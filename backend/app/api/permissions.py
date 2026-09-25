"""Organization-scoped authorization helpers — the org-scope sibling of
`app/api/deps.py` platform role guards. Pure Python; no FastAPI dependencies.
"""

from collections.abc import Callable, Iterable

from app.core.security import role_satisfies
from app.models.enums import OrganizationRoleEnum, RoleEnum
from app.models.organization_member import OrganizationMember
from app.models.user import User


def require_org_roles(
    *roles: OrganizationRoleEnum,
) -> Callable[[User, Iterable[OrganizationMember]], None]:
    """Guard: the user must hold one of the org roles in a membership.

    Authorization flows through `OrganizationMember.role`, never `users.role`;
    the platform-wide SUPER_ADMIN role bypasses membership entirely (matching
    `app/api/deps.py` role guards).
    """

    def check(user: User, memberships: Iterable[OrganizationMember]) -> None:
        if role_satisfies(user.role, {RoleEnum.SUPER_ADMIN}):
            return
        if not any(member.role in roles for member in memberships):
            raise PermissionError("insufficient permissions")

    return check