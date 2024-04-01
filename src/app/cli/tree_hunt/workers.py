import asyncio

from ...lib.strategies.scraping import LandState


async def task(land_number: int):
    try:
        land_state = await LandState.from_browser(land_number)
    except Exception:
        pass
    else:
        print(f"\rSearch land {land_number:05d} complete", end="")
        return land_state.state["id"]


def worker(land_number: int):
    return asyncio.run(task(land_number))
