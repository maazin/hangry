from collections.abc import AsyncIterator

from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.sqlalchemy_url,
    # The host's libpq query string, translated for asyncpg. See app/dburl.py.
    connect_args=settings.sqlalchemy_connect_args,
    pool_pre_ping=True,
    **({"poolclass": NullPool} if settings.testing else {}),
)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session
