import json
from datetime import datetime
from typing import Union, cast

from fastapi import HTTPException
from playwright.async_api import async_playwright
from redis import Redis

from .... import settings
from ._utils import phaser_land_state_getter

redis = Redis()


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
    def trees(self):
        try:
            return self._parse_trees(self._state)
        except Exception:
            raise HTTPException(422, "Could not parse trees data")

    def save_to_cache(self):
        redis.set(
            f"land-{self.land_number}-state",
            json.dumps(self.state),
            ex=settings.REDIS_DEFAULT_TTL,
        )

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
                    settings.BROWSERLESS_URL,
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
        if serialized_state := redis.get(f"land-{land_number}-state"):
            state = json.loads(serialized_state)
            return LandState(land_number, state)
        return None

    @classmethod
    async def get(cls, land_number: int):
        if land_state := cls.from_cache(land_number):
            return land_state

        land_state = await cls.from_browser(land_number)
        land_state.save_to_cache()
        return land_state
