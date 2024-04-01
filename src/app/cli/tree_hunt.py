from ..lib.strategies.scraping import LandState


def main():
    for i in range(5000):
        LandState.enqueue(i + 1)


if __name__ == "__main__":
    main()
