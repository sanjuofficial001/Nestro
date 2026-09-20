"""Tests for application construction, lifespan, and exception handling."""

from fastapi.testclient import TestClient

from app.core.exceptions import AppException
from app.main import app, create_application


def test_create_application_metadata() -> None:
    application = create_application()
    assert application.title == "Nestro"
    assert application.version == "0.1.0"
    assert application.router.lifespan_context is not None


def test_application_starts_and_serves() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "environment": "development"}


def test_app_exception_handler() -> None:
    application = create_application()

    def boom() -> None:
        raise AppException(status_code=403, detail="Forbidden")

    application.add_api_route("/boom", boom, methods=["GET"])

    with TestClient(application) as client:
        response = client.get("/boom")
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}