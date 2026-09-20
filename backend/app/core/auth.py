"""JWT verification layer.

Verification only — nothing here creates or signs tokens (that is Supabase
Auth's job). Tokens are decoded with PyJWT using RS256, the only algorithm
Supabase signs with; `exp`, `aud`, and `iss` are enforced. Every rejection
surfaces as the same generic AuthenticationError so clients cannot tell an
expired token apart from a malformed one.

# ponytail: the verification key is a statically-configured PEM; swap
# `get_verifier` for a live JWKS fetch (network) once a real Supabase project
# is wired up — the seams (deps, tests) do not change.
"""

from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import SUPPORTED_JWT_ALGORITHMS
from app.models.enums import RoleEnum


@dataclass(frozen=True)
class TokenClaims:
    """Verified identity extracted from a token.

    `sub` is the platform user UUID. `role`, when present in the token, is a
    fast-path hint only — the database row is the authority.
    """

    sub: UUID
    role: RoleEnum | None


class JwtVerifier:
    def __init__(
        self,
        *,
        key: str,
        issuer: str,
        audience: str,
        algorithms: frozenset[str] = SUPPORTED_JWT_ALGORITHMS,
    ) -> None:
        self._key = key.strip()
        self._issuer = issuer
        self._audience = audience
        self._algorithms = list(algorithms)

    def verify(self, token: str) -> TokenClaims:
        if not self._key:
            raise AuthenticationError(detail="JWT verification key not configured")
        try:
            payload = jwt.decode(
                token,
                self._key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp"]},
            )
        except jwt.PyJWTError:
            raise AuthenticationError() from None
        try:
            sub = UUID(payload["sub"])
        except (KeyError, TypeError, ValueError):
            raise AuthenticationError() from None
        return TokenClaims(sub=sub, role=self._extract_role(payload.get("role")))

    @staticmethod
    def _extract_role(claim: object) -> RoleEnum | None:
        if claim is None:
            return None
        try:
            return RoleEnum(claim)
        except (TypeError, ValueError):
            raise AuthenticationError() from None


@lru_cache
def get_verifier() -> JwtVerifier:
    """Default verifier built from settings at call time (cacheable per env)."""
    settings = get_settings()
    return JwtVerifier(
        key=settings.jwt_verification_key,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )