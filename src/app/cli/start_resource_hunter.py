from datetime import datetime
from time import sleep

import rq
import rq.registry
from rq.job import JobStatus

from ..jobs import resource_hunter as rh

MAX_LANDS_TO_SCAN = 5000


def enqueue_job(land_number: int) -> rq.job.Job | None:
    if not (job := rh.queue.fetch_job(f"app:land:{land_number}:job")):
        job = rh.enqueue(land_number)
        return job
    elif (job_status := job.get_status()) == JobStatus.FINISHED:
        expires_at: datetime = job.result["expiresAt"]

        if int((expires_at - datetime.now()).total_seconds()) > 0:
            return None

        return rh.enqueue(land_number)
    elif job_status == JobStatus.FAILED:
        return job.requeue(True)


def main():
    print("Starting Resource Hunter Loop")

    while True:
        sleep(2)

        if rh.queue.count > 0:
            print(f"There is {rh.queue.count} jobs left to handle")
            continue

        print("Searching for Resources ...")
        enqueued_jobs = [*filter(bool, [enqueue_job(i + 1) for i in range(MAX_LANDS_TO_SCAN)])]
        print(f"Found {len(enqueued_jobs)}")


if __name__ == "__main__":
    main()
