from datetime import datetime
from time import time

import httpx
from fastapi import HTTPException

from ..lib.strategies.scraping.land_state import from_cache as land_state_from_cache
from ..lib.strategies.scraping.land_state import get as land_state_get
from ..lib.strategies.scraping.land_state import parse as land_state_parse


def get_land_state(land_number: int, cached: bool = True, raw: bool = False):
    if state := land_state_get(land_number, cached):
        if raw:
            return {"state": state}
        return {"state": land_state_parse(state)}

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


def get_cached_lands_states(raw: bool = False) -> dict[str, dict]:
    lands = {i: land_state_from_cache(i) for i in range(1, 5000)}

    if raw:
        result = {str(key): value for key, value in lands.items() if value}
    else:
        result = {str(key): land_state_parse(value) for key, value in lands.items() if value}

    return {"states": result}
