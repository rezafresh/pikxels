import os
from multiprocessing import Process

import redis
import rq


def _main():
    if not (redis_url := os.getenv("APP_REDIS_URL")):
        raise Exception("The 'APP_REDIS_URL' environment variable isn`t defined")

    concurrency = int(os.getenv("APP_CONCURRENCY", 1))
    connection = redis.Redis.from_url(redis_url)
    workers = [
        rq.worker.Worker(queues=["default"], connection=connection) for _ in range(concurrency)
    ]
    processes = [Process(target=w.work, daemon=True) for w in workers]
    [p.start() for p in processes]
    [p.join() for p in processes]


def main():
    try:
        _main()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
