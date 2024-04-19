import asyncio
import json
from datetime import datetime
from random import randint

from redis.asyncio import Redis

from ...lib.redis import get_redis_connection
from ...lib.strategies.scraping import land_state as ls
from ...lib.utils import get_logger, parse_datetime
from .._concurrency import sema_tasks

logger = get_logger("app:resource-hunter")


async def worker(redis: Redis, land_number: int):
    while not asyncio.current_task().cancelled():
        try:
            state = await _worker(redis, land_number)

            if expires_at := parse_datetime(state["expiresAt"], "%Y-%m-%d %H:%M:%S.%f"):
                if (sleep_seconds := int((expires_at - datetime.now()).total_seconds())) <= 0:
                    sleep_seconds = randint(60, 600)
            else:
                sleep_seconds = randint(60, 300)

        except Exception as error:
            logger.error(f"{repr(error)}")
            sleep_seconds = randint(60, 300)

        logger.info(f"Land {land_number} next sync in {sleep_seconds} seconds")
        await asyncio.sleep(sleep_seconds)


async def _worker(redis: Redis, land_number: int):
    if cached := await ls.from_cache(land_number):
        return cached

    state = await ls.worker(land_number, sema_tasks)
    await redis.publish(
        "app:lands:states:channel",
        json.dumps({"landNumber": land_number, **state}, default=str),
    )
    return state


async def main():
    async with get_redis_connection() as redis:
        tasks = [asyncio.create_task(worker(redis, i + 1)) for i in range(5000)]
        await asyncio.wait(tasks)
