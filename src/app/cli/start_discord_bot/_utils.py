from datetime import datetime
from typing import Callable, Iterable, TypedDict

from ...lib.pixels import land_state as ls


class FormatedLandResources(TypedDict):
    trees: list[ls.ParsedLandTree]
    indutries: list[ls.ParsedLandIndustry]


def filter_resources(
    parsed_state: ls.ParsedLandState, lb_secs: int, hb_secs: int
) -> ls.ParsedLandState:
    now = datetime.now()

    def get_ent_finish_time(item: ls.LandResource) -> datetime:
        return item.get("utcRefresh") or item.get("finishTime") or now

    def predicate(item: ls.LandResource) -> bool:
        if not (dt := get_ent_finish_time(item)):
            return True
        delta = (dt - now).total_seconds()
        return lb_secs < delta < hb_secs

    def filter_and_sort(it: Iterable):
        return sorted([*filter(predicate, it)], key=get_ent_finish_time)

    result: ls.ParsedLandState = {
        **parsed_state,
        "trees": filter_and_sort(filter(lambda _: _.get("current", 4) >= 4, parsed_state["trees"])),
        "grills": filter_and_sort(parsed_state["grills"]),
        "kilns": filter_and_sort(parsed_state["kilns"]),
        "windmills": filter_and_sort(parsed_state["windmills"]),
        "wineries": filter_and_sort(parsed_state["wineries"]),
    }
    return result


def format_land_resources_message(parsed_state: ls.ParsedLandState) -> FormatedLandResources:
    def make_message(resource: ls.LandResource) -> str:
        if resource["entity"].startswith("ent_tree"):
            description = f"🌲 Tree [**{resource['state']}**]"
        elif resource["entity"].startswith("ent_windmill"):
            description = "🌀 WindMill"
        elif resource["entity"].startswith("ent_landbbq"):
            description = "🍖 Grill"
        elif resource["entity"].startswith("ent_kiln"):
            description = "🪨 Kiln"
        elif resource["entity"].startswith("ent_winery"):
            description = "🍇 Winery"
        else:
            description = f"🤷‍♂️ {resource['entity']}"

        if dt := resource.get("utcRefresh") or resource.get("finishTime"):
            availability = f"<t:{int(dt.timestamp())}:R>"
        else:
            availability = "**Available**"

        return f"**#{parsed_state['land_number']}** {description} {availability}"

    return {
        "trees": "\n".join(map(make_message, parsed_state["trees"])),
        "indutries": "\n".join(
            map(
                make_message,
                [
                    *parsed_state["grills"],
                    *parsed_state["windmills"],
                    *parsed_state["wineries"],
                    *parsed_state["kilns"],
                ],
            )
        ),
    }


def extract_items(it: list[dict], predicate: Callable[[dict], None]):
    results = []
    while (i := 0) < len(it):
        if predicate(it[i]):
            results.append(it.pop(i))
        else:
            i += 1
    return results
