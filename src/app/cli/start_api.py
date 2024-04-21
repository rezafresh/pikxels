import argparse
import os

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", action="store_true")
    return parser.parse_known_args()[0]


def main():
    args = parse_args()
    port = int(os.getenv("API_PORT", 9000))
    uvicorn.run("src.app.api.asgi:app", port=port, host="0.0.0.0", reload=args.reload)


if __name__ == "__main__":
    main()
