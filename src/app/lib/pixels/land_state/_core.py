import json
from datetime import datetime, timedelta
from typing import TypedDict

from fastapi import HTTPException
from playwright.async_api import Page, ProxySettings, ViewportSize, async_playwright
from redis.asyncio import Redis

from .... import settings
from ...utils import retry_until_valid


async def from_browser(land_number: int, *, proxy: ProxySettings = None) -> dict:
    async with async_playwright() as pw:
        browser = await pw.chromium.connect(
            settings.PW_WS_ENDPOINT,
            timeout=settings.PW_DEFAULT_TIMEOUT,
        )
        page = await browser.new_page(
            viewport=ViewportSize(width=10, height=10),
            screen=ViewportSize(width=10, height=10),
            is_mobile=True,
            proxy=proxy,
        )
        page.set_default_navigation_timeout(settings.PW_DEFAULT_TIMEOUT)
        page.set_default_timeout(settings.PW_DEFAULT_TIMEOUT)

        if not (
            response := await page.goto(f"https://play.pixels.xyz/pixels/share/{land_number}")
        ).ok:
            raise HTTPException(
                422, f"Failed to navigate to the land. [http-code {response.status}]"
            )

        if (state_str := await phaser_land_state_getter(page)) is None:
            raise HTTPException(422, "Could not retrieve the land state")
        elif not state_str:
            raise HTTPException(422, "Invalid land state")

    return json.loads(state_str)


class CachedLandState(TypedDict):
    createdAt: datetime
    expiresAt: datetime
    state: dict


async def from_cache(land_number: int, *, redis: Redis) -> CachedLandState | None:
    if cached := await redis.get(f"app:land:{land_number}:state"):
        return json.loads(cached)

    return None


async def to_cache(land_number: int, raw_state: dict, ex: int, *, redis: Redis) -> CachedLandState:
    result: CachedLandState = {
        "createdAt": (now := datetime.now()),
        "expiresAt": now + timedelta(seconds=ex),
        "state": raw_state,
    }
    await redis.set(f"app:land:{land_number}:state", json.dumps(result, default=str))
    return result


@retry_until_valid(tries=settings.PW_DEFAULT_TIMEOUT // 1000)
async def phaser_land_state_getter(page: Page) -> str:
    return await page.evaluate(
        "JSON.stringify(Phaser.Display.Canvas.CanvasPool.pool[0].parent.game.scene.scenes[1].stateManager.room.state)",
    )


async def publish(land_number: int, state: CachedLandState, *, redis: Redis):
    await redis.publish(
        "app:lands:states:channel", json.dumps({"landNumber": land_number, **state}, default=str)
    )
