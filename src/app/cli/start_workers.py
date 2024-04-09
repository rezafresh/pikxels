import math
import os
from multiprocessing import Process

import rq
import rq.scheduler

from ..lib.strategies.scraping import _queues as q


def create_workers(queues: list[rq.Queue], count: int) -> list[rq.Worker]:
    return [rq.Worker(queues, connection=q._redis, default_worker_ttl=-1) for _ in range(count)]


def main():
    if not (concurrency := int(os.getenv("BROWSERLESS_MAX_CONCURRENT_SESSIONS", 0))):
        raise Exception("BROWSERLESS_MAX_CONCURRENT_SESSIONS env variable is not defined")

    default_queue_workers = math.floor(concurrency * 0.6)
    sync_queue_workers = concurrency - default_queue_workers

    workers = [
        *create_workers([q.default], default_queue_workers),
        *create_workers([q.sync], sync_queue_workers),
    ]
    processes = [Process(target=w.work) for w in workers]

    for p in processes:
        p.start()

    processes.append(rq.scheduler.RQScheduler([q.sync], q._redis).start())

    for p in processes:
        p.join()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
