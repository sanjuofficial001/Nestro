"""Data access for users. Repository layer only — no services, no endpoints."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        normalized = email.strip().lower()
        return self._session.scalar(
            select(User).where(func.lower(User.email) == normalized)
        )

    def exists_by_email(self, email: str) -> bool:
        normalized = email.strip().lower()
        return self._session.scalar(
            select(User.id).where(func.lower(User.email) == normalized).limit(1)
        ) is not None

    def create(self, data: UserCreate) -> User:
        user = User(**data.model_dump())
        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        return user

    def create_user(self, data: UserCreate) -> User:
        user = User(**data.model_dump())
        self._session.add(user)
        try:
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise
        self._session.refresh(user)
        return user