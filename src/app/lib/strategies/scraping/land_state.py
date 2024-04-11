import asyncio
import json
import time
from datetime import datetime, timedelta
from random import randint
from typing import TypedDict

import rq
from fastapi import HTTPException
from playwright.async_api import Error as PWError
from playwright.async_api import Page, async_playwright

from .... import settings
from . import _queues as q
from ._utils import retry_until_valid, unix_time_to_datetime


class LandEntityPosition(TypedDict):
    x: int
    y: int


class ParsedTree(TypedDict):
    entity: str
    position: LandEntityPosition
    state: str
    utcRefresh: datetime | None
    lastChop: datetime | None
    lastTimer: datetime | None


class ParsedWindMill(TypedDict):
    entity: str
    position: LandEntityPosition
    allowPublic: bool
    inUseBy: str
    finishTime: datetime | None


class ParsedLandState(TypedDict):
    is_blocked: bool
    total_players: int
    trees: list[ParsedTree]
    windmills: list[ParsedWindMill]


async def from_browser(land_number: int) -> dict:
    async with async_playwright() as pw:
        browser = await pw.chromium.connect(
            settings.PW_WS_ENDPOINT,
            timeout=settings.PW_DEFAULT_TIMEOUT,
        )
        page = await browser.new_page()
        page.set_default_navigation_timeout(settings.PW_DEFAULT_TIMEOUT)
        page.set_default_timeout(settings.PW_DEFAULT_TIMEOUT)

        if not (await page.goto(f"https://play.pixels.xyz/pixels/share/{land_number}")).ok:
            raise HTTPException(422, "An error has ocurred while navigating to the land")

        # await page.wait_for_load_state("load")

        if (state_str := await phaser_land_state_getter(page)) is None:
            raise HTTPException(422, "Could not retrieve the land state")
        elif not state_str:
            raise HTTPException(422, "Invalid land state")

    return json.loads(state_str)


def from_cache(land_number: int, *, queue: rq.Queue = q.default) -> dict | None:
    if job := queue.fetch_job(f"app:land:{land_number}:state"):
        if latest := job.latest_result():
            if cached := latest.return_value:
                return json.loads(cached)
    return None


def get(land_number: int, cached: bool = True):
    if cached:
        if land_state := from_cache(land_number):
            return land_state
        elif land_state := from_cache(land_number, queue=q.sync):
            return land_state

    job = enqueue(land_number)

    while not (job.is_finished or job.is_failed):
        time.sleep(1)

    if job.is_failed:
        raise HTTPException(
            422, job.get_meta().get("message", "Unexpected error ocurred while running the job")
        )
    elif not job.result:
        raise HTTPException(422, "The job finished successfully, but returned an invalid result")

    return json.loads(job.result)


