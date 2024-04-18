import json
import time
from asyncio import Semaphore
from datetime import datetime, timedelta
from typing import TypedDict

from fastapi import HTTPException
from playwright.async_api import Page, async_playwright

from .... import settings
from ...redis import get_redis_connection
from ...utils import retry_until_valid


class LandState(TypedDict):
    createdAt: datetime
    expiresAt: datetime
    state: dict


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
    lastUpdated: datetime
    isBlocked: bool
    totalPlayers: int
    trees: list[ParsedTree]
    windmills: list[ParsedWindMill]


async def from_browser(land_number: int, semaphore: Semaphore) -> dict:
    async with semaphore:
        return await _from_browser(land_number)


async def _from_browser(land_number: int) -> dict:
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

        if (state_str := await phaser_land_state_getter(page)) is None:
            raise HTTPException(422, "Could not retrieve the land state")
        elif not state_str:
            raise HTTPException(422, "Invalid land state")

    return json.loads(state_str)


async def from_cache(land_number: int) -> LandState:
    async with get_redis_connection() as redis:
        if cached := await redis.get(f"app:land:{land_number}:state"):
            return json.loads(cached)

    return None


async def get(land_number: int, semaphore: Semaphore) -> LandState:
    if cached := await from_cache(land_number):
        return cached

    return await worker(land_number, semaphore)


async def worker(land_number: int, semaphore: Semaphore) -> LandState:
    async with get_redis_connection() as redis:
        raw_state = await from_browser(land_number, semaphore)
        seconds_to_expire = get_best_seconds_to_expire(raw_state)
        result: LandState = {
            "createdAt": (now := datetime.now()),
            "expiresAt": now + timedelta(seconds=seconds_to_expire),
            "state": raw_state,
        }
        await redis.set(
            f"app:land:{land_number}:state", json.dumps(result, default=str), ex=seconds_to_expire
        )

    return result


@retry_until_valid(tries=settings.PW_DEFAULT_TIMEOUT // 1000)
async def phaser_land_state_getter(page: Page):
    return await page.evaluate(
        "JSON.stringify(Phaser.Display.Canvas.CanvasPool.pool[0].parent.game.scene.scenes[1].stateManager.room.state)",
    )


def get_best_seconds_to_expire(raw_state: dict) -> int:
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    entities: dict = raw_state["entities"]
    trees = [v for _, v in entities.items() if v["entity"].startswith("ent_tree")]

    def extract_utc_refresh(t: dict) -> int:
        if utc_refresh := t["generic"].get("utcRefresh"):
            return utc_refresh // 1000
        return time.time()

    if trees:
        last_tree_respawn = datetime.fromtimestamp(max(extract_utc_refresh(t) for t in trees))
    else:
        last_tree_respawn = tomorrow

    windmills = [v for _, v in entities.items() if v["entity"].startswith("ent_windmill")]

    def extract_finish_time(wm: dict) -> int:
        statics: list[dict] = wm["generic"]["statics"]

        if finish_time_str := [_ for _ in statics if _["name"] == "finishTime"][0].get("value"):
            return int(finish_time_str) // 1000

        return time.time()

    if windmills:
        first_wm_available = datetime.fromtimestamp(
            min(extract_finish_time(wm) for wm in windmills)
        )
    else:
        first_wm_available = tomorrow

    result = min(last_tree_respawn, first_wm_available)
    return max(0, int((result - now).total_seconds()))
