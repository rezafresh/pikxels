import asyncio
from datetime import datetime, timedelta
from random import randint

from redis.asyncio import Redis

from ... import settings
from ...lib.redis import get_redis_connection
from ...lib.strategies.scraping import land_state as ls
from ...lib.utils import get_logger, parse_datetime

logger = get_logger("app:resource-hunter")
semaphore = asyncio.Semaphore(settings.CONCURRENCY)


async def worker(land_number: int, *, redis: Redis):
    while not asyncio.current_task().cancelled():
        try:
            state = await _worker(land_number, redis=redis)

            if expires_at := parse_datetime(state["expiresAt"], "%Y-%m-%d %H:%M:%S.%f"):
                if (sleep_seconds := int((expires_at - datetime.now()).total_seconds())) <= 0:
                    sleep_seconds = randint(60, 600)
            else:
                sleep_seconds = randint(60, 300)

        except Exception as error:
            logger.error(f"{repr(error)}")
            sleep_seconds = randint(60, 300)

        logger.info(f"Land {land_number} next sync in {sleep_seconds} seconds")
        await asyncio.sleep(sleep_seconds)


async def _worker(land_number: int, *, redis: Redis):
    if cached := await ls.from_cache(land_number, redis=redis):
        return cached

    state = await fetch_state_and_cache(land_number, redis=redis)
    await ls.publish(land_number, state, redis=redis)
    return state


async def fetch_state_and_cache(land_number: int, *, redis: Redis) -> ls.CachedLandState:
    raw_state = await ls.from_browser(land_number, semaphore)
    seconds_to_expire = get_best_seconds_to_expire(raw_state)
    return await ls.to_cache(land_number, raw_state, seconds_to_expire, redis=redis)


def get_best_seconds_to_expire(raw_state: dict) -> int:
    if raw_state["permissions"]["use"][0] != "ANY":
        # Land is Blocked
        return 86400

    now = datetime.now()
    now_as_epoch = int(now.timestamp())
    tomorrow_as_epoch = int((now + timedelta(days=1)).timestamp())

    def extract_utc_refresh(t: dict) -> int:
        if utc_refresh := t["generic"].get("utcRefresh"):
            return utc_refresh // 1000

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
    }
    timers = [tomorrow_as_epoch]

    # trees
    if resources["trees"]:
        timers.append(max(extract_utc_refresh(t) for t in resources["trees"]))

    # windmills
    if resources["windmills"]:
        timers.append(min(extract_finish_time(item) for item in resources["windmills"]))

    # wineries
    if resources["wineries"]:
        timers.append(min(extract_finish_time(item) for item in resources["wineries"]))

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


async def main():
    async with get_redis_connection() as redis:
        tasks = [asyncio.create_task(worker(i + 1, redis=redis)) for i in range(5000)]
        await asyncio.wait(tasks)
