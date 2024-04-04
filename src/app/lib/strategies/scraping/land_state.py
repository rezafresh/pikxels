import asyncio
import json
from datetime import datetime, timedelta
from random import randint
from typing import Union

import rq
from fastapi import HTTPException
from playwright.async_api import Page, async_playwright

from .... import settings
from ._queues import queue_default, queue_low
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
    def last_tree_respawn_in(self) -> timedelta:
        try:
            return self._get_last_tree_respawn_in()
        except Exception:
            return timedelta(seconds=randint(180, 300))

    def _get_last_tree_respawn_in(self) -> timedelta:
        entities: dict = self.state["entities"]
        max_utc_refresh = max(
            [
                value["generic"]["utcRefresh"]
                for key, value in entities.items()
                if value["entity"].startswith("ent_tree")
            ]
        )
        last_utc_refresh = datetime.fromtimestamp(max_utc_refresh / 1000)
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
        cls, land_number: int, queue: rq.Queue = queue_default
    ) -> Union["LandState", None]:
        if job := queue.fetch_job(f"app:land:{land_number}:state"):
            if cached := job.result:
                land_state = json.loads(cached)
                return LandState(land_number, land_state)
        return None

    @classmethod
    def get(cls, land_number: int, cached: bool = True):
        if cached and (land_state := cls.from_cache(land_number)):
            return land_state

        job = cls.enqueue(land_number)

        while True:
            if job.is_finished:
                return cls.from_cache(land_number)
            elif job.is_failed:
                return None

            continue

    @classmethod
    def enqueue(
        cls, land_number: int, *, queue: rq.Queue = queue_default
    ) -> rq.job.Job:
        return queue.enqueue(
            worker,
            land_number,
            job_id=f"app:land:{land_number}:state",
            result_ttl=-1,
            retry=rq.Retry(max=5, interval=[10, 30, 60, 120, 300]),
        )

    @classmethod
    def enqueue_in(
        cls, land_number: int, at: timedelta, *, queue: rq.Queue = queue_default
    ) -> rq.job.Job:
        return queue.enqueue_in(
            at,
            worker,
            land_number,
            job_id=f"app:land:{land_number}:state",
            result_ttl=-1,
            retry=rq.Retry(max=5, interval=[10, 30, 60, 120, 300]),
        )


@retry_until_valid(tries=10)
async def phaser_land_state_getter(page: Page):
    return await page.evaluate(
        "JSON.stringify(Phaser.Display.Canvas.CanvasPool.pool[0].parent.game.scene.scenes[1].stateManager.room.state)",
    )


def worker(land_number: int):
    land_state: LandState = asyncio.run(LandState.from_browser(land_number))
    LandState.enqueue_in(land_number, land_state.last_tree_respawn_in, queue=queue_low)
    return json.dumps(land_state.state)
