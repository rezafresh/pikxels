import math
import os
from subprocess import Popen


def start_worker_pool(queue: list[str], workers_count: int):
    return Popen(
        [
            "rq",
            "worker-pool",
            "-n",
            str(workers_count),
            "-u",
            os.getenv("APP_REDIS_URL"),
            " ".join(queue),
        ]
    )


def _main():
    if not (max_concurrency := int(os.getenv("BROWSERLESS_CONCURRENT", 0))):
        raise Exception("The 'BROWSERLESS_CONCURRENT' environment variable is note defined")

    default_queue_concurrency = math.floor(max_concurrency * 0.6)
    sync_queue_concurrency = max_concurrency - default_queue_concurrency
    processes = [
        start_worker_pool(["default", "sync"], default_queue_concurrency),
        start_worker_pool(["sync", "default"], sync_queue_concurrency),
    ]

    while True:
        try:
            for p in processes:
                p.wait()
            break
        except KeyboardInterrupt:
            pass


def main():
    _main()


if __name__ == "__main__":
    main()
