"""Registration business logic. First service layer.

`AuthService.register_user` owns the registration flow: duplicate checks,
password hashing (transient — hashes are never persisted), and the creation
of the application user record. No login, no tokens.
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.enums import RoleEnum
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserCreate


class AuthService:
    def __init__(self, session: Session) -> None:
        self._repo = UserRepository(session)

    def register_user(self, data: RegisterRequest) -> User:
        if self._repo.get_by_email(data.email) is not None:
            raise ValueError("email already exists")

        # Hash then discard: no credential material is stored on the user row.
        hash_password(data.password)

        try:
            user = self._repo.create_user(
                UserCreate(
                    email=data.email,
                    phone=data.phone,
                    full_name=data.full_name,
                    role=RoleEnum.TENANT,
                )
            )
        except IntegrityError:
            if self._repo.get_by_email(data.email) is not None:
                raise ValueError("email already exists") from None
            raise

        return user