import asyncio
import json
import logging
from datetime import datetime

from redis.asyncio import Redis

from ...lib.redis import get_redis_connection
from ...lib.strategies.scraping import land_state as ls
from .._concurrency import sema_tasks


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.addHandler(_ := logging.StreamHandler())
    _.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    return logger


logger = get_logger("app:tasks:res-hunter")


async def worker(redis: Redis, land_number: int):
    while not asyncio.current_task().cancelled():
        state = await _worker(redis, land_number)
        sleep_seconds = int(max(0, (state["expiresAt"] - datetime.now()).total_seconds()))
        logger.info(f"Land {land_number} next sync in {sleep_seconds} seconds")
        await asyncio.sleep(sleep_seconds)


async def _worker(redis: Redis, land_number: int):
    if cached := await ls.from_cache(land_number):
        return cached

    state = await ls.worker(land_number, sema_tasks)
    await redis.publish(
        "app:lands:states:channel",
        json.dumps({"message": {"landNumber": land_number, **state}}, default=str),
    )
    return state


async def main():
    async with get_redis_connection() as redis:
        tasks = [asyncio.create_task(worker(redis, i + 1)) for i in range(5000)]
        await asyncio.wait(tasks)
