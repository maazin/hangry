import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app import retention
from app.config import settings
from app.db import engine
from app.routes import router
from app.routes_groups import router as groups_router

logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the retention sweep alongside the app.

    One machine serves this, so an in-process task is the whole scheduler.
    It is cancelled on shutdown so a redeploy does not leave it running
    against a closing connection pool.
    """
    task = None
    if settings.purge_enabled:
        task = asyncio.create_task(retention.purge_loop())
        log.info("retention sweep every %d minutes", settings.purge_interval_minutes)

    yield

    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Hangry",
    description="Group dining decisions that do not quietly exclude anyone.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(groups_router)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Turn a crash into something the client can read.

    Starlette's default 500 is plain text, which the frontend's JSON error
    parser cannot use, so a real bug surfaced in the interface as the generic
    "Something went wrong" with no code to branch on. The traceback goes to
    the log and stays out of the response.
    """
    log.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": {"code": "server_error", "message": "Something broke on our side. Try again."}},
    )


@app.get("/api/health")
async def health() -> dict:
    """Liveness plus a real database round trip.

    A health check that avoids the database reports green while every request
    returns 500, which is the failure this endpoint exists to catch.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("select 1"))
        database = "ok"
    except Exception as exc:  # surfaced rather than swallowed
        log.warning("health: db unreachable: %s", exc)
        database = "unreachable"

    return {"api": "ok", "db": database}
