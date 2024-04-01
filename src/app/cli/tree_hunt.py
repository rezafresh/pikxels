from ..lib.strategies.scraping import LandState


def main():
    for i in range(1, 10):
        LandState.enqueue(i)


if __name__ == "__main__":
    main()
