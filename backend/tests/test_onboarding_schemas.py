"""Tests for the onboarding request/response schemas."""

import pytest
from pydantic import ValidationError

from app.models.enums import OrganizationRoleEnum
from app.schemas.onboarding import OnboardingRequest, OnboardingResponse


def test_valid_request() -> None:
    request = OnboardingRequest(
        organization_name="My PG",
        organization_slug="my-pg",
    )
    assert request.organization_name == "My PG"
    assert request.organization_slug == "my-pg"


def test_uppercase_slug_rejected() -> None:
    with pytest.raises(ValidationError, match="slug must be lowercase"):
        OnboardingRequest(organization_name="My PG", organization_slug="My-PG")


def test_slug_with_spaces_rejected() -> None:
    with pytest.raises(ValidationError, match="slug must not contain spaces"):
        OnboardingRequest(organization_name="My PG", organization_slug="my pg")


def test_extra_field_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        OnboardingRequest(
            organization_name="My PG",
            organization_slug="my-pg",
            extra="fields",
        )


def test_response_shape() -> None:
    response = OnboardingResponse(
        organization_id="8f9a2854-8408-4bae-89e7-37831ab2163b",
        organization_name="My PG",
        organization_slug="my-pg",
        membership_id="8f9a2854-8408-4bae-89e7-37831ab2163c",
        role=OrganizationRoleEnum.OWNER,
    )
    assert response.role is OrganizationRoleEnum.OWNER
    assert str(response.organization_id) == "8f9a2854-8408-4bae-89e7-37831ab2163b"