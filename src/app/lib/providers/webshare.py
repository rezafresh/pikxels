from typing import TypedDict

from httpx import Client

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
