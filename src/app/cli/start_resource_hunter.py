import os
from datetime import datetime
from time import sleep

import redis
import rq
import rq.registry
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

    connection = redis.Redis.from_url(redis_url)
    queued_registry = rq.registry.StartedJobRegistry(connection=connection)

    try:
        while True:
            sleep(2)

            if queued_registry.count > 0:
                print(f"There is {queued_registry.count} jobs to handle left")
                continue

            print("Searching for Resources ...")
            enqueued_jobs = [*filter(bool, [enqueue_job(i + 1) for i in range(MAX_LANDS_TO_SCAN)])]
            print(f"Found {len(enqueued_jobs)}")
    except Exception as error:
        print(repr(error))


def main():
    try:
        _main()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
