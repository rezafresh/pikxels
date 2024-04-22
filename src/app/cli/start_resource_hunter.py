import os
from datetime import datetime
from random import randint

import redis
import rq
import rq.worker_pool
from rq.job import JobStatus

from ..jobs import resource_hunter as rh


def create_worker_pool() -> rq.worker_pool.WorkerPool:
    if not (redis_url := os.getenv("APP_REDIS_URL")):
        raise Exception("The 'APP_REDIS_URL' environment variable isn`t defined")

    concurrency = int(os.getenv("APP_CONCURRENCY", 1))
    connection = redis.Redis.from_url(redis_url)
    worker_pool = rq.worker_pool.WorkerPool(
        queues=["default"], connection=connection, num_workers=concurrency
    )
    return worker_pool


def _handler(land_number: int, job: rq.job.Job):
    if (job_status := job.get_status()) == JobStatus.FINISHED:
        # print(f"Job {job.id} [{job_status!s}]")
        expires_at: datetime = job.result["expiresAt"]

        if not (delta := int((expires_at - datetime.now()).total_seconds())) <= 0:
            delta = randint(60, 300)

        print(f"Waiting job {job.id} for {delta} seconds")
        return rh.enqueue(land_number)
    elif job_status == JobStatus.FAILED:
        print(f"Retrying failed job {job.id}")
        return job.requeue(True)
    return job


def handler(land_number: int):
    if not (job := rh.queue.fetch_job(f"app:land:{land_number}:job")):
        job = rh.enqueue(land_number)
        print(f"Enqueueing new job {job.id}")
        return job

    return _handler(land_number, job)


def main():
    worker_pool = create_worker_pool()

    while True:
        for i in range(5000):
            handler(i + 1)
        worker_pool.start(burst=True)


if __name__ == "__main__":
    main()
