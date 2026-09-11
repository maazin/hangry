"""Turning a hosting provider's connection string into one asyncpg accepts.

Every managed Postgres hands out a libpq connection string, because libpq is
what psycopg2 and `psql` speak. This app is async and speaks asyncpg, which
takes a different set of keywords. Two things therefore need translating.

The scheme. Providers emit `postgres://` or `postgresql://`, which SQLAlchemy
resolves to psycopg2 and then fails on.

The query string. This is the one that bites. Neon appends
`?sslmode=require&channel_binding=require`, and SQLAlchemy forwards unknown
query parameters straight to the driver, so the deploy dies on

    TypeError: connect() got an unexpected keyword argument 'sslmode'

asyncpg wants the same SSL modes under `ssl` instead, passed as a connect
argument rather than in the URL. Anything libpq-only with no asyncpg
equivalent is dropped and logged, because a silently ignored parameter is how
this failed in the first place.
"""

from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlsplit, urlunsplit

log = logging.getLogger(__name__)

ASYNC_SCHEME = "postgresql+asyncpg"


def normalize(raw: str) -> tuple[str, dict]:
    """Return a URL SQLAlchemy can use, plus connect args for asyncpg.

    Non-Postgres URLs are handed back untouched, so this stays out of the way
    of anything else.
    """
    parts = urlsplit(raw)
    if not parts.scheme.startswith("postgres"):
        return raw, {}

    connect_args: dict = {}
    dropped: list[str] = []

    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        name = key.lower()

        if name == "sslmode":
            # asyncpg takes libpq's own mode names, under a different keyword.
            connect_args["ssl"] = value
        elif name == "connect_timeout":
            connect_args["timeout"] = float(value)
        elif name == "application_name":
            connect_args.setdefault("server_settings", {})["application_name"] = value
        else:
            dropped.append(key)

    if dropped:
        # channel_binding is the usual one. asyncpg negotiates SCRAM channel
        # binding by itself, so losing the parameter costs nothing.
        # Warning rather than info on purpose. This runs at import time,
        # before the app configures logging, so anything quieter never
        # reaches a handler, and a connection parameter vanishing without a
        # trace is the exact failure this module exists to stop.
        log.warning(
            "ignoring connection parameters asyncpg does not accept: %s", ", ".join(sorted(set(dropped)))
        )

    # The query is rebuilt as empty rather than filtered, so nothing can leak
    # through to the driver by being spelled in a way this function missed.
    url = urlunsplit((ASYNC_SCHEME, parts.netloc, parts.path, "", parts.fragment))
    return url, connect_args
