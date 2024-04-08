from datetime import datetime
from typing import TypedDict


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
    is_blocked: bool
    total_players: int
    trees: list[ParsedTree]
    windmills: list[ParsedWindMill]
