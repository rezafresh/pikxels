from ..jobs import resource_hunter


def main():
    for i in range(0, 5000):
        resource_hunter.dispatch_job(i + 1)


if __name__ == "__main__":
    main()
