"""Tests for the role enum and the User model metadata."""

from sqlalchemy import Uuid

from app.models.enums import RoleEnum
from app.models.user import User


def test_role_enum_values() -> None:
    assert [role.value for role in RoleEnum] == [
        "SUPER_ADMIN",
        "PG_OWNER",
        "MANAGER",
        "STAFF",
        "TENANT",
    ]


def test_role_enum_is_str_enum() -> None:
    assert RoleEnum("SUPER_ADMIN") is RoleEnum.SUPER_ADMIN
    assert RoleEnum.MANAGER.value == "MANAGER"


def test_user_table_name() -> None:
    assert User.__tablename__ == "users"


def test_user_primary_key_is_uuid() -> None:
    pk = User.__table__.primary_key.columns.values()[0]
    assert pk.name == "id"
    assert isinstance(pk.type, Uuid)


def test_user_has_unique_email_and_phone() -> None:
    unique = {
        constraint.columns.values()[0].name
        for constraint in User.__table__.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }
    assert "email" in unique
    assert "phone" in unique


def test_user_role_enum_type() -> None:
    role = User.__table__.c["role"]
    assert role.type.name == "user_role"
    assert list(role.type.enums) == [r.value for r in RoleEnum]


def test_user_required_columns() -> None:
    nullable = {col.name for col in User.__table__.columns if col.nullable}
    assert "email" not in nullable
    assert "full_name" not in nullable
    assert "role" not in nullable
    assert "is_active" not in nullable
    assert "is_verified" not in nullable
    assert "phone" in nullable


def test_user_timestamps_present() -> None:
    assert "created_at" in User.__table__.columns
    assert "updated_at" in User.__table__.columns


def test_user_role_indexed() -> None:
    indexed = {idx.columns.keys()[0] for idx in User.__table__.indexes}
    assert "role" in indexed


def test_user_has_no_password_auth_fields() -> None:
    columns = set(User.__table__.columns.keys())
    assert "password" not in columns
    assert "password_hash" not in columns
    assert "auth_user_id" not in columns