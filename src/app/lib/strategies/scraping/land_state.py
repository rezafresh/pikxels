import asyncio
import json
from datetime import datetime
from typing import Union, cast

import redis
import rq
from fastapi import HTTPException
from playwright.async_api import Page, async_playwright

from .... import settings
from ._utils import retry_until_valid


class LandState:
    queue = rq.Queue(
        connection=redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    )

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
    def trees(self):
        try:
            return self._parse_trees(self._state)
        except Exception:
            raise HTTPException(422, "Could not parse trees data")

    def _parse_trees(self, state: dict) -> list[dict]:
        entities: dict = state["entities"]
        results = []

        for item in entities.values():
            if not cast(str, item["entity"]).startswith("ent_tree"):
                continue

            try:
                next_state_in = datetime.fromtimestamp(
                    item["generic"]["utcRefresh"] / 1000
                )
            except Exception:
                next_state_in = None

            results.append(
                {
                    "entity": item["entity"],
                    "position": item["position"],
                    "current_state": item["generic"]["state"],
                    "next_state_in": next_state_in,
                }
            )

        return sorted(results, key=lambda _: (_["next_state_in"] or 0))

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
    def from_cache(cls, land_number: int) -> Union["LandState", None]:
        if job := cls.queue.fetch_job(f"app:land:{land_number}:state"):
            if cached := job.result:
                land_state = json.loads(cached)
                return LandState(land_number, land_state)
        return None

    @classmethod
    def get(cls, land_number: int):
        if land_state := cls.from_cache(land_number):
            return land_state

        job = cls.enqueue(land_number)

        while True:
            if job.is_finished:
                return cls.from_cache(land_number)
            elif job.is_failed:
                return None

            continue

    @classmethod
    def enqueue(cls, land_number: int) -> rq.job.Job:
        return cls.queue.enqueue(
            worker,
            land_number,
            job_id=f"app:land:{land_number}:state",
            result_ttl=settings.REDIS_DEFAULT_TTL,
        )


@retry_until_valid(tries=10)
async def phaser_land_state_getter(page: Page):
    return await page.evaluate(
        "JSON.stringify(Phaser.Display.Canvas.CanvasPool.pool[0].parent.game.scene.scenes[1].stateManager.room.state)",
    )


def worker(land_number: int):
    land_state: LandState = asyncio.run(LandState.from_browser(land_number))
    return json.dumps(land_state.state)
