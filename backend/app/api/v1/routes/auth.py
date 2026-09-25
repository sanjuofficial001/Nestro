"""Registration and current-user endpoints.

- Register: self-service tenant registration that creates only the application
  user record; no password, token, or session material is issued or stored.
- Auth me: returns the authenticated Nestro user profile. The JWT proves
  identity; role and active status come from the database row, never the token.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import RegisterRequest, RegisterResponse
from app.schemas.auth_me import AuthMeResponse
from app.services.auth_service import AuthService

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