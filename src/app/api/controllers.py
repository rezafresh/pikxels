import json
from datetime import datetime
from itertools import chain
from time import time

import httpx
import rq
from fastapi import HTTPException

from ..lib.strategies.scraping._queues import _redis, sync
from ..lib.strategies.scraping.land_state import get as land_state_get
from ..lib.strategies.scraping.land_state import parse as land_state_parse


def get_land_state(land_number: int, cached: bool = True, raw: bool = False):
    if not (state := land_state_get(land_number, cached=cached, raw=raw)):
        raise HTTPException(422, "Could not retrieve the land state. Try again later.")

    return {"lastUpdated": state[0].created_at.astimezone().isoformat(), "state": state[1]}


def get_cached_lands_available_resources(offset: int = 0):
    if not (cached := _redis.get("app:lands:resources")):
        if not (job_ids := sync.finished_job_registry.get_job_ids()):
            return HTTPException(404, "No data found")

        jobs = [sync.fetch_job(jid) for jid in job_ids]

        def parse(j: rq.job.Job):
            if last_result := j.latest_result():
                if result := last_result.return_value:
                    return {
                        "lastUpdated": last_result.created_at.astimezone().isoformat(),
                        **land_state_parse(result),
                    }
            return None

        resources = {j.args[0]: parse(j) for j in jobs}
        _redis.set("app:lands:resources", json.dumps(resources, default=str), ex=60)
    else:
        resources = json.loads(cached)

    def to_datetime(dt: datetime | str | None) -> datetime | None:
        if isinstance(dt, datetime):
            return dt
        elif isinstance(dt, str):
            return datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        return None

    now = datetime.now()
    resources = [
        [
            *[
                {
                    "landNumber": int(land_number),
                    "isBlocked": state["isBlocked"],
                    "totalPlayers": state["totalPlayers"],
                    "lastUpdated": state["lastUpdated"],
                    **t,
                }
                for t in state["trees"]
                if 0 < ((to_datetime(t["utcRefresh"]) or now) - now).total_seconds() < 600
            ],
            *[
                {
                    "landNumber": int(land_number),
                    "isBlocked": state["isBlocked"],
                    "totalPlayers": state["totalPlayers"],
                    "lastUpdated": state["lastUpdated"],
                    **w,
                }
                for w in state["windmills"]
                if 0 < ((to_datetime(w["finishTime"]) or now) - now).total_seconds() < 600
            ],
        ]
        for land_number, state in resources.items()
    ]
    resources = [*chain.from_iterable(resources)]
    resources = sorted(
        resources,
        key=lambda r: (to_datetime(r.get("utcRefresh")) or to_datetime(r.get("finishTime")) or now),
    )
    return {
        "totalItems": len(resources),
        "currentOffset": offset,
        "resultsPerPage": (results_per_page := 50),
        "resources": resources[offset : offset + results_per_page],
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
