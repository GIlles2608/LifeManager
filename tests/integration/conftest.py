"""Integration test fixtures: per-test isolation, minimal seed data, and the
truncate fallback documented in ADR-0002.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from lifemanager.core.models.base import Base
from lifemanager.finance.models import Account, AccountType, Category, GrandType


@pytest.fixture
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Default isolation: a connection-bound transaction rolled back after
    each test. Session commits use a SAVEPOINT so they don't end the outer
    transaction — see SQLAlchemy's "joining a session into an external
    transaction" pattern. Code under test that commits explicitly and relies
    on that commit surviving still needs the `truncate_tables` fallback.
    """
    connection = db_engine.connect()
    transaction = connection.begin()

    session_factory = sessionmaker(bind=connection, join_transaction_mode="create_savepoint")
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def seeded_session(db_session: Session) -> Session:
    """`db_session` pre-populated with the minimal reference data most
    integration tests need: one active account and one category."""
    account = Account(name="Compte courant", type=AccountType.COURANT, initial_balance=0)
    category = Category(name="Divers", grand_type=GrandType.DEPENSE)
    db_session.add_all([account, category])
    db_session.flush()
    return db_session


@pytest.fixture
def truncate_tables(db_engine: Engine) -> Iterator[None]:
    """Fallback isolation for tests whose code under test commits explicitly,
    which breaks `db_session`'s rollback. Truncates every table after the
    test runs. Exception mechanism, not the default — see ADR-0002.
    """
    yield
    with db_engine.connect() as connection:
        table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
        connection.exec_driver_sql(f"TRUNCATE {table_names} RESTART IDENTITY CASCADE")
        connection.commit()
