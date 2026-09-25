"""JWT verification layer.

Verification only — nothing here creates or signs tokens (that is Supabase
Auth's job). Tokens are decoded with PyJWT using RS256, the only algorithm
Supabase signs with; `exp`, `aud`, and `iss` are enforced, and the verified
`email` claim is the identity the dependencies resolve a Nestro user by.

Public keys come from one of two contexts:

- a statically-configured PEM (`JWT_VERIFICATION_KEY`) for offline dev and
  tests; or
- the Supabase project's JWKS endpoint (PyJWT's `PyJWKClient`), fetched and
  cached by the client when `SUPABASE_URL` is configured.

Every rejection surfaces as the same generic AuthenticationError so clients
cannot tell an expired token apart from a malformed one. Network I/O happens
only inside the cached `get_verifier()` singleton — never in route dependencies.
"""

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol
from uuid import UUID

import jwt
from jwt import PyJWKClient

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError
from app.core.security import SUPPORTED_JWT_ALGORITHMS
from app.models.enums import RoleEnum

# Sentinel default: an unset issuer derives from SUPABASE_URL when configured.
_PLACEHOLDER_ISSUER = "supabase"


class JwksKey(Protocol):
    """A resolved signing key exposing its PEM form."""

    @property
    def key(self) -> str: ...


class JwksClient(Protocol):
    """Anything able to resolve a token to its signing key (PyJWKClient's shape)."""

    def get_signing_key_from_jwt(self, token: str) -> JwksKey: ...


@dataclass(frozen=True)
class TokenClaims:
    """Verified identity extracted from a token.

    `sub` is the Supabase auth user UUID — a different namespace from Nestro
    user ids, so identity is resolved by `email`. `role`, when present in the
    token, is a fast-path hint only — the database row is the authority.
    """

    sub: UUID
    email: str
    role: RoleEnum | None


class JwtVerifier:
    def __init__(
        self,
        *,
        key: str = "",
        jwks_client: JwksClient | None = None,
        issuer: str,
        audience: str,
        algorithms: frozenset[str] = SUPPORTED_JWT_ALGORITHMS,
    ) -> None:
        self._static_key = key.strip()
        self._jwks_client = jwks_client
        self._issuer = issuer
        self._audience = audience
        self._algorithms = list(algorithms)

    def verify(self, token: str) -> TokenClaims:
        signing_key = self._resolve_key(token)
        if not signing_key:
            raise AuthenticationError(detail="JWT verification key not configured")
        try:
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=self._algorithms,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp"]},
            )
        except jwt.PyJWTError:
            raise AuthenticationError() from None
        try:
            sub = UUID(payload["sub"])
            email = payload["email"]
            if not isinstance(email, str) or not email.strip():
                raise KeyError("email")
            email = email.strip()
        except (KeyError, TypeError, ValueError):
            raise AuthenticationError() from None
        return TokenClaims(sub=sub, email=email, role=self._extract_role(payload.get("role")))

    def _resolve_key(self, token: str) -> str | None:
        if self._jwks_client is not None:
            try:
                return self._jwks_client.get_signing_key_from_jwt(token).key
            except (jwt.PyJWTError, AttributeError, TypeError, ValueError):
                raise AuthenticationError() from None
        return self._static_key or None

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
    """Default verifier built from settings at call time (cacheable per env).

    With `SUPABASE_URL` set, keys come from the project JWKS endpoint and the
    issuer default aligns to Supabase's; otherwise the static verification key
    (dev/test) is used with the explicitly configured issuer.
    """
    settings = get_settings()
    if settings.supabase_url:
        base = settings.supabase_url.rstrip("/")
        return JwtVerifier(
            jwks_client=PyJWKClient(f"{base}/auth/v1/.well-known/jwks.json"),
            issuer=(
                settings.jwt_issuer
                if settings.jwt_issuer != _PLACEHOLDER_ISSUER
                else f"{base}/auth/v1"
            ),
            audience=settings.jwt_audience,
        )
    return JwtVerifier(
        key=settings.jwt_verification_key,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )