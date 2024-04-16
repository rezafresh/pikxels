import asyncio
import json
from datetime import datetime, timedelta
from random import randint
from typing import TypedDict

from fastapi import HTTPException
from playwright.async_api import Page, async_playwright

from .... import settings
from ...executor import pool
from ...redis import get_redis_connection
from ...utils import retry_until_valid, unix_time_to_datetime

LandState = dict


class LandStateMeta(TypedDict):
    updatedAt: datetime
    expiresAt: datetime


LandStateJobResult = tuple[LandState, LandStateMeta]


class LandEntityPosition(TypedDict):
    x: int
    y: int


class ParsedTree(TypedDict):
    entity: str
    position: LandEntityPosition
    state: str
    utcRefresh: datetime | None
    lastChop: datetime | None
    lastTimer: datetime | None


class ParsedWindMill(TypedDict):
    entity: str
    position: LandEntityPosition
    allowPublic: bool
    inUseBy: str
    finishTime: datetime | None


class ParsedLandState(TypedDict):
    lastUpdated: datetime
    isBlocked: bool
    totalPlayers: int
    trees: list[ParsedTree]
    windmills: list[ParsedWindMill]


async def from_browser(land_number: int) -> dict:
    async with async_playwright() as pw:
        browser = await pw.chromium.connect(
            settings.PW_WS_ENDPOINT,
            timeout=settings.PW_DEFAULT_TIMEOUT,
        )
        page = await browser.new_page()
        page.set_default_navigation_timeout(settings.PW_DEFAULT_TIMEOUT)
        page.set_default_timeout(settings.PW_DEFAULT_TIMEOUT)

        if not (await page.goto(f"https://play.pixels.xyz/pixels/share/{land_number}")).ok:
            raise HTTPException(422, "An error has ocurred while navigating to the land")

        if (state_str := await phaser_land_state_getter(page)) is None:
            raise HTTPException(422, "Could not retrieve the land state")
        elif not state_str:
            raise HTTPException(422, "Invalid land state")

    return json.loads(state_str)


def from_cache(land_number: int) -> LandStateJobResult | None:
    with get_redis_connection() as redis:
        if cached := redis.get(f"app:land:{land_number}:state"):
            result = json.loads(cached)

            if cached_meta := redis.get(f"app:land:{land_number}:state:meta"):
                return result, json.loads(cached_meta)

            return result, {}

    return None


def get(land_number: int, *, raw: bool = False) -> LandStateJobResult:
    if not (result := from_cache(land_number)):
        result = pool.submit(worker, land_number).result()

    return result if raw else (parse(result[0]), result[1])


def worker(land_number: int) -> LandStateJobResult:
    with get_redis_connection() as redis:
        result: dict = asyncio.run(from_browser(land_number))
        result_as_str = json.dumps(result, default=str)
        best_ex_time = get_best_expiration_seconds(result)
        meta = {
            "updatedAt": (now := datetime.now()),
            "expiresAt": now + timedelta(seconds=best_ex_time),
        }
        redis.set(f"app:land:{land_number}:state", result_as_str, ex=best_ex_time)
        redis.set(f"app:land:{land_number}:state:meta", json.dumps(meta, default=str))
        redis.hset("app:lands:states", str(land_number), result_as_str)

    return result, meta


@retry_until_valid(tries=settings.PW_DEFAULT_TIMEOUT // 1000)
async def phaser_land_state_getter(page: Page):
    return await page.evaluate(
        "JSON.stringify(Phaser.Display.Canvas.CanvasPool.pool[0].parent.game.scene.scenes[1].stateManager.room.state)",
    )


def parse_tree(data: dict) -> ParsedTree:
    utc_refresh = unix_time_to_datetime(data["generic"].get("utcRefresh"))
    statics = {_["name"]: _["value"] for _ in data["generic"]["statics"]}
    last_timer = unix_time_to_datetime(statics["lastTimer"])
    last_chop = unix_time_to_datetime(statics["lastChop"])
    return {
        "entity": data["entity"],
        "position": data["position"],
        "state": data["generic"].get("state"),
        "utcRefresh": utc_refresh,
        "lastChop": last_chop,
        "lastTimer": last_timer,
    }


def parse_trees(entities: dict) -> list[ParsedTree]:
    return sorted(
        [
            {"id": key, **parse_tree(value)}
            for key, value in entities.items()
            if value["entity"].startswith("ent_tree")
        ],
        key=lambda _: (_["utcRefresh"] or datetime.fromtimestamp(0)),
    )


def parse_windmill(data: dict) -> ParsedWindMill:
    statics = {_["name"]: _["value"] for _ in data["generic"]["statics"]}
    return {
        "entity": data["entity"],
        "position": data["position"],
        "allowPublic": bool(int(statics["allowPublic"])),
        "inUseBy": statics["inUseBy"],
        "finishTime": unix_time_to_datetime(statics["finishTime"]),
    }


def parse_windmills(entities: dict) -> list[ParsedWindMill]:
    return sorted(
        [
            {"id": key, **parse_windmill(value)}
            for key, value in entities.items()
            if value["entity"].startswith("ent_windmill")
        ],
        key=lambda _: (_["finishTime"] or datetime.fromtimestamp(0)),
    )


def parse(state: LandState) -> ParsedLandState:
    return {
        "isBlocked": state["permissions"]["use"][0] != "ANY",
        "totalPlayers": len(state["players"]),
        "trees": parse_trees(state["entities"]),
        "windmills": parse_windmills(state["entities"]),
    }


def get_expiration_by_trees(land_state: ParsedLandState):
    if not land_state.get("trees"):
        # if the land doesnt have trees
        return 86400  # 1 day
    elif not land_state["trees"][0]["utcRefresh"]:
        # if the next tree is available
        return randint(60, 300)  # between 1 and 5 minutes
    elif utc_refresh := land_state["trees"][-1]["utcRefresh"]:
        # if all trees are in cooldown, scan again when the last one finish
        return max(60, int((utc_refresh - datetime.now()).total_seconds()))
    else:
        return 3600  # 1 hour


def get_expiration_by_windmills(land_state: ParsedLandState):
    if not land_state.get("windmills"):
        # if the land doesnt have trees
        return 86400  # 1 day
    elif not land_state["windmills"][0]["finishTime"]:
        # if the next tree is available
        return randint(60, 300)  # between 1 and 5 minutes
    elif finish_time := land_state["windmills"][-1]["finishTime"]:
        # if all trees are in cooldown, scan again when the last one finish
        return max(60, int((finish_time - datetime.now()).total_seconds()))
    else:
        return 3600  # 1 hour


def get_best_expiration_seconds(state: LandState) -> int:
    parsed_state = parse(state)
    return min(
        get_expiration_by_trees(parsed_state),
        get_expiration_by_windmills(parsed_state),
    )
