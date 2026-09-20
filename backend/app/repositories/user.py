"""Data access for users. Repository layer only — no services, no endpoints."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.user import UserCreate


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._session.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        return self._session.scalar(select(User).where(User.email == email))

    def exists_by_email(self, email: str) -> bool:
        return self._session.scalar(
            select(User.id).where(User.email == email).limit(1)
        ) is not None

    def create(self, data: UserCreate) -> User:
        user = User(**data.model_dump())
        self._session.add(user)
        self._session.commit()
        self._session.refresh(user)
        return user