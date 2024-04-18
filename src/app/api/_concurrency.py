import math
from asyncio import Semaphore

from .. import settings

sema_api = Semaphore(math.ceil(settings.CONCURRENCY * 0.05))
sema_tasks = Semaphore(math.floor(settings.CONCURRENCY * 0.95))
