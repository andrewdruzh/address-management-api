from urllib.parse import urlparse

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.workers.jobs import recognize_addresses_batch, validate_addresses_batch


def _parse_redis_url(url: str) -> RedisSettings:
    """Parse Redis connection URL into RedisSettings."""
    parsed_url = urlparse(url)
    database_number = int((parsed_url.path or "/0").lstrip("/"))
    return RedisSettings(
        host=parsed_url.hostname or "localhost",
        port=parsed_url.port or 6379,
        database=database_number,
        password=parsed_url.password,
        ssl=(parsed_url.scheme == "rediss"),
    )


class ARQWorkerConfig:
    """Configuration for ARQ background worker."""

    config = get_settings()
    redis_settings = _parse_redis_url(config.redis_url)
    functions = [validate_addresses_batch, recognize_addresses_batch]
    max_jobs = 10
