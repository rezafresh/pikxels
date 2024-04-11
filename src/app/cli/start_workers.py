import math
import os
from multiprocessing import Process

import rq
import rq.worker_pool

from src.app.lib.strategies.scraping import _queues as q


def _main():
    if not (max_concurrency := int(os.getenv("BROWSERLESS_CONCURRENT", 0))):
        raise Exception("The 'BROWSERLESS_CONCURRENT' environment variable is note defined")

    default_queue_concurrency = math.floor(max_concurrency * 0.6)
    sync_queue_concurrency = max_concurrency - default_queue_concurrency
    workers = [
        rq.worker_pool.WorkerPool([q.default], q._redis, default_queue_concurrency),
        rq.worker_pool.WorkerPool([q.sync], q._redis, sync_queue_concurrency),
    ]
    processes = [Process(target=w.start) for w in workers]

    for p in processes:
        p.start()

    for p in processes:
        p.join()


def main():
    try:
        _main()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
