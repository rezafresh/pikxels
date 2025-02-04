import asyncio
import logging
from datetime import datetime
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


def unix_time_to_datetime(unix_time: str | int | None) -> datetime | None:
    if isinstance(unix_time, str):
        if (unix_time_int := int(unix_time)) > 0:
            return datetime.fromtimestamp(int(unix_time_int) // 1000)
        return None
    elif isinstance(unix_time, int) and unix_time > 0:
        return datetime.fromtimestamp(unix_time // 1000)

    return None


def parse_datetime(dt: str | datetime | None, dt_fmt: str = "%Y-%m-%d %H:%M:%S") -> datetime | None:
    if isinstance(dt, datetime):
        return dt
    if isinstance(dt, str):
        if dt_parsed := datetime.strptime(dt, dt_fmt):
            return dt_parsed

    return None


def get_logger(name: str) -> logging.Logger:
    result = logging.getLogger(name)
    result.setLevel(logging.INFO)
    result.addHandler(_ := logging.StreamHandler())
    _.setFormatter(logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
    return result
