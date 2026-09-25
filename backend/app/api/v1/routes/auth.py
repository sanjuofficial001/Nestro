"""Registration, current-user, and onboarding endpoints.

- Register: self-service tenant registration that creates only the application
  user record; no password, token, or session material is issued or stored.
- Auth me: returns the authenticated Nestro user profile. The JWT proves
  identity; role and active status come from the database row, never the token.
- Onboard: one-time bootstrap that creates the user's first organization and
  OWNER membership. No property creation, no joining existing organizations.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import RegisterRequest, RegisterResponse
from app.schemas.auth_me import AuthMeResponse
from app.schemas.onboarding import OnboardingRequest, OnboardingResponse
from app.services.auth_service import AuthService
from app.services.onboarding_service import OnboardingService

router = APIRouter(tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register(
    payload: RegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> RegisterResponse:
    try:
        user = AuthService(db).register_user(payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return RegisterResponse.model_validate(user)


@router.get("/me", response_model=AuthMeResponse)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> AuthMeResponse:
    return current_user


@router.post("/onboard", response_model=OnboardingResponse, status_code=201)
def onboard(
    payload: OnboardingRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> OnboardingResponse:
    try:
        organization, member = OnboardingService(db).onboard_user(current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    return OnboardingResponse(
        organization_id=organization.id,
        organization_name=organization.name,
        organization_slug=organization.slug,
        membership_id=member.id,
        role=member.role,
    )