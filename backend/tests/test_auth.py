"""JWT verification tests — the token-validation seam (SECURITY.md §1).

Fully offline and deterministic: RS256 tokens are signed locally with the test
keypair and verified through the real `app.core.auth` engine. Every rejection —
malformed, expired, wrong issuer, wrong audience, wrong signature, wrong
algorithm, missing claims — surfaces as the same generic `AuthenticationError`,
so clients can never tell which check failed (SECURITY.md §1: uniform 401 that
does not leak its cause).

The JWKS path is exercised through a fake duck-typed key client, so no network
is involved.
"""

import datetime as _dt
from datetime import UTC, datetime

import jwt
import pytest

from app.core.auth import JwtVerifier, get_verifier
from app.core.exceptions import AuthenticationError
from app.core.security import extract_bearer_token

UTC_HOUR = _dt.timedelta(hours=1)


def test_extract_bearer_token_parses_valid_header() -> None:
    assert extract_bearer_token("Bearer abc.def.ghi") == "abc.def.ghi"


def test_extract_bearer_token_rejects_non_bearer_scheme() -> None:
    assert extract_bearer_token("Basic abc.def.ghi") is None


def test_extract_bearer_token_rejects_missing_header() -> None:
    assert extract_bearer_token("") is None


def test_extract_bearer_token_rejects_blank_credentials() -> None:
    assert extract_bearer_token("Bearer    ") is None


def test_verifier_accepts_valid_token(auth_env: None, make_token) -> None:
    claims = get_verifier().verify(make_token())
    assert claims.sub is not None
    assert claims.email == "user@example.com"


def test_verifier_accepts_valid_token_via_jwks(auth_env: None, make_token, jwk_client) -> None:
    verifier = JwtVerifier(
        jwks_client=jwk_client,
        issuer="test-issuer",
        audience="test-audience",
    )
    claims = verifier.verify(make_token())
    assert claims.email == "user@example.com"


def test_verifier_rejects_malformed_token(auth_env: None) -> None:
    with pytest.raises(AuthenticationError):
        get_verifier().verify("not-a-jwt")


def test_verifier_rejects_expired_token(auth_env: None, make_token) -> None:
    with pytest.raises(AuthenticationError):
        get_verifier().verify(make_token(expires_in=-UTC_HOUR))


def test_verifier_rejects_wrong_issuer(auth_env: None, make_token) -> None:
    with pytest.raises(AuthenticationError):
        get_verifier().verify(make_token(issuer="attacker-issuer"))


def test_verifier_rejects_wrong_audience(auth_env: None, make_token) -> None:
    with pytest.raises(AuthenticationError):
        get_verifier().verify(make_token(audience="attacker-audience"))


def test_verifier_rejects_tampered_signature(auth_env: None, make_token) -> None:
    with pytest.raises(AuthenticationError):
        get_verifier().verify(f"{make_token()[:-3]}AAA")


def test_verifier_rejects_hmac_algorithm(auth_env: None) -> None:
    now = datetime.now(UTC)
    hs256_token = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "iss": "test-issuer",
            "aud": "test-audience",
            "iat": now,
            "exp": now + UTC_HOUR,
            "email": "user@example.com",
        },
        "attacker-inferior-secret-0123456789abcdef",
        algorithm="HS256",
    )
    with pytest.raises(AuthenticationError):
        get_verifier().verify(hs256_token)


def test_verifier_rejects_missing_exp(auth_env: None, make_token) -> None:
    with pytest.raises(AuthenticationError):
        get_verifier().verify(make_token(omit_exp=True))


def test_verifier_rejects_missing_email_claim(auth_env: None, make_token) -> None:
    with pytest.raises(AuthenticationError):
        get_verifier().verify(make_token(omit_email=True))


def test_verifier_rejects_jwks_key_lookup_failure(auth_env: None, make_token) -> None:
    class _Unresolvable:
        def get_signing_key_from_jwt(self, token: str) -> object:
            raise jwt.exceptions.PyJWKClientError("no matching key")

    verifier = JwtVerifier(
        jwks_client=_Unresolvable(),
        issuer="test-issuer",
        audience="test-audience",
    )
    with pytest.raises(AuthenticationError):
        verifier.verify(make_token())


def test_verifier_rejects_blank_email_claim(auth_env: None, make_token) -> None:
    with pytest.raises(AuthenticationError):
        get_verifier().verify(make_token(email="   "))


def test_verifier_rejects_missing_signature(auth_env: None, make_token) -> None:
    token = make_token()
    with pytest.raises(AuthenticationError):
        get_verifier().verify(token[: token.rfind(".")])


def test_verifier_unconfigured_raises_not_configured() -> None:
    verifier = JwtVerifier(key="", issuer="test-issuer", audience="test-audience")
    with pytest.raises(AuthenticationError):
        verifier.verify("any.token.value")