"""Shared FastAPI dependencies: identity and role authorization.

Every route that needs a caller declares one of these; nothing in a router
re-implements authentication or role checks.

- `get_current_user` — the single identity seam (SECURITY.md §1). Accepts the
  `Authorization: Bearer <JWT>` header (specific scheme via `HTTPBearer`),
  verifies the token, resolves `sub` to a platform `User`, and rejects missing,
  malformed, expired, unknown-`sub`, and inactive users — all as one generic
  401 so causes stay indistinguishable (SECURITY.md §1).
- `require_role(...)` / `require_any_role(...)` — reusable role guards built on
  `get_current_user`. The DB row is the role authority; the JWT `role` claim is
  never trusted. The platform-wide role (SUPER_ADMIN) passes any guard.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth import get_verifier
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.security import role_satisfies
from app.db.session import get_db
from app.models.enums import RoleEnum
from app.models.user import User
from app.repositories.user import UserRepository

security = HTTPBearer(auto_error=False)

_Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(security)]
_SessionDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    credentials: _Credentials,
    db: _SessionDep,
) -> User:
    """Dependency: resolve the authenticated, active user from the bearer token."""
    if credentials is None or not credentials.credentials:
        raise AuthenticationError()
    try:
        claims = get_verifier().verify(credentials.credentials)
    except AuthenticationError:
        raise
    user = UserRepository(db).get_by_id(claims.sub)
    if user is None or not user.is_active:
        raise AuthenticationError()
    return user


def require_role(role: RoleEnum) -> Callable[..., User]:
    """Build a dependency requiring `role` (or the platform-wide role)."""

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not role_satisfies(user.role, {role}):
            raise AuthorizationError()
        return user

    return dependency


def require_any_role(*roles: RoleEnum) -> Callable[..., User]:
    """Build a dependency requiring any of `roles` (the platform-wide role always passes)."""

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not role_satisfies(user.role, roles):
            raise AuthorizationError()
        return user

    return dependency
