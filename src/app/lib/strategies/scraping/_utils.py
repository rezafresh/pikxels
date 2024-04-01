from time import sleep
from typing import Awaitable

from playwright.async_api import Page


def retry_until_valid(*, tries: int = 3):
    def wrapper(f: Awaitable):
        async def g(*args, **kwargs):
            _tries = tries
            while _tries > 0:
                try:
                    if result := await f(*args, **kwargs):
                        break
                except Exception:
                    sleep(2)
                    _tries -= 1
            return result

        return g

    return wrapper


@retry_until_valid(tries=10)
async def phaser_land_state_getter(page: Page):
    return await page.evaluate(
        "JSON.stringify(Phaser.Display.Canvas.CanvasPool.pool[0].parent.game.scene.scenes[1].stateManager.room.state)",
    )
