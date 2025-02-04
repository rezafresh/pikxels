from playwright.async_api import ProxySettings

from . import _webshare as webshare


def create_proxy_yielder():
    def yielder():
        if not (proxies := webshare.fetch_proxy_list()):
            raise Exception("There is no proxy to serve")

        while True:
            for proxy in proxies:
                yield ProxySettings(
                    server=f"http://{proxy['proxy_address']}:{proxy['port']}",
                    username=proxy["username"],
                    password=proxy["password"],
                )

    _yielder = yielder()
    return lambda: next(_yielder)
