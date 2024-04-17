from concurrent.futures import ProcessPoolExecutor

from .. import settings

pool = ProcessPoolExecutor(max_workers=settings.CONCURRENCY)
