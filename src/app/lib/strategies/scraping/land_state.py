import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Union

import rq
from fastapi import HTTPException
from playwright.async_api import Page, async_playwright

from .... import settings
from . import _queues as q
from ._utils import retry_until_valid


class LandState:
    def __init__(self, land_number, state: dict) -> None:
        self._land_number = land_number
        self._state = state

    @property
    def land_number(self):
        return self._land_number

    @property
    def state(self):
        return self._state

    @property
    def last_tree_respawn_in(self) -> timedelta | None:
        return self.get_last_tree_respawn_in()

    def get_last_tree_respawn_in(self) -> timedelta | None:
        entities: dict = self.state["entities"]
        max_utc_refreshes = [
            value["generic"].get("utcRefresh", time.time() / 1000)
            for _, value in entities.items()
            if value["entity"].startswith("ent_tree")
        ]

        if not max_utc_refreshes:
            return None

        last_utc_refresh = datetime.fromtimestamp(max(max_utc_refreshes) / 1000)
        now = datetime.now()
        return last_utc_refresh - now

    @classmethod
    async def from_browser(cls, land_number: int) -> "LandState":
        async with async_playwright() as pw:
            try:
                browser = await pw.chromium.connect_over_cdp(
                    settings.BROWSERLESS_CDP_ENDPOINT_URL,
                    timeout=settings.BROWSERLESS_DEFAULT_TIMEOUT,
                )
            except Exception:
                raise HTTPException(
                    422, "An error has ocurred while connecting to the chrome instance"
                )

            context = await browser.new_context()
            page = await context.new_page()
            page.set_default_navigation_timeout(settings.BROWSERLESS_DEFAULT_TIMEOUT)
            page.set_default_timeout(settings.BROWSERLESS_DEFAULT_TIMEOUT)

            try:
                if not (
                    await page.goto(
                        f"https://play.pixels.xyz/pixels/share/{land_number}"
                    )
                ).ok:
                    raise HTTPException(
                        404, "An error has ocurred while navigating to the land"
                    )

                await page.wait_for_load_state("load")

                try:
                    state_str = await phaser_land_state_getter(page)
                except Exception:
                    raise HTTPException(422, "Could not fetch the land state")

                try:
                    state = json.loads(state_str)
                except Exception:
                    raise HTTPException(422, "Could not parse land state data")
            finally:
                await page.close()
                await context.close()
                await browser.close()

        return LandState(land_number, state)

    @classmethod
    def from_cache(
        cls, land_number: int, *, queue: rq.Queue = q.default
    ) -> Union["LandState", None]:
        if job := queue.fetch_job(f"app:land:{land_number}:state"):
            if latest := job.latest_result():
                if cached := latest.return_value:
                    return LandState(land_number, json.loads(cached))
        return None

    @classmethod
    def enqueue(cls, land_number: int, *, queue: rq.Queue = q.default) -> rq.job.Job:
        return queue.enqueue(
            worker, land_number, job_id=f"app:land:{land_number}:state"
        )

    @classmethod
    def enqueue_in(
        cls, land_number: int, time_delta: timedelta, *, queue: rq.Queue = q.default
    ) -> rq.job.Job:
        return queue.enqueue_in(
            time_delta, worker, land_number, job_id=f"app:land:{land_number}:state"
        )

    @classmethod
    def get(cls, land_number: int, cached: bool = True):
        if cached and (land_state := cls.from_cache(land_number)):
            return land_state

        job = cls.enqueue(land_number)

        while not (job.is_finished or job.is_failed):
            time.sleep(1)

        if not job.result:
            raise HTTPException(422, "The job returned a invalid land state")

        return LandState(land_number, json.loads(job.result))


@retry_until_valid(tries=10)
async def phaser_land_state_getter(page: Page):
    return await page.evaluate(
        "JSON.stringify(Phaser.Display.Canvas.CanvasPool.pool[0].parent.game.scene.scenes[1].stateManager.room.state)",
    )


def worker(land_number: int):
    land_state: LandState = asyncio.run(LandState.from_browser(land_number))

    try:
        if not (
            result_ttl := max(0, int(land_state.last_tree_respawn_in.total_seconds()))
        ):
            result_ttl = 86400  # 1 day
    except Exception:
        result_ttl = 86400  # 1 day

    rq.job.get_current_job().result_ttl = result_ttl
    LandState.enqueue_in(land_number, timedelta(seconds=result_ttl), queue=q.low)
    return json.dumps(land_state.state)
