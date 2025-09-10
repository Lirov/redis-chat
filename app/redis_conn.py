from redis.asyncio import from_url
from .config import settings

redis = from_url(
    str(settings.REDIS_URL),
    decode_responses=True,
    health_check_interval=30,
)
