"""Permission-matcher tests — the role authorization seam (SECURITY.md §2).

`role_satisfies` is the single authority for "does an authenticated user's role
pass a requirement". The platform-wide role (SUPER_ADMIN) always passes, so that
behaviour is pinned explicitly and separately from the ordinary allow-list
logic.
"""

from app.core.security import role_satisfies
from app.models.enums import RoleEnum


def test_role_satisfies_exact_match() -> None:
    assert role_satisfies(RoleEnum.PG_OWNER, {RoleEnum.PG_OWNER})


def test_role_satisfies_any_member_of_requirements() -> None:
    assert role_satisfies(RoleEnum.MANAGER, {RoleEnum.PG_OWNER, RoleEnum.MANAGER})


def test_role_satisfies_empty_requirements() -> None:
    assert not role_satisfies(RoleEnum.MANAGER, set())


def test_role_satisfies_unrelated_role() -> None:
    assert not role_satisfies(RoleEnum.MANAGER, {RoleEnum.PG_OWNER})


def test_role_satisfies_platform_role_passes_everything() -> None:
    assert role_satisfies(RoleEnum.SUPER_ADMIN, {RoleEnum.PG_OWNER})
    assert role_satisfies(RoleEnum.SUPER_ADMIN, set())
    assert role_satisfies(RoleEnum.SUPER_ADMIN, {RoleEnum.MANAGER})
