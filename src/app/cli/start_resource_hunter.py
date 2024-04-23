import os
from datetime import datetime
from multiprocessing import Process
from time import sleep

import redis
import rq
from rq.job import JobStatus

from ..jobs import resource_hunter as rh

MAX_LANDS_TO_SCAN = 5000


def enqueue_job(land_number: int) -> rq.job.Job | None:
    if not (job := rh.queue.fetch_job(f"app:land:{land_number}:job")):
        job = rh.enqueue(land_number)
        print(f"Enqueueing new job {job.id}")
        return job
    elif (job_status := job.get_status()) == JobStatus.FINISHED:
        expires_at: datetime = job.result["expiresAt"]

        if int((expires_at - datetime.now()).total_seconds()) > 0:
            return None

        print(f"Job {job.id} expired, requeuing")
        return rh.enqueue(land_number)
    elif job_status == JobStatus.FAILED:
        print(f"Retrying failed job {job.id}")
        return job.requeue(True)


def _main():
    if not (redis_url := os.getenv("APP_REDIS_URL")):
        raise Exception("The 'APP_REDIS_URL' environment variable isn`t defined")

    concurrency = int(os.getenv("APP_CONCURRENCY", 1))
    connection = redis.Redis.from_url(redis_url)
    workers = [
        rq.worker.Worker(queues=["default"], name=f"worker-{_}", connection=connection)
        for _ in range(concurrency)
    ]

    while True:
        enqueued_jobs = [*filter(bool, [enqueue_job(i + 1) for i in range(MAX_LANDS_TO_SCAN)])]

        if not enqueued_jobs:
            sleep(5)
            continue

        processes = [
            Process(target=w.work, args=(True,), daemon=True)
            for w in workers[: min(concurrency, len(enqueued_jobs))]
        ]
        [p.start() for p in processes]
        [p.join() for p in processes]


def main():
    try:
        _main()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
