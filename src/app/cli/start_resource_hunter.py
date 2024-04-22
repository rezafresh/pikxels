from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime
from random import randint
from time import sleep

import rq
import rq.results

from ..jobs import resource_hunter as rh


def handler(land_number: int):
    while True:
        if isinstance(result := dispatch_job(land_number), tuple):
            _, job_result = result
            expires_at: datetime = job_result["expiresAt"]

            if not (delta := int((expires_at - datetime.now()).total_seconds())):
                delta = randint(60, 600)

            print(f"Waiting land {land_number} for {delta} seconds")
            sleep(delta)
        else:
            print(f"Waiting result for land {land_number} [{result.get_status()!s}]")
            sleep(1)


def dispatch_job(land_number: int) -> rq.job.Job | tuple[rq.job.Job, rq.results.Result]:
    if job := rh.queue.fetch_job(f"app:land:{land_number}:job"):
        if (job_status := job.get_status()) in [rq.job.JobStatus.QUEUED, rq.job.JobStatus.STARTED]:
            return job
        elif job_status == rq.job.JobStatus.FINISHED:
            if job.result:
                if job.result["expiresAt"] > datetime.now():
                    return job, job.result
    print(f"Dispatching job for land {land_number}")
    return rh.enqueue(land_number)


def main():
    with ThreadPoolExecutor(max_workers=5000) as executor:
        tasks = [executor.submit(handler, i + 1) for i in range(executor._max_workers)]
        wait(tasks)


if __name__ == "__main__":
    main()
