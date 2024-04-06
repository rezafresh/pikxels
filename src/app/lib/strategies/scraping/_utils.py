import asyncio
from typing import Awaitable


def retry_until_valid(*, tries: int = 10):
    def wrapper(f: Awaitable):
        async def g(*args, **kwargs):
            _tries = tries
            while _tries > 0:
                try:
                    if result := await f(*args, **kwargs):
                        return result
                except Exception:
                    await asyncio.sleep(1)
                    _tries -= 1
            return None

        return g

    return wrapper
