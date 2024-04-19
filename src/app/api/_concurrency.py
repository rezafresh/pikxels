from asyncio import Semaphore

from .. import settings

sema_tasks = Semaphore(settings.CONCURRENCY)
