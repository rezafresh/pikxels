import argparse
from datetime import datetime

from app.strategies.websocket import get_land_websocket


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--land", type=int, required=True)
    return parser.parse_known_args()[0]


def main():
    args = parse_args()
    ws = get_land_websocket(args.land)

    def on_message_handler(_, data: bytes):
        print(datetime.now().isoformat())
        print(data.decode("utf8", errors="ignore"))
        if data[0] == 10:
            ws.send_bytes(bytearray([10]))

    ws.on_message = on_message_handler
    ws.run_forever()


if __name__ == "__main__":
    main()
