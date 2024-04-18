import asyncio
import json
from datetime import datetime
from random import randint

from redis.asyncio import Redis

from ..lib.redis import get_redis_connection
from ..lib.strategies.scraping import land_state as ls


async def worker(redis: Redis, land_number: int):
    while not asyncio.current_task().cancelled():
        if state := await _worker(redis, land_number):
            sleep_seconds = int(max(0, (state["expiresAt"] - datetime.now()).total_seconds()))
        else:
            sleep_seconds = randint(60, 600)

        print(f"Land {land_number} next sync in {sleep_seconds} seconds")
        await asyncio.sleep(sleep_seconds)


async def _worker(redis: Redis, land_number: int):
    if await redis.exists(f"app:land:{land_number}:state"):
        return None

    state = await ls.worker(land_number)
    await redis.publish(
        "app:lands:states:channel",
        json.dumps({"message": {"landNumber": land_number, **state}}, default=str),
    )
    return state


async def main():
    async with get_redis_connection() as redis:
        tasks = [asyncio.create_task(worker(redis, i + 1)) for i in range(5000)]
        await asyncio.wait(tasks)


if __name__ == "__main__":
    asyncio.run(main())
