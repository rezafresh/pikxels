from concurrent.futures import ThreadPoolExecutor

from .. import settings

pool = ThreadPoolExecutor(max_workers=settings.CONCURRENCY)
