import argparse
import json

from app.strategies.scraping import get_land_state


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--land", type=int, required=True)
    return parser.parse_known_args()[0]


def main():
    args = parse_args()
    result = json.dumps(get_land_state(args.land), indent=4)
    print(result)


if __name__ == "__main__":
    main()
