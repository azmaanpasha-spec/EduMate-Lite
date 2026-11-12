"""
Database setup: SQLAlchemy engine, session factory and helpers.
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import BACKEND_DIR, get_settings


def _resolve_sqlite_url(url: str) -> str:
    """Make relative SQLite paths relative to the backend folder.

    Without this, `sqlite:///./edumate.db` would create the database in
    whichever folder uvicorn happened to be started from.
    """
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith(prefix + "/"):
        relative = url[len(prefix):]
        if relative != ":memory:" and not (len(relative) > 1 and relative[1] == ":"):
            return prefix + str((BACKEND_DIR / relative).resolve()).replace("\\", "/")
    return url


DATABASE_URL = _resolve_sqlite_url(get_settings().database_url)

engine = create_engine(
    DATABASE_URL,
    # Needed because FastAPI may use the connection from different threads
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _record):
    """SQLite ignores foreign keys unless this pragma is switched on."""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    """Create all tables if they do not exist yet."""
    from . import models  # noqa: F401  (registers the models with Base)

    Base.metadata.create_all(bind=engine)


def get_db():
    """FastAPI dependency that yields a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
