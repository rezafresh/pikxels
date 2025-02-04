import asyncio
from datetime import datetime, timedelta
from random import randint

import rq
from playwright.async_api import ProxySettings
from redis import Redis as RedisSync

from .. import settings
from ..lib.pixels import land_state as ls
from ..lib.redis import create_redis_connection

queue = rq.Queue(connection=RedisSync.from_url(settings.REDIS_URL))


def enqueue(land_number: int, *, proxy: ProxySettings = None) -> rq.job.Job:
    return queue.enqueue(
        job,
        land_number,
        proxy=proxy,
        job_id=f"app:land:{land_number}:job",
        on_success=job_success_handler,
        on_failure=job_failure_handler,
    )


def job(land_number: int, *, proxy: ProxySettings = None):
    return asyncio.run(_job(land_number, proxy=proxy))


async def _job(land_number: int, *, proxy: ProxySettings = None):
    raw_state = await ls.from_browser(land_number, proxy=proxy)
    seconds_to_expire = get_best_seconds_to_expire(raw_state)

    async with create_redis_connection() as redis:
        cached_state = await ls.to_cache(land_number, raw_state, seconds_to_expire, redis=redis)
        await ls.publish(land_number, cached_state, redis=redis)

    return cached_state


def job_success_handler(job: rq.job.Job, connection, result: ls.CachedLandState, *args, **kwargs):
    expires_at = result["expiresAt"]
    print(f"Land {job.args[0]} next sync at {expires_at!s}.")


def job_failure_handler(job: rq.job.Job, connection, type, value, traceback):
    next_attempt = datetime.now() + timedelta(seconds=randint(60, 600))
    print(f"Failed to fetch land {job.args[0]} state. Next attempt at {next_attempt!s}.")


def get_best_seconds_to_expire(raw_state: dict) -> int:
    if raw_state["permissions"]["use"][0] != "ANY":
        # Land is Blocked
        # try again between 3 and 5 days
        return randint(259200, 432000)

    now = datetime.now()
    now_as_epoch = int(now.timestamp())
    tomorrow_as_epoch = int((now + timedelta(days=1)).timestamp())

    def calc_next_respawn(t: dict) -> int:
        statics: list[dict] = t["generic"]["statics"]

        if last_chop := [_ for _ in statics if _["name"] == "lastChop"][0].get("value"):
            result = datetime.fromtimestamp(int(last_chop) // 1000)
            result += timedelta(hours=7, minutes=15)
            return result.timestamp()

        return now_as_epoch

    def extract_finish_time(industry: dict) -> int:
        statics: list[dict] = industry["generic"]["statics"]

        if finish_time_str := [_ for _ in statics if _["name"] == "finishTime"][0].get("value"):
            return int(finish_time_str) // 1000

        return now_as_epoch

    entities: dict = raw_state["entities"]
    resources = {
        "trees": [v for _, v in entities.items() if v["entity"].startswith("ent_tree")],
        "windmills": [v for _, v in entities.items() if v["entity"].startswith("ent_windmill")],
        "wineries": [v for _, v in entities.items() if v["entity"].startswith("ent_winery")],
        "grills": [v for _, v in entities.items() if v["entity"].startswith("ent_landbbq")],
        "kilns": [v for _, v in entities.items() if v["entity"].startswith("ent_kiln")],
    }
    timers = [tomorrow_as_epoch]

    # trees
    if resources["trees"]:
        timers.append(max(calc_next_respawn(t) for t in resources["trees"]))

    # windmills
    if resources["windmills"]:
        timers.append(min(extract_finish_time(item) for item in resources["windmills"]))

    # wineries
    if resources["wineries"]:
        timers.append(min(extract_finish_time(item) for item in resources["wineries"]))

    # grills
    if resources["grills"]:
        timers.append(min(extract_finish_time(item) for item in resources["grills"]))

    # kilns
    if resources["kilns"]:
        timers.append(min(extract_finish_time(item) for item in resources["kilns"]))

    result = datetime.fromtimestamp(min(timers))

    if (delta := int((result - now).total_seconds())) == 0:
        # this case happens if:
        # 1. all resources are available now.
        #   In that case, probally the land is locked;
        return 86400
    elif delta < 0:
        # probally, the data Analyzed is old; schedule update between 1 and 5 minutes;
        return randint(60, 300)

    return max(15, delta)
