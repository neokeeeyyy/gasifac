from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from api.config import settings

_url = settings.DATABASE_URL

engine = create_async_engine(
    _url,
    pool_pre_ping=True,
    connect_args={"statement_cache_size": 0} if "pooler" in _url else {},
)


async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