@retry_until_valid(tries=settings.PW_DEFAULT_TIMEOUT // 1000)
async def phaser_land_state_getter(page: Page):
    return await page.evaluate(
        "JSON.stringify(Phaser.Display.Canvas.CanvasPool.pool[0].parent.game.scene.scenes[1].stateManager.room.state)",
    )


def enqueue(land_number: int, *, queue: rq.Queue = q.default) -> rq.job.Job:
    return queue.enqueue(
        worker,
        land_number,
        job_id=f"app:land:{land_number}:state",
        on_success=worker_success_handler,
        on_failure=worker_failure_handler,
    )


def enqueue_at(land_number: int, at: datetime, *, queue: rq.Queue = q.default) -> rq.job.Job:
    return queue.enqueue_at(
        at,
        worker,
        land_number,
        job_id=f"app:land:{land_number}:state",
        on_success=worker_success_handler,
        on_failure=worker_failure_handler,
    )


def parse_tree(data: dict) -> ParsedTree:
    utc_refresh = unix_time_to_datetime(data["generic"].get("utcRefresh"))
    statics = {_["name"]: _["value"] for _ in data["generic"]["statics"]}
    last_timer = unix_time_to_datetime(statics["lastTimer"])
    last_chop = unix_time_to_datetime(statics["lastChop"])
    return {
        "entity": data["entity"],
        "position": data["position"],
        "state": data["generic"].get("state"),
        "utcRefresh": utc_refresh,
        "lastChop": last_chop,
        "lastTimer": last_timer,
    }


def parse_trees(entities: dict) -> list[ParsedTree]:
    return sorted(
        [
            {"id": key, **parse_tree(value)}
            for key, value in entities.items()
            if value["entity"].startswith("ent_tree")
        ],
        key=lambda _: (_["utcRefresh"] or datetime.fromtimestamp(0)),
    )


def parse_windmill(data: dict) -> ParsedWindMill:
    statics = {_["name"]: _["value"] for _ in data["generic"]["statics"]}
    return {
        "entity": data["entity"],
        "position": data["position"],
        "allowPublic": bool(int(statics["allowPublic"])),
        "inUseBy": statics["inUseBy"],
        "finishTime": unix_time_to_datetime(statics["finishTime"]),
    }


def parse_windmills(entities: dict) -> list[ParsedWindMill]:
    return sorted(
        [
            {"id": key, **parse_windmill(value)}
            for key, value in entities.items()
            if value["entity"].startswith("ent_windmill")
        ],
        key=lambda _: (_["finishTime"] or datetime.fromtimestamp(0)),
    )


def parse(land_state: dict) -> ParsedLandState:
    return {
        "isBlocked": land_state["permissions"]["use"][0] != "ANY",
        "totalPlayers": len(land_state["players"]),
        "trees": parse_trees(land_state["entities"]),
        "windmills": parse_windmills(land_state["entities"]),
    }


def worker(land_number: int):
    return json.dumps(asyncio.run(from_browser(land_number)))


def get_result_ttl_by_trees(land_state: ParsedLandState):
    if not land_state.get("trees"):
        # if the land doesnt have trees
        return 86400  # 1 day
    elif not land_state["trees"][0]["utcRefresh"]:
        # if the next tree is available
        return randint(60, 300)  # between 1 and 5 minutes
    elif utc_refresh := land_state["trees"][-1]["utcRefresh"]:
        # if all trees are in cooldown, scan again when the last one finish
        return max(60, int((utc_refresh - datetime.now()).total_seconds()))
    else:
        return 3600  # 1 hour


def get_result_ttl_by_windmills(land_state: ParsedLandState):
    if not land_state.get("windmills"):
        # if the land doesnt have trees
        return 86400  # 1 day
    elif not land_state["windmills"][0]["finishTime"]:
        # if the next tree is available
        return randint(60, 300)  # between 1 and 5 minutes
    elif finish_time := land_state["windmills"][-1]["finishTime"]:
        # if all trees are in cooldown, scan again when the last one finish
        return max(60, int((finish_time - datetime.now()).total_seconds()))
    else:
        return 3600  # 1 hour


def get_best_result_ttl(land_state: dict) -> int:
    parsed_land_state = parse(json.loads(land_state))
    return min(
        get_result_ttl_by_trees(parsed_land_state), get_result_ttl_by_windmills(parsed_land_state)
    )


def worker_success_handler(job: rq.job.Job, connection, result, *args, **kwargs):
    job.result_ttl = get_best_result_ttl(result)
    land_number = int(job.args[0])
    next_sync = datetime.now() + timedelta(seconds=job.result_ttl)
    print("next sync", land_number, next_sync)
    enqueue_at(land_number, next_sync, queue=q.sync)


def worker_failure_handler(job: rq.job.Job, connection, type, value, traceback):
    if isinstance(value, PWError):
        if "too many" in value.message.lower():
            job.meta["message"] = "The Job cannot be done now, the browser engine is at his limit"
        else:
            job.meta["message"] = "Failed to connect to the browser engine"
    else:
        job.meta["message"] = str(value)

    job.meta["detail"] = repr(value)
    job.save_meta()
    land_number = int(job.args[0])
    next_attempt = datetime.now() + timedelta(seconds=randint(120, 600))
    print("next attempt", land_number, next_attempt)
    enqueue_at(land_number, next_attempt, queue=q.sync)
