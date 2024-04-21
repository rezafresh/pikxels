import os

import redis
import rq
import rq.worker_pool


def main():
    if not (redis_url := os.getenv("APP_REDIS_URL")):
        raise Exception("The 'APP_REDIS_URL' environment variable isnt defined")

    concurrency = int(os.getenv("APP_CONCURRENCY", 1))
    worker = rq.worker_pool.WorkerPool(
        ["default"], connection=redis.Redis.from_url(redis_url), num_workers=concurrency
    )
    worker.start()


if __name__ == "__main__":
    main()
