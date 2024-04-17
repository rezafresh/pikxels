from asyncio import Semaphore

from .. import settings

semaphore = Semaphore(settings.CONCURRENCY)
