from typing import TypedDict

from httpx import Client
from playwright.async_api import ProxySettings

from ... import settings

client = Client(headers={"Authorization": f"Token {settings.WEBSHARE_TOKEN}"})


class WebshareProxy(TypedDict):
    id: str
    username: str
    password: str
    proxy_address: str
    port: int
    valid: bool
    last_verification: str
    country_code: str
    city_name: str
    created_at: str


def fetch_proxy_list() -> list[WebshareProxy]:
    response = client.get(
        "https://proxy.webshare.io/api/v2/proxy/list/?mode=direct&page=1&page_size=25"
    )
    response.raise_for_status()
    return response.json().get("results", [])


def create_proxy_yielder():
    def yielder():
        while True:
            try:
                if proxies := fetch_proxy_list():
                    for proxy in proxies:
                        yield ProxySettings(
                            server=f"http://{proxy['proxy_address']}:{proxy['port']}",
                            username=proxy["username"],
                            password=proxy["password"],
                        )
                else:
                    yield None
            except Exception as error:
                print(repr(error))
                yield None


    _yielder = yielder()
    return lambda: next(_yielder)
