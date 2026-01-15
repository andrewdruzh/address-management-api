from contextlib import asynccontextmanager
from fastapi import FastAPI
from arq.connections import RedisSettings, create_pool

from app.api.v1.routers import api_router
from app.core.config import get_settings


@asynccontextmanager
async def application_lifespan(app_instance: FastAPI):
    """Manage application lifecycle events."""
    config = get_settings()
    redis_pool = await create_pool(RedisSettings.from_dsn(config.redis_url))
    app_instance.state.redis = redis_pool
    try:
        yield
    finally:
        await redis_pool.close()


def initialize_application() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    application = FastAPI(
        title="Address Management API",
        description="RESTful API for address validation and recognition services",
        lifespan=application_lifespan,
    )
    application.include_router(api_router)
    return application


app = initialize_application()
