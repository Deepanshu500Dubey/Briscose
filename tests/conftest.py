"""Shared pytest fixtures.

Tests run against the already-migrated database pointed to by DATABASE_URL
(see README: `alembic upgrade head` before `pytest`), matching Phase 1's
own verification sequence. Each test runs inside an outer transaction that
is rolled back afterwards, so tests are isolated without needing a second
database or any test-specific infrastructure.
"""
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import Session, sessionmaker

from app.core.rate_limit import limiter
from app.db.session import engine, get_db
from app.main import app

# Rate limiting on /auth/login and /auth/refresh is per-source-IP, and
# Starlette's TestClient always presents the same fake address — so without
# this, the whole suite would share one bucket and start failing partway
# through on 429s that have nothing to do with the behaviour under test.
limiter.enabled = False


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    connection = engine.connect()
    outer_transaction = connection.begin()

    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = TestSessionLocal()

    # Nest all ORM commits inside a SAVEPOINT so `db.commit()` calls made by
    # application code don't end the outer transaction we roll back below.
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans) -> None:
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def _get_db_override() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
