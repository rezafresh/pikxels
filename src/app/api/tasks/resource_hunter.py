import asyncio
from datetime import datetime, timedelta
from random import randint

import rq
from redis import Redis as RedisSync

from ... import settings
from ...lib.redis import create_redis_connection
from ...lib.strategies.scraping import land_state as ls
from ...lib.utils import get_logger, parse_datetime

logger = get_logger("app:resource-hunter")
queue = rq.Queue(connection=RedisSync.from_url(settings.REDIS_URL))


async def loop(land_number: int):
    while not asyncio.current_task().cancelled():
        try:
            state = await fetch_land_state(land_number)

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


def worker(land_number: int):
    return asyncio.run(_worker(land_number))


async def _worker(land_number: int):
    async with create_redis_connection() as redis:
        if cached := await ls.from_cache(land_number, redis=redis):
            return cached

        raw_state = await ls.from_browser(land_number)
        seconds_to_expire = get_best_seconds_to_expire(raw_state)
        cached_state = await ls.to_cache(land_number, raw_state, seconds_to_expire, redis=redis)
        await ls.publish(land_number, cached_state, redis=redis)

    return cached_state


async def fetch_land_state(land_number: int):
    jid = f"app:land:{land_number}:job"

    if not (job := queue.fetch_job(jid)):
        job = queue.enqueue(worker, land_number, job_id=jid)
    elif job.get_status() in [rq.job.JobStatus.FINISHED, rq.job.JobStatus.FAILED]:
        job = queue.enqueue(worker, land_number, job_id=jid)

    while True:
        if job.get_status() == rq.job.JobStatus.FINISHED:
            break
        elif job.get_status() == rq.job.JobStatus.FAILED:
            raise Exception(f"Failed to fetch land state\n{job.exc_info!r}")

        await asyncio.sleep(0.1)

    return job.result


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
        "grills": [v for _, v in entities.items() if v["entity"].startswith("ent_landbbq")],
        "kilns": [v for _, v in entities.items() if v["entity"].startswith("ent_kiln")],
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


async def main():
    tasks = [asyncio.create_task(loop(i + 1)) for i in range(5000)]
    await asyncio.wait(tasks)
