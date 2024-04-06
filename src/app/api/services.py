from datetime import datetime
from time import time

import httpx
from fastapi import HTTPException

from ..lib.strategies.scraping import land_state


def get_land_state(land_number: int, cached: bool = True):
    if state := land_state.get(land_number, cached):
        return {"state": state}
    raise HTTPException(422, "Could not retrieve the land state. Try again later.")


async def get_marketplace_listing():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://pixels-server.pixels.xyz/cache/marketplace/listings/count?v={int(time())}"
        )
        listing = response.json()

    counts: dict = listing["counts"]
    prices: dict = listing["prices"]
    return {
        "lastUpdated": datetime.fromtimestamp(int(listing["lastUpdated"]) // 1000),
        "listing": {
            item_id: {
                "count": counts.get(item_id, None),
                "price": prices.get(item_id, None),
            }
            for item_id in set(list(counts.keys()) + list(prices.keys()))
        },
    }


def get_cached_lands_states() -> dict[str, dict]:
    def get_from_cache(land_number: int) -> dict:
        return land_state.from_cache(land_number) or land_state.from_cache(
            land_number, queue=land_state.q.low
        )

    lands = {i: get_from_cache(i) for i in range(1, 5000)}
    result = {str(key): value for key, value in lands.items() if value}
    return {"states": result}
