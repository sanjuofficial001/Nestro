"""Security primitives — isolated utilities with no business logic and no DB.

Bearer-token extraction, the JWT algorithm allow-list, the role-matching
helpers used by the authorization layer, and password hashing. Nothing here
reads settings, talks to a database, or raises FastAPI-specific exceptions.
"""

from collections.abc import Collection

from pwdlib import PasswordHash

from app.models.enums import RoleEnum

BEARER_SCHEME = "Bearer"

# RS256 is the only algorithm Supabase Auth signs with; anything else — including
# HS256 and the `none` algorithm — is rejected before decoding even starts.
SUPPORTED_JWT_ALGORITHMS = frozenset({"RS256"})

# A token carrying this role satisfies any role requirement: it is the single
# platform-wide role (SECURITY.md §2), admitting the user everywhere.
PLATFORM_WIDE_ROLE = RoleEnum.SUPER_ADMIN


def extract_bearer_token(authorization: str | None) -> str | None:
    """Return the token from an `Authorization: Bearer <token>` header, else None.

    The scheme match is case-insensitive. A header holding more than one token
    is malformed and rejected rather than silently truncated.
    """
    if not authorization:
        return None
    scheme, _, remainder = authorization.partition(" ")
    if not remainder or scheme.lower() != BEARER_SCHEME.lower():
        return None
    if " " in remainder:
        return None
    return remainder


def role_satisfies(user_role: RoleEnum, allowed: Collection[RoleEnum]) -> bool:
    """Whether a role passes a role requirement.

    The platform-wide role (SUPER_ADMIN) satisfies any guard; no other role is
    elevated. `allowed` may be empty — only the platform-wide role passes then.
    """
    return user_role is PLATFORM_WIDE_ROLE or user_role in allowed


# Argon2id via pwdlib's recommended configuration. Hashes are never persisted:
# registration uses them as a transient validation step only.
_PASSWORD_HASHER = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return _PASSWORD_HASHER.verify(password, hashed_password)
