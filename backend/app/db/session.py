"""Database engine and session management.

The engine is created lazily — calling `get_engine()` for the first time
constructs it from settings; `create_engine()` itself opens no connection until
first use. Sessions are produced through the `sessionmaker` in `SessionLocal`;
`get_db()` yields one per request lifecycle for future route wiring.
"""

from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine: Engine | None = None


def create_engine_instance(database_url: str | None = None) -> Engine:
    """Build an engine for the given URL (or settings.database_url).

    Safe FastAPI defaults: pool_pre_ping, a 30-minute pool recycle, and a short
    connection timeout on PostgreSQL so startup failures surface quickly.
    """
    url = database_url or get_settings().database_url
    url_obj = make_url(url)

    kwargs: dict = {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "connect_args": {},
    }
    if url_obj.get_backend_name() in {"postgresql", "postgres"}:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
        kwargs["connect_args"]["connect_timeout"] = 5
    elif url_obj.get_backend_name() == "sqlite":
        kwargs["connect_args"]["check_same_thread"] = False

    return create_engine(url, **kwargs)


def get_engine() -> Engine:
    """Return the lazily-initialized application engine."""
    global _engine
    if _engine is None:
        _engine = create_engine_instance()
    return _engine


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine or get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


SessionLocal = create_session_factory()


def get_db() -> Iterator[Session]:
    """Yield a database session and always close it.

    Intended for FastAPI dependency injection; not wired to any route yet.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()