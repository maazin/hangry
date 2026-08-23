"""Test fixtures.

Tests run against a real Postgres (`hangry_test`), not SQLite. The schema
leans on JSONB, text[] and native uuid, and a filter whose whole job is to
keep `null` distinct from `"no"` should not be validated on a database with
different null semantics than production.
"""

import os

# Must be set before anything imports app.config and builds the engine.
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://hangry:hangry@localhost:5433/hangry_test")
os.environ["TESTING"] = "1"

# The admin connection is derived from DATABASE_URL rather than hardcoded, so
# the suite follows the database wherever it is bound. Hardcoding a port means
# the tests only run when Postgres happens to sit on that one.
_url = os.environ["DATABASE_URL"]
ADMIN_URL = _url.replace("+asyncpg", "").rsplit("/", 1)[0] + "/postgres"

import asyncpg  # noqa: E402
import httpx  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402

TABLES = "rankings, results, candidates, participants, sessions, places, tile_cache"


@pytest_asyncio.fixture(scope="session", loop_scope="session", autouse=True)
async def _database():
    conn = await asyncpg.connect(ADMIN_URL)
    try:
        exists = await conn.fetchval("select 1 from pg_database where datname = 'hangry_test'")
        if not exists:
            await conn.execute("create database hangry_test")
    finally:
        await conn.close()

    # Rebuilt from the models each run. create_all alone never alters an
    # existing table, so a schema change would silently test the old one.
    async with engine.begin() as db:
        await db.run_sync(Base.metadata.drop_all)
        await db.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def _clean():
    """Truncate between tests. Cheaper than per-test transactions, and the
    code under test commits, so a wrapping transaction wouldn't isolate."""
    async with engine.begin() as db:
        await db.execute(text(f"truncate {TABLES} restart identity cascade"))
    yield


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def db():
    async with SessionLocal() as session:
        yield session


@pytest.fixture
def auth():
    """Header helper, participant auth is one opaque token, nothing more."""
    return lambda token: {"X-Participant-Token": token}
