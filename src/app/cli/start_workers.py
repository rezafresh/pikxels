import math
import os
from multiprocessing import Process

import rq
import rq.worker_pool

from ..lib.strategies.scraping import _queues as q


def main():
    if not (concurrency := int(os.getenv("BROWSERLESS_MAX_CONCURRENT_SESSIONS", 0))):
        raise Exception("BROWSERLESS_MAX_CONCURRENT_SESSIONS env variable is not defined")

    default_queue_workers = math.floor(concurrency * 0.6)
    sync_queue_workers = concurrency - default_queue_workers
    workers = [
        rq.worker_pool.WorkerPool([q.default], q._redis, default_queue_workers),
        rq.worker_pool.WorkerPool([q.sync], q._redis, sync_queue_workers),
    ]
    processes = [Process(target=w.start) for w in workers]

    for p in processes:
        p.start()

    for p in processes:
        p.join()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
