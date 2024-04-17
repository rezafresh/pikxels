import json
from datetime import datetime
from itertools import chain

from ..lib.redis import get_redis_connection
from ..lib.strategies.scraping import land_state as ls


async def get_land_state(land_number: int, raw: bool = False):
    state, meta = await ls.get(land_number, raw=raw)
    return {**meta, "state": state}


async def get_cached_lands_available_resources(offset: int = 0):
    async with get_redis_connection() as redis:
        cached: dict = (await redis.hgetall("app:lands:states")) or {}

    def to_datetime(dt: datetime | str | None) -> datetime | None:
        if isinstance(dt, datetime):
            return dt
        elif isinstance(dt, str):
            return datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
        return None

    states = {k: ls.parse(json.loads(v)) for k, v in cached.items()}
    now = datetime.now()
    resources = [
        [
            *[
                {
                    "landNumber": int(land_number),
                    "isBlocked": state["isBlocked"],
                    "totalPlayers": state["totalPlayers"],
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
                    **w,
                }
                for w in state["windmills"]
                if 0 < ((to_datetime(w["finishTime"]) or now) - now).total_seconds() < 600
            ],
        ]
        for land_number, state in states.items()
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


async def get_current_running_processes():
    pass
    # processes = [
    #     {
    #         "uid": uid,
    #         "fn": t.fn.__module__,
    #         "args": wi.args,
    #         "kwargs": wi.kwargs,
    #         "state": wi.future._state,
    #     }
    #     for wi in executor._threads.
    # ]
    # return {
    #     "length": len(processes),
    #     "processes": processes
    # }
