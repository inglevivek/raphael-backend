from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
import os

Base = declarative_base()

# These are lazily initialized on first use so that importing this module
# without DATABASE_URL set (e.g. during tests or import-time checks) does not crash.
_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        url = os.environ.get("DATABASE_URL")
        if not url:
            raise RuntimeError(
                "DATABASE_URL environment variable is not set. "
                "Please configure it before making database calls."
            )
        _engine = create_engine(url)
    return _engine


def _get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _SessionLocal


class _LazySessionLocal:
    """Proxy that behaves like SessionLocal but initialises the engine lazily."""

    def __call__(self, *args, **kwargs):
        return _get_session_local()(*args, **kwargs)

    def __enter__(self):
        self._session = _get_session_local()()
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                self._session.rollback()
        finally:
            self._session.close()


SessionLocal = _LazySessionLocal()

# Expose engine for Alembic and other callers
engine = property(lambda self: _get_engine())


def get_db():
    """FastAPI dependency that yields a database session."""
    session = _get_session_local()()
    try:
        yield session
    finally:
        session.close()
