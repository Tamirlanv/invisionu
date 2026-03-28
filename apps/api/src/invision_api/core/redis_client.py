from functools import lru_cache
from typing import Any

import redis

from invision_api.core.config import get_settings


@lru_cache
def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis.from_url(str(settings.redis_url), decode_responses=True)


def redis_ping() -> bool:
    try:
        return bool(get_redis_client().ping())
    except (redis.RedisError, OSError):
        return False


def enqueue_job(queue_name: str, payload: dict[str, Any]) -> None:
    """Redis list-backed job queue scaffold (LPUSH)."""
    client = get_redis_client()
    import json

    client.lpush(queue_name, json.dumps(payload))
