"""Test-wide environment, applied before any app module imports settings.

Disables LLM rate-limit pacing and backoff sleeps so tests exercising the
resilience layer's fallback paths stay fast and deterministic (os.environ
takes precedence over .env in pydantic-settings).
"""
import os

os.environ.setdefault("LLM_REQUESTS_PER_MINUTE", "0")
os.environ.setdefault("LLM_BACKOFF_BASE_SECONDS", "0")

import pytest
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

import app.db.session as db_session_module


@pytest.fixture(autouse=True)
def db_transaction():
    """Wraps every test in one outer transaction rolled back at teardown,
    so the suite stops leaving rows behind in the shared dev Postgres DB
    (see CLAUDE.md's test_seed.py accumulation note - this is the fix for
    it). Standard SQLAlchemy "join a session into an external transaction"
    recipe: a SAVEPOINT is restarted after every commit so app code that
    calls db.commit() (every route/runner branch does) ends the savepoint,
    not the outer transaction.
    """
    connection = db_session_module.engine.connect()
    outer_transaction = connection.begin()
    factory = sessionmaker(autocommit=False, autoflush=False, bind=connection)

    nested = connection.begin_nested()

    @event.listens_for(factory, "after_transaction_end")
    def _restart_savepoint(session, trans):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    db_session_module._session_factory_override = factory
    try:
        yield
    finally:
        db_session_module._session_factory_override = None
        outer_transaction.rollback()
        connection.close()
