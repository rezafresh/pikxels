import os

import redis
import rq
import rq.worker_pool


def main():
    if not (redis_url := os.getenv("APP_REDIS_URL")):
        raise Exception("The 'APP_REDIS_URL' environment variable isn`t defined")

    concurrency = int(os.getenv("APP_CONCURRENCY", 1))
    connection = redis.Redis.from_url(redis_url)
    worker_pool = rq.worker_pool.WorkerPool(
        queues=["default"], connection=connection, num_workers=concurrency
    )
    worker_pool.start()


if __name__ == "__main__":
    main()
