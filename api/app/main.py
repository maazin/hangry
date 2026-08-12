import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config import settings
from app.db import engine
from app.routes import router

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(
    title="Hangry",
    description="Group dining decisions that don't quietly exclude anyone.",
    version="0.4.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/api/health")
async def health() -> dict:
    """Liveness plus a real database round trip.

    A health check that doesn't touch the database reports green while every
    request 500s, which is the failure this endpoint exists to catch.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        database = "ok"
    except Exception as exc:  # surfaced, not swallowed
        logging.getLogger(__name__).warning("health: db unreachable: %s", exc)
        database = "unreachable"

    return {"api": "ok", "db": database}
