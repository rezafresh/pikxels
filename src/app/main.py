import httpx


def main():
    url = "wss://pixels-server.pixels.xyz/rq_VP5tjQ/M38cmBWQs?sessionId=u2-AO5wZd"
    headers = {
        # "Pragma": "no-cache",
        # "Origin": "https://play.pixels.xyz",
        # "Accept-Language": "en-US,en;q=0.9,pt;q=0.8",
        # "Sec-WebSocket-Key": "R0yZvcxRNbuAsyYALWQnzQ==",
        # "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        # "Upgrade": "websocket",
        # "Cache-Control": "no-cache",
        # "Connection": "Upgrade",
        # "Sec-WebSocket-Version": "13",
        # "Sec-WebSocket-Extensions": "permessage-deflate; client_max_window_bits"
        "accept-language": "en-US,en;q=0.9,pt;q=0.8",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "sec-websocket-extensions": "permessage-deflate; client_max_window_bits",
        "sec-websocket-key": "uoK53+CsSZKTVNxgb879+Q==",
        "sec-websocket-version": "13"
    }

    with httpx.stream("GET", url, headers=headers) as response:
        for data in response.iter_bytes():
            print(data)


if __name__ == "__main__":
    main()
