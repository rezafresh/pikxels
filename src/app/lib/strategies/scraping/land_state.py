import json
from datetime import datetime, timedelta
from typing import TypedDict

from fastapi import HTTPException
from playwright.async_api import Page, ProxySettings, ViewportSize, async_playwright
from redis.asyncio import Redis

from .... import settings
from ...utils import retry_until_valid


async def from_browser(land_number: int, *, proxy: ProxySettings = None) -> dict:
    async with async_playwright() as pw:
        browser = await pw.chromium.connect(
            settings.PW_WS_ENDPOINT,
            timeout=settings.PW_DEFAULT_TIMEOUT,
        )
        page = await browser.new_page(
            viewport=ViewportSize(width=10, height=10),
            screen=ViewportSize(width=10, height=10),
            is_mobile=True,
            proxy=proxy,
        )
        page.set_default_navigation_timeout(settings.PW_DEFAULT_TIMEOUT)
        page.set_default_timeout(settings.PW_DEFAULT_TIMEOUT)

        if not (
            response := await page.goto(f"https://play.pixels.xyz/pixels/share/{land_number}")
        ).ok:
            raise HTTPException(
                422, f"Failed to navigate to the land. [http-code {response.status}]"
            )

        if (state_str := await phaser_land_state_getter(page)) is None:
            raise HTTPException(422, "Could not retrieve the land state")
        elif not state_str:
            raise HTTPException(422, "Invalid land state")

    return json.loads(state_str)


class CachedLandState(TypedDict):
    createdAt: datetime
    expiresAt: datetime
    state: dict


async def from_cache(land_number: int, *, redis: Redis) -> CachedLandState | None:
    if cached := await redis.get(f"app:land:{land_number}:state"):
        return json.loads(cached)

    return None


async def to_cache(land_number: int, raw_state: dict, ex: int, *, redis: Redis) -> CachedLandState:
    result: CachedLandState = {
        "createdAt": (now := datetime.now()),
        "expiresAt": now + timedelta(seconds=ex),
        "state": raw_state,
    }
    # await redis.set(f"app:land:{land_number}:state", json.dumps(result, default=str), ex=ex)
    await redis.set(f"app:land:{land_number}:state", json.dumps(result, default=str))
    return result


@retry_until_valid(tries=settings.PW_DEFAULT_TIMEOUT // 1000)
async def phaser_land_state_getter(page: Page):
    return await page.evaluate(
        "JSON.stringify(Phaser.Display.Canvas.CanvasPool.pool[0].parent.game.scene.scenes[1].stateManager.room.state)",
    )


async def publish(land_number: int, state: CachedLandState, *, redis: Redis):
    await redis.publish(
        "app:lands:states:channel", json.dumps({"landNumber": land_number, **state}, default=str)
    )


class ParsedLandState(TypedDict):
    land_number: int
    is_blocked: bool
    trees: list["ParsedLandTree"]
    windmills: list["ParsedLandIndustry"]
    wineries: list["ParsedLandIndustry"]
    grills: list["ParsedLandIndustry"]
    kilns: list["ParsedLandIndustry"]


class LandEntityPosition(TypedDict):
    x: int
    y: int


class ParsedLandTree(TypedDict):
    mid: str
    entity: str
    position: LandEntityPosition
    state: str
    utcRefresh: datetime
    chops: int
    lastTimer: datetime
    lastChop: datetime


class ParsedLandIndustry(TypedDict):
    mid: str
    entity: str
    position: LandEntityPosition
    state: str
    allowPublic: bool
    inUseBy: str
    finishTime: datetime
    firedUntil: datetime


class LandStateParser:
    @classmethod
    def parse_tree(cls, raw_tree: dict) -> ParsedLandTree:
        generic: dict = raw_tree["generic"]

        if utc_refresh := generic.get("utcRefresh"):
            utc_refresh = datetime.fromtimestamp(utc_refresh // 1000)

        statics = {_["name"]: _["value"] for _ in generic["statics"]}
        statics["chops"] = int(statics.get("chops", 0))

        for fld in ["lastChop", "lastTimer"]:
            if _ := int(statics.get(fld, 0)):
                statics[fld] = datetime.fromtimestamp(_ // 1000)
            else:
                statics[fld] = None

        return {
            "mid": raw_tree["mid"],
            "entity": raw_tree["entity"],
            "position": raw_tree["position"],
            "state": raw_tree["generic"]["state"],
            "utcRefresh": utc_refresh,
            **statics,
        }

    @classmethod
    def parse_trees(cls, raw_state: dict) -> list[ParsedLandTree]:
        entities: dict = raw_state["entities"]
        trees = [_ for _ in entities.values() if _["entity"].startswith("ent_tree")]
        return [*map(cls.parse_tree, trees)]

    @classmethod
    def parse_industry(cls, raw_industry: dict) -> ParsedLandIndustry:
        generic: dict = raw_industry["generic"]
        statics = {_["name"]: _["value"] for _ in generic["statics"]}
        statics["allowPublic"] = bool(int(statics.get("allowPublic", 0)))

        for fld in ["finishTime", "firedUntil"]:
            if _ := int(statics.get(fld, 0)):
                statics[fld] = datetime.fromtimestamp(_ // 1000)
            else:
                statics[fld] = None

        return {
            "mid": raw_industry["mid"],
            "entity": raw_industry["entity"],
            "position": raw_industry["position"],
            "state": raw_industry["generic"].get("state"),
            **statics,
        }

    @classmethod
    def parse_industries(cls, raw_state: dict, entity: str) -> list[ParsedLandIndustry]:
        entities: dict = raw_state["entities"]
        industries = [_ for _ in entities.values() if _["entity"].startswith(entity)]
        return [*map(cls.parse_industry, industries)]

    @classmethod
    def parse(cls, raw_state: dict) -> ParsedLandState:
        return {
            "land_number": int(raw_state["nft"]["tokenId"]),
            "is_blocked": raw_state["permissions"]["use"][0] != "ANY",
            "trees": cls.parse_trees(raw_state),
            "windmills": cls.parse_industries(raw_state, "ent_windmill"),
            "grills": cls.parse_industries(raw_state, "ent_landbbq"),
            "kilns": cls.parse_industries(raw_state, "ent_kiln"),
            "wineries": cls.parse_industries(raw_state, "ent_winery"),
        }


def parse(raw_state: dict) -> ParsedLandState:
    return LandStateParser.parse(raw_state)
