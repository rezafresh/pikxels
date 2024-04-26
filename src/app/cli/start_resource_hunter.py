import os
from datetime import datetime
from time import sleep

import rq
import rq.registry
import sentry_sdk
from playwright.async_api import ProxySettings
from rq.job import JobStatus

from .. import settings
from ..jobs import resource_hunter as rh
from ..lib.proxy import create_proxy_yielder
from ..lib.utils import get_logger

logger = get_logger("app:resource-hunter")
MAX_LANDS_TO_SCAN = 5000


def enqueue_job(land_number: int, *, proxy: ProxySettings = None) -> rq.job.Job | None:
    if not (job := rh.queue.fetch_job(f"app:land:{land_number}:job")):
        job = rh.enqueue(land_number, proxy=proxy)
        return job
    elif (job_status := job.get_status()) == JobStatus.FINISHED:
        expires_at: datetime = job.result["expiresAt"]

        if int((expires_at - datetime.now()).total_seconds()) > 0:
            return None

        return rh.enqueue(land_number, proxy=proxy)
    elif job_status == JobStatus.FAILED:
        return rh.enqueue(land_number, proxy=proxy)


def _main():
    while True:
        sleep(2)

        if rh.queue.count > 0:
            logger.info(f"There is {rh.queue.count} jobs left to handle")
            continue

        if settings.PW_PROXY_ENABLED:
            get_proxy = create_proxy_yielder()
        else:
            get_proxy = lambda: None  # noqa

        logger.info("Searching for Resources ...")
        enqueued_jobs = [
            *filter(bool, [enqueue_job(i + 1, proxy=get_proxy()) for i in range(MAX_LANDS_TO_SCAN)])
        ]
        logger.info(f"Found {len(enqueued_jobs)}")


def main():
    logger.info("Starting Resource Hunter Loop")

    if RH_SENTRY_DSN := os.getenv("RH_SENTRY_DSN"):
        sentry_sdk.init(
            dsn=RH_SENTRY_DSN,
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )

    if settings.PW_PROXY_ENABLED:
        if not settings.WEBSHARE_TOKEN:
            raise Exception(
                "Proxy use is enable, but APP_WEBSHARE_TOKEN environment variable is empty"
            )
        logger.info("Proxy is enabled")

    _main()


if __name__ == "__main__":
    main()
