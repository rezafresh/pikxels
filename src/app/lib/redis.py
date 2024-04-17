from contextlib import aclosing, asynccontextmanager

from redis.asyncio import Redis

from .. import settings


@asynccontextmanager
async def get_redis_connection():
    async with aclosing(Redis.from_url(settings.REDIS_URL, decode_responses=True)) as client:
        yield client
