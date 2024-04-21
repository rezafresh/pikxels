import os

import redis
import rq
import rq.logutils
import rq.worker_pool


def main():
    if not (redis_url := os.getenv("APP_REDIS_URL")):
        raise Exception("The 'APP_REDIS_URL' environment variable isn`t defined")

    concurrency = int(os.getenv("APP_CONCURRENCY", 1))
    worker_pool = rq.worker_pool.WorkerPool(
        ["default"], connection=redis.Redis.from_url(redis_url), num_workers=concurrency
    )
    return worker_pool.start()


if __name__ == "__main__":
    main()
