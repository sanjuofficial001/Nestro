"""Shared fixtures for the authentication and authorization test suites.

Fully offline and deterministic:

- rsa_keypair   - a fresh locally generated RSA keypair (cryptography).
- auth_env      - pins that keypair plus a test issuer/audience into the JWT
                  settings through the cacheable get_settings / get_verifier
                  seams, then restores the caches on teardown.
- make_token    - RS256-signs a token with the test private key (PyJWT),
                  carrying a sub, an email claim, and an optional role hint.
- jwk_client    - a fake duck-typed PyJWKClient resolving tokens to the test
                  public key, for exercising the JWKS verification path offline.
- db_session_factory / db_session - a fresh StaticPool-backed in-memory SQLite
                  session per test, with all models registered.
- create_user   - seeds a platform User that get_current_user resolves by email.
- auth_app      - a throwaway FastAPI app with guarded routes built on the real
                  app.api.deps guards, wired to the in-memory DB via
                  dependency_overrides[get_db]. Guards return the caller so
                  tests can assert identity and role resolution (and rejections)
                  through the exact FastAPI dependency path real routers use.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import uuid4

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_current_user, require_any_role, require_role
from app.core.auth import get_verifier
from app.core.config import get_settings
from app.core.handlers import register_exception_handlers
from app.db.base import Base
from app.db.session import get_db
from app.models.enums import RoleEnum
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate

TEST_ISSUER = "test-issuer"
TEST_AUDIENCE = "test-audience"
TEST_ALGORITHM = "RS256"


@pytest.fixture
def rsa_keypair() -> tuple[str, str]:
    """A fresh RSA keypair: (private_pem, public_pem)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


@pytest.fixture
def auth_env(
    monkeypatch: pytest.MonkeyPatch,
    rsa_keypair: tuple[str, str],
) -> Iterator[None]:
    """Pin the JWT settings to the test keypair/issuer/audience via the seams."""
    _, public_pem = rsa_keypair
    monkeypatch.setenv("JWT_VERIFICATION_KEY", public_pem)
    monkeypatch.setenv("JWT_ISSUER", TEST_ISSUER)
    monkeypatch.setenv("JWT_AUDIENCE", TEST_AUDIENCE)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    get_settings.cache_clear()
    get_verifier.cache_clear()
    yield
    get_settings.cache_clear()
    get_verifier.cache_clear()


@pytest.fixture
def make_token(rsa_keypair: tuple[str, str]) -> Callable[..., str]:
    """Factory building an RS256 token signed with the test private key."""

    def _make(
        *,
        sub: str | None = None,
        email: str = "user@example.com",
        omit_email: bool = False,
        omit_exp: bool = False,
        role: RoleEnum | None = None,
        issuer: str = TEST_ISSUER,
        audience: str = TEST_AUDIENCE,
        expires_in: timedelta = timedelta(hours=1),
        **overrides: object,
    ) -> str:
        now = datetime.now(UTC)
        payload: dict[str, object] = {
            "sub": sub or str(uuid4()),
            "iss": issuer,
            "aud": audience,
            "iat": now,
        }
        if not omit_exp:
            payload["exp"] = now + expires_in
        if not omit_email:
            payload["email"] = email
        if role is not None:
            payload["role"] = role.value
        payload.update(overrides)
        return pyjwt.encode(payload, rsa_keypair[0], algorithm=TEST_ALGORITHM)

    return _make


class _FakeSigningKey:
    def __init__(self, key: str) -> None:
        self.key = key


class _FakeJwksClient:
    """A duck-typed PyJWKClient resolving every token to a fixed public key."""

    def __init__(self, key: str) -> None:
        self._key = key

    def get_signing_key_from_jwt(self, token: str) -> _FakeSigningKey:
        return _FakeSigningKey(self._key)


@pytest.fixture
def jwk_client(rsa_keypair: tuple[str, str]) -> _FakeJwksClient:
    """A fake JWKS client resolving tokens to the test public key."""
    return _FakeJwksClient(rsa_keypair[1])


@pytest.fixture
def db_session_factory() -> Iterator[sessionmaker[Session]]:
    """A fresh StaticPool-backed in-memory SQLite session factory per test."""
    import app.models  # noqa: F401  # registers every model on Base.metadata

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_session_factory: sessionmaker[Session]) -> Iterator[Session]:
    with db_session_factory() as session:
        yield session


@pytest.fixture
def create_user(db_session: Session) -> Callable[..., User]:
    def _create(
        *,
        email: str,
        role: RoleEnum,
        is_active: bool = True,
        is_verified: bool = True,
    ) -> User:
        user = UserRepository(db_session).create(
            UserCreate(email=email, phone=None, full_name="Test User", role=role),
        )
        user.is_active = is_active
        user.is_verified = is_verified
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@dataclass
class AuthHarness:
    """Guarded app + the in-memory DB factory it is wired to."""

    client: TestClient
    factory: sessionmaker[Session]

    def seed(
        self,
        *,
        email: str,
        role: RoleEnum,
        is_active: bool = True,
        is_verified: bool = True,
    ) -> User:
        with self.factory() as session:
            user = UserRepository(session).create(
                UserCreate(email=email, phone=None, full_name="Test User", role=role),
            )
            user.is_active = is_active
            user.is_verified = is_verified
            session.commit()
            session.refresh(user)
            return user


@pytest.fixture
def auth_app(
    db_session_factory: sessionmaker[Session],
    auth_env: None,
) -> Iterator[AuthHarness]:
    """A throwaway app exercising the real deps guards, backed by the in-memory DB."""

    def override_get_db() -> Iterator[Session]:
        with db_session_factory() as session:
            yield session

    app = FastAPI()
    app.dependency_overrides[get_db] = override_get_db
    register_exception_handlers(app)

    @app.get("/me")
    def me(user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
        return {"email": user.email}

    @app.get("/admin")
    def admin(
        user: Annotated[User, Depends(require_role(RoleEnum.SUPER_ADMIN))],
    ) -> dict[str, str]:
        return {"email": user.email, "role": user.role.value}

    @app.get("/owner-ops")
    def owner_ops(
        user: Annotated[
            User,
            Depends(require_any_role(RoleEnum.PG_OWNER, RoleEnum.MANAGER)),
        ],
    ) -> dict[str, str]:
        return {"email": user.email, "role": user.role.value}

    with TestClient(app) as client:
        yield AuthHarness(client=client, factory=db_session_factory)
