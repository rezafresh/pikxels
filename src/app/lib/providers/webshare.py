from typing import TypedDict

from httpx import Client
from playwright.async_api import ProxySettings

WEBSHARE_TOKEN = "bj00u9pn5eanb7zc982jheaej7iyeooz1y8oun8u"
client = Client(headers={"Authorization": f"Token {WEBSHARE_TOKEN}"})


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

    if response.status_code != 200:
        raise Exception("webshare: Failed to fetch proxy list")

    return response.json().get("results", [])


def _create_proxy_yielder():
    while True:
        for proxy in fetch_proxy_list():
            yield ProxySettings(
                server=f"http://{proxy['proxy_address']}:{proxy['port']}",
                username=proxy["username"],
                password=proxy["password"],
            )


get_available_proxy = _create_proxy_yielder()
