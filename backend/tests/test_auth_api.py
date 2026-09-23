"""Tests for the registration endpoint over the in-memory database."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app

REGISTER_PAYLOAD = {
    "email": "user@example.com",
    "phone": "9876543210",
    "full_name": "John Doe",
    "password": "StrongPass123",
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    import app.models  # noqa: F401  # registers every model on Base.metadata

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.pop(get_db)
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_register_success(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "user@example.com"
    assert body["phone"] == "9876543210"
    assert body["full_name"] == "John Doe"
    assert body["id"]
    assert body["created_at"]


def test_register_duplicate_email_conflict(client: TestClient) -> None:
    assert client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD).status_code == 201
    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "phone": "9999999999"},
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "email already exists"}


def test_register_invalid_payload_unprocessable(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={**REGISTER_PAYLOAD, "password": "short"},
    )
    assert response.status_code == 422