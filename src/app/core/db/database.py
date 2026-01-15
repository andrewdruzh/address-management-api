from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings


def create_database_engine():
    """Create and configure the async database engine."""
    config = get_settings()
    return create_async_engine(
        config.database_url,
        echo=config.sql_echo,
        pool_pre_ping=True,
        future=True,
    )


database_engine = create_database_engine()

SessionLocal = async_sessionmaker(
    bind=database_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_database_session() -> AsyncIterator[AsyncSession]:
    """Dependency function to get database session."""
    async with SessionLocal() as db_session:
        try:
            yield db_session
        finally:
            await db_session.close()


# Alias for backward compatibility with workers
async_session_factory = SessionLocal
