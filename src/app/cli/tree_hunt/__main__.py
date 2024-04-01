import time

import rq
from redis import Redis

from .workers import worker

queue = rq.Queue(connection=Redis())


def main():
    tasks = [queue.enqueue(worker, i) for i in range(1, 5)]

    while not all(t.is_finished for t in tasks):
        time.sleep(1)


if __name__ == "__main__":
    main()
