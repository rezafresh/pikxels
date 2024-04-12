from datetime import datetime
from time import time

import httpx
from fastapi import HTTPException

from ..lib.strategies.scraping.land_state import get as land_state_get
from ..lib.strategies.scraping.land_state import (
    get_from_cache as land_state_get_from_cache,
)


def get_land_state(land_number: int, cached: bool = True, raw: bool = False):
    if not (state := land_state_get(land_number, cached=cached, raw=raw)):
        raise HTTPException(422, "Could not retrieve the land state. Try again later.")

    return {"resultCreatedAt": state[0].created_at.astimezone().isoformat(), "state": state[1]}


def get_cached_lands_states() -> dict[str, dict]:
    def make_land_state(land_number: int):
        if not (cached := land_state_get_from_cache(land_number)):
            return None

        return {
            "resultCreatedAt": cached[0].created_at.astimezone().isoformat(),
            "state": cached[1],
        }

    lands = {i: make_land_state(i) for i in range(1, 5000)}
    result = {str(key): value for key, value in lands.items() if value}
    return {"states": result}


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
