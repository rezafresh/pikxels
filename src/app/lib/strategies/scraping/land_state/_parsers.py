from datetime import datetime

from .._utils import unix_time_to_datetime
from . import types as t


def parse_tree(data: dict) -> t.ParsedTree:
    utc_refresh = unix_time_to_datetime(data["generic"].get("utcRefresh"))
    statics = {_["name"]: _["value"] for _ in data["generic"]["statics"]}
    last_timer = unix_time_to_datetime(statics["lastTimer"])
    last_chop = unix_time_to_datetime(statics["lastChop"])
    return {
        "entity": data["entity"],
        "position": data["position"],
        "state": data["generic"]["state"],
        "utcRefresh": utc_refresh,
        "lastChop": last_chop,
        "lastTimer": last_timer,
    }


def parse_trees(entities: dict) -> list[t.ParsedTree]:
    return sorted(
        [
            {"id": key, **parse_tree(value)}
            for key, value in entities.items()
            if value["entity"].startswith("ent_tree")
        ],
        key=lambda _: (_["utcRefresh"] or datetime.fromtimestamp(0)),
    )


def parse_windmill(data: dict) -> t.ParsedWindMill:
    statics = {_["name"]: _["value"] for _ in data["generic"]["statics"]}
    return {
        "entity": data["entity"],
        "position": data["position"],
        "allowPublic": bool(int(statics["allowPublic"])),
        "inUseBy": statics["inUseBy"],
        "finishTime": unix_time_to_datetime(statics["finishTime"]),
    }


def parse_windmills(entities: dict) -> list[t.ParsedWindMill]:
    return sorted(
        [
            {"id": key, **parse_windmill(value)}
            for key, value in entities.items()
            if value["entity"].startswith("ent_windmill")
        ],
        key=lambda _: (_["finishTime"] or datetime.fromtimestamp(0)),
    )


def parse(land_state: dict) -> t.ParsedLandState:
    return {
        "is_blocked": land_state["permissions"]["use"][0] != "ANY",
        "total_players": len(land_state["players"]),
        "trees": parse_trees(land_state["entities"]),
        "windmills": parse_windmills(land_state["entities"]),
    }
