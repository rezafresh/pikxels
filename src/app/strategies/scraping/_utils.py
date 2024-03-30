from time import sleep
from typing import Callable

from playwright.sync_api import Page


def retry_until_valid(*, tries: int = 3):
    def wrapper(f: Callable):
        def g(*args, **kwargs):
            _tries = tries
            while _tries > 0:
                try:
                    if result := f(*args, **kwargs):
                        break
                except Exception:
                    sleep(1)
                    _tries -= 1
            return result

        return g

    return wrapper


@retry_until_valid(tries=10)
def phaser_land_state_getter(page: Page):
    return page.evaluate(
        "JSON.stringify(Phaser.Display.Canvas.CanvasPool.pool[0].parent.game.scene.scenes[1].stateManager.room.state)",
    )
