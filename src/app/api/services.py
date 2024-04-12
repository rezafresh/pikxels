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


def get_cached_lands_available_resources(offset: int = 0):
    now = datetime.now()

    def make_resources(land_number: int):
        if not (cached := land_state_get_from_cache(land_number)):
            return None

        result = [
            *list(
                filter(
                    lambda t: ((t["utcRefresh"] or now) - now).total_seconds() <= 600,
                    cached[1]["trees"],
                )
            ),
            *list(
                filter(
                    lambda w: ((w["finishTime"] or now) - now).total_seconds() <= 600,
                    cached[1]["windmills"],
                )
            ),
        ]
        return [
            {
                "land": land_number,
                "landIsBlocked": cached[1]["isBlocked"],
                "totalPlayers": cached[1]["totalPlayers"],
                **_,
            }
            for _ in result
        ]

    results = list(filter(bool, [make_resources(i) for i in range(1, 5000)]))
    results = [_ for item in results for _ in item]

    def predicate(item: dict) -> bool:
        return True

    results = [_ for _ in results if predicate(_)]
    results = sorted(
        results, key=lambda item: (item.get("utcRefresh") or item.get("finishTime") or now)
    )
    return {
        "totalItems": len(results),
        "currentOffset": offset,
        "resources": results[offset : offset + 20],
    }


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
