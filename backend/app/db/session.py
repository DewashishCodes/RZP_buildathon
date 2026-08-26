from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
_default_session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# tests/conftest.py's db_transaction fixture swaps this to a factory bound
# to one per-test connection+transaction (rolled back at teardown), so
# every SessionLocal() call across the whole call graph - including
# modules that did `from app.db.session import SessionLocal` at collection
# time, before any fixture ran - joins the same transaction. SessionLocal
# is a plain function rather than a sessionmaker instance so this lookup
# happens at call time, not at import time.
_session_factory_override: sessionmaker | None = None


def SessionLocal(*args, **kwargs):
    factory = _session_factory_override or _default_session_factory
    return factory(*args, **kwargs)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
