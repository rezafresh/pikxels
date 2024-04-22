import rq

from ..jobs import resource_hunter as rh


def dispatch_job(land_number: int) -> rq.job.Job | None:
    if job := rh.queue.fetch_job(f"app:land:{land_number}:job"):
        if job.get_status() in [rq.job.JobStatus.QUEUED, rq.job.JobStatus.SCHEDULED]:
            return None
        return job
    return rh.enqueue(land_number)


def main():
    for i in range(0, 5000):
        dispatch_job(i + 1)


if __name__ == "__main__":
    main()
