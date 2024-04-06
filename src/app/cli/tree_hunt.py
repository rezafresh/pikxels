from ..lib.strategies.scraping._queues import low as low_queue
from ..lib.strategies.scraping.land_state import enqueue as land_state_enqueue


def main():
    for i in range(5000):
        land_state_enqueue(i + 1, queue=low_queue)


if __name__ == "__main__":
    main()
