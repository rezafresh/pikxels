from datetime import datetime
from typing import TypedDict


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


LandResource = ParsedLandTree | ParsedLandIndustry


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
