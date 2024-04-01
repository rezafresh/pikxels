from time import sleep
from typing import Awaitable


def retry_until_valid(*, tries: int = 3):
    def wrapper(f: Awaitable):
        async def g(*args, **kwargs):
            _tries = tries
            while _tries > 0:
                try:
                    if result := await f(*args, **kwargs):
                        return result
                except Exception:
                    sleep(2)
                    _tries -= 1

        return g

    return wrapper
