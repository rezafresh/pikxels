import os
from concurrent.futures import ThreadPoolExecutor, wait

import redis
import rq


def main():
    if not (redis_url := os.getenv("APP_REDIS_URL")):
        raise Exception("The 'APP_REDIS_URL' environment variable isn`t defined")

    concurrency = int(os.getenv("APP_CONCURRENCY", 1))
    connection = redis.Redis.from_url(redis_url)
    workers = [rq.worker.Worker(["default"], connection=connection) for _ in range(concurrency)]

    with ThreadPoolExecutor(concurrency) as executor:
        tasks = [executor.submit(workers[0].work, with_scheduler=True)]
        tasks.extend(executor.submit(w.work) for w in workers[1:])
        wait(tasks)


if __name__ == "__main__":
    main()
