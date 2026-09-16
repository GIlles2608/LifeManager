"""Root pytest configuration.

Provides the testcontainers-backed PostgreSQL fixture used by the
integration suite (see ADR-0002). Unit tests mock the SQLAlchemy session
and do not depend on anything defined here.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from testcontainers.community.postgres import PostgresContainer

from lifemanager.core.config.settings import settings

_ALEMBIC_INI = settings.app.project_root / "alembic.ini"


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """One ephemeral PostgreSQL container for the whole test session."""
    with PostgresContainer("postgres:16-alpine") as container:
        yield container


@pytest.fixture(scope="session")
def db_engine(postgres_container: PostgresContainer) -> Iterator[Engine]:
    """Engine bound to the container, schema created via Alembic migrations."""
    url = postgres_container.get_connection_url()

    alembic_cfg = Config(str(_ALEMBIC_INI))
    alembic_cfg.attributes["sqlalchemy.url"] = url
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(url)
    yield engine
    engine.dispose()
