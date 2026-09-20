"""Tests for the database layer: engine, session, metadata, and mixins.

SQLite is used throughout so no external PostgreSQL server is required.
"""

import time
from datetime import datetime

from sqlalchemy import Engine, Integer, String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.db.base import NAMING_CONVENTION, Base
from app.db.mixins import TimestampMixin
from app.db.session import (
    SessionLocal,
    create_engine_instance,
    create_session_factory,
    get_db,
    get_engine,
)

TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


class TempModel(TimestampMixin, Base):
    __tablename__ = "temp_model"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)


def test_create_engine_instance() -> None:
    engine = create_engine_instance(TEST_DATABASE_URL)
    assert isinstance(engine, Engine)
    assert engine.url.get_backend_name() == "sqlite"
    assert engine.pool._pre_ping is True
    assert engine.pool._recycle == 1800


def test_get_engine_wired_to_settings() -> None:
    engine = get_engine()
    assert engine is get_engine()
    assert engine.url.get_backend_name() == "postgresql"


def test_session_factory_runs_select() -> None:
    engine = create_engine_instance(TEST_DATABASE_URL)
    factory = create_session_factory(engine)
    with factory() as session:
        assert session.execute(select(1)).scalar() == 1


def test_get_db_yields_session() -> None:
    sessions = get_db()
    session = next(sessions)
    try:
        assert isinstance(session, Session)
    finally:
        sessions.close()


def test_session_factory_configuration() -> None:
    assert SessionLocal.kw["autoflush"] is False
    assert SessionLocal.kw["autocommit"] is False
    assert SessionLocal.kw["expire_on_commit"] is False


def test_base_names_naming_convention() -> None:
    assert Base.metadata.naming_convention is not None
    convention = Base.metadata.naming_convention
    assert "ix" in convention and "uq" in convention and "ck" in convention
    assert "fk" in convention and "pk" in convention
    assert convention == NAMING_CONVENTION


def test_timestamp_mixin_populates_and_refreshes() -> None:
    engine = create_engine_instance(TEST_DATABASE_URL)
    TempModel.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            row = TempModel(name="alpha")
            session.add(row)
            session.commit()
            row_id = row.id
            created_at = row.created_at
            updated_at = row.updated_at
        assert isinstance(created_at, datetime)
        assert isinstance(updated_at, datetime)
        time.sleep(1.1)
        with factory() as session:
            row = session.get(TempModel, row_id)
            assert row is not None
            row.name = "beta"
            session.commit()
            assert row.updated_at > created_at
    finally:
        TempModel.metadata.drop_all(engine)