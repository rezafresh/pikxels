import argparse
import json

from ..strategies.scraping import get_land_state


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--land", type=int, required=True)
    return parser.parse_known_args()[0]


def main():
    args = parse_args()
    result = get_land_state(args.land)
    print(json.dumps(result, indent=4))


if __name__ == "__main__":
    main()
