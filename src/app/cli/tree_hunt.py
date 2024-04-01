import asyncio
from itertools import cycle

from .. import settings
from ..lib.strategies.scraping import LandState


async def job(land_number: int):
    try:
        await LandState.get(land_number)
    except Exception:
        pass
    else:
        print(f"\rSearch land {land_number:05d} complete", end="")


async def worker(land_number: int):
    while True:
        await job(land_number)
        await asyncio.sleep(settings.REDIS_DEFAULT_TTL)


async def main():
    for i in cycle(range(1, 10)):
        await job(i)


if __name__ == "__main__":
    asyncio.run(main())
