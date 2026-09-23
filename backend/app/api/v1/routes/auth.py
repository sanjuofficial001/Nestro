"""Registration endpoints.

Self-service tenant registration: creates only the application user record;
no password, token, or session material is issued or stored.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import RegisterRequest, RegisterResponse
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