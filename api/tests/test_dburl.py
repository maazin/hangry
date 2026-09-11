"""Translating a hosting provider's connection string for asyncpg.

Written after a Render deploy died on the real thing:

    TypeError: connect() got an unexpected keyword argument 'sslmode'

Neon appends `?sslmode=require&channel_binding=require`, SQLAlchemy forwards
unknown query parameters to the driver, and asyncpg has no such keyword. The
scheme rewrite alone was never enough.
"""

import pytest

from app.config import Settings
from app.dburl import normalize

# What each host actually hands you.
NEON = "postgresql://user:pw@ep-cool-sun-123.us-east-2.aws.neon.tech/hangry?sslmode=require&channel_binding=require"
SUPABASE = "postgresql://postgres:pw@db.abcdefgh.supabase.co:5432/postgres?sslmode=require"
HEROKU = "postgres://user:pw@host.compute.amazonaws.com:5432/dbname"
FLY = "postgres://hangry:pw@hangry-db.flycast:5432/hangry?sslmode=disable"
RENDER = "postgresql://hangry:pw@dpg-abc123-a.oregon-postgres.render.com/hangry"
LOCAL = "postgresql+asyncpg://hangry:hangry@localhost:5433/hangry"


@pytest.mark.parametrize("raw", [NEON, SUPABASE, HEROKU, FLY, RENDER, LOCAL])
def test_every_provider_lands_on_the_async_driver(raw):
    url, _ = normalize(raw)
    assert url.startswith("postgresql+asyncpg://")


@pytest.mark.parametrize("raw", [NEON, SUPABASE, HEROKU, FLY, RENDER, LOCAL])
def test_no_query_string_survives(raw):
    """The whole failure was a query parameter reaching the driver. Rebuilding
    the URL without one is what guarantees it cannot happen again."""
    url, _ = normalize(raw)
    assert "?" not in url


def test_sslmode_becomes_an_asyncpg_connect_argument():
    url, args = normalize(NEON)
    assert "sslmode" not in url
    assert args["ssl"] == "require"


def test_channel_binding_is_dropped():
    """asyncpg negotiates SCRAM channel binding itself, so the parameter has
    no equivalent and costs nothing to lose."""
    _, args = normalize(NEON)
    assert "channel_binding" not in args


def test_sslmode_disable_is_carried_through_rather_than_assumed():
    _, args = normalize(FLY)
    assert args["ssl"] == "disable"


def test_a_url_with_no_query_needs_no_connect_args():
    url, args = normalize(HEROKU)
    assert url == "postgresql+asyncpg://user:pw@host.compute.amazonaws.com:5432/dbname"
    assert args == {}


def test_host_credentials_and_database_are_left_alone():
    url, _ = normalize(NEON)
    assert "user:pw@ep-cool-sun-123.us-east-2.aws.neon.tech" in url
    assert url.endswith("/hangry")


def test_connect_timeout_and_application_name_are_translated():
    _, args = normalize("postgresql://u:p@h/db?connect_timeout=10&application_name=hangry")
    assert args["timeout"] == 10.0
    assert args["server_settings"]["application_name"] == "hangry"


def test_a_password_with_reserved_characters_survives():
    """Generated passwords contain these. Losing one turns into an
    authentication failure that reads like a wrong secret."""
    url, _ = normalize("postgresql://u:p%40ss%2Fword@host/db?sslmode=require")
    assert "p%40ss%2Fword" in url


def test_a_non_postgres_url_is_left_untouched():
    raw = "sqlite+aiosqlite:///./local.db"
    assert normalize(raw) == (raw, {})


def test_settings_expose_the_translated_pair():
    settings = Settings(database_url=NEON)
    assert settings.sqlalchemy_url.startswith("postgresql+asyncpg://")
    assert "?" not in settings.sqlalchemy_url
    assert settings.sqlalchemy_connect_args == {"ssl": "require"}


async def test_the_engine_actually_connects_with_a_neon_shaped_url(db):
    """The regression, end to end.

    Points a Neon-shaped URL at the local test database: same libpq query
    string, a host that really answers. Before the fix this raised
    TypeError on `sslmode` before any network call happened.
    """
    import os

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    base = os.environ["DATABASE_URL"].replace("+asyncpg", "")
    raw = f"{base}?sslmode=disable&channel_binding=prefer"

    url, connect_args = normalize(raw)
    engine = create_async_engine(url, connect_args=connect_args)
    try:
        async with engine.connect() as conn:
            assert (await conn.execute(text("select 1"))).scalar_one() == 1
    finally:
        await engine.dispose()
