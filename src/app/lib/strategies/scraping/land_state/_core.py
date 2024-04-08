import asyncio
import json
import time
from datetime import datetime, timedelta
from random import randint

import rq
from fastapi import HTTPException
from playwright.async_api import Error as PWError
from playwright.async_api import Page, async_playwright

from ..... import settings
from .. import _queues as q
from .._utils import retry_until_valid
from . import _parsers as p
from . import types as t


async def from_browser(land_number: int) -> dict:
    async with async_playwright() as pw:
        browser = context = page = None

        try:
            browser = await pw.chromium.connect_over_cdp(
                settings.PW_CDP_ENDPOINT_URL,
                timeout=settings.PW_DEFAULT_TIMEOUT,
            )
            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_navigation_timeout(settings.PW_DEFAULT_TIMEOUT)
            page.set_default_timeout(settings.PW_DEFAULT_TIMEOUT)

            if not (await page.goto(f"https://play.pixels.xyz/pixels/share/{land_number}")).ok:
                raise HTTPException(422, "An error has ocurred while navigating to the land")

            # await page.wait_for_load_state("load")

            if (state_str := await phaser_land_state_getter(page)) is None:
                raise HTTPException(422, "Could not retrieve the land state")
            elif not state_str:
                raise HTTPException(422, "Invalid land state")
        finally:
            page and await page.close()
            context and await context.close()
            browser and await browser.close()

    return json.loads(state_str)


def from_cache(land_number: int, *, queue: rq.Queue = q.default) -> dict | None:
    if job := queue.fetch_job(f"app:land:{land_number}:state"):
        if latest := job.latest_result():
            if cached := latest.return_value:
                return json.loads(cached)
    return None


def enqueue(land_number: int, *, queue: rq.Queue = q.default) -> rq.job.Job:
    return queue.enqueue(
        worker,
        land_number,
        job_id=f"app:land:{land_number}:state",
        on_success=worker_success_handler,
        on_failure=worker_failure_handler,
    )


def enqueue_in(
    land_number: int, time_delta: timedelta, *, queue: rq.Queue = q.default
) -> rq.job.Job:
    return queue.enqueue_in(
        time_delta,
        worker,
        land_number,
        job_id=f"app:land:{land_number}:state",
        on_success=worker_success_handler,
        on_failure=worker_failure_handler,
    )


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


def worker(land_number: int):
    return json.dumps(asyncio.run(from_browser(land_number)))


def get_result_ttl_by_trees(land_state: t.ParsedLandState):
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


def get_result_ttl_by_windmills(land_state: t.ParsedLandState):
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


def worker_success_handler(job: rq.job.Job, connection, result, *args, **kwargs):
    parsed_land_state = p.parse(json.loads(result))
    result_ttl = min(
        get_result_ttl_by_trees(parsed_land_state), get_result_ttl_by_windmills(parsed_land_state)
    )
    job.result_ttl = result_ttl
    land_number: int = job.args[0]
    enqueue_in(land_number, time_delta=timedelta(seconds=result_ttl), queue=q.sync)


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
