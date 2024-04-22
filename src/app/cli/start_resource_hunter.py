import os
from datetime import datetime

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


def enqueue_job(land_number: int):
    if not (job := rh.queue.fetch_job(f"app:land:{land_number}:job")):
        jid = rh.enqueue(land_number).id
        print(f"Enqueueing new job {jid}")
    elif (job_status := job.get_status()) == JobStatus.FINISHED:
        expires_at: datetime = job.result["expiresAt"]

        if int((expires_at - datetime.now()).total_seconds()) > 0:
            return

        print(f"Job {job.id} expired, requeuing")
        rh.enqueue(land_number)
    elif job_status == JobStatus.FAILED:
        print(f"Retrying failed job {job.id}")
        job.requeue(True)


def main():
    worker_pool = create_worker_pool()

    while True:
        for i in range(5000):
            enqueue_job(i + 1)

        worker_pool.start(burst=True)


if __name__ == "__main__":
    main()
