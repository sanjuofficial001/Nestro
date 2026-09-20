"""JWT verification tests — the token-validation seam (SECURITY.md §1).

Fully offline and deterministic: RS256 tokens are signed locally with the test
keypair and verified through the real `app.core.auth` engine. Every rejection —
malformed, expired, wrong issuer, wrong audience, wrong signature — surfaces as
the same generic `AuthenticationError`, so clients can never tell which check
failed (SECURITY.md §1: uniform 401 that does not leak its cause).
"""

import datetime as _dt

import pytest

from app.core.auth import get_verifier
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
