import asyncio
import json
import time
from datetime import datetime, timedelta

import rq
from fastapi import HTTPException
from playwright.async_api import Error as PWError
from playwright.async_api import Page, async_playwright

from .... import settings
from . import _queues as q
from ._utils import retry_until_valid


def get_last_tree_next_stage_seconds(land_state: dict) -> int | None:
    entities: dict = land_state["entities"]

    trees = [value for _, value in entities.items() if value["entity"].startswith("ent_tree")]
    max_utc_refreshes = [tree["generic"].get("utcRefresh", time.time() / 1000) for tree in trees]

    if not max_utc_refreshes:
        return None

    last_utc_refresh = datetime.fromtimestamp(max(max_utc_refreshes) / 1000)
    now = datetime.now()
    return int((last_utc_refresh - now).total_seconds())


async def from_browser(land_number: int) -> dict:
    async with async_playwright() as pw:
        browser = await pw.chromium.connect_over_cdp(
            settings.PW_CDP_ENDPOINT_URL,
            timeout=settings.PW_DEFAULT_TIMEOUT,
        )
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_navigation_timeout(settings.PW_DEFAULT_TIMEOUT)
        page.set_default_timeout(settings.PW_DEFAULT_TIMEOUT)

        try:
            if not (await page.goto(f"https://play.pixels.xyz/pixels/share/{land_number}")).ok:
                raise HTTPException(422, "An error has ocurred while navigating to the land")

            await page.wait_for_load_state("load")
            state_str = await phaser_land_state_getter(page)
        finally:
            await page.close()
            await context.close()
            await browser.close()

    return json.loads(state_str)


def from_cache(land_number: int) -> dict | None:
    if job := q.default.fetch_job(f"app:land:{land_number}:state"):
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
    if cached and (land_state := from_cache(land_number)):
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


@retry_until_valid(tries=30)
async def phaser_land_state_getter(page: Page):
    return await page.evaluate(
        "JSON.stringify(Phaser.Display.Canvas.CanvasPool.pool[0].parent.game.scene.scenes[1].stateManager.room.state)",
    )


def worker(land_number: int):
    return json.dumps(asyncio.run(from_browser(land_number)))


def worker_success_handler(job: rq.job.Job, connection, result, *args, **kwargs):
    land_state = json.loads(result)

    if (result_ttl := get_last_tree_next_stage_seconds(land_state) or 60) > 0:
        job.result_ttl = result_ttl
    else:
        job.result_ttl = 60

    land_number: int = job.args[0]
    enqueue_in(land_number, time_delta=timedelta(seconds=result_ttl), queue=q.low)


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
