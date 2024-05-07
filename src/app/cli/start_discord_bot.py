import asyncio
import json
from datetime import datetime
from typing import Iterable

import discord
import httpx
from discord import app_commands

from .. import settings
from ..lib.redis import create_redis_connection
from ..lib.strategies.scraping import land_state as ls
from ..lib.utils import get_logger

logger = get_logger("app:discord-bot")
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
guild = discord.Object(id=1228360466405920850)
LandResource = ls.ParsedLandTree | ls.ParsedLandIndustry


def filter_resources(
    parsed_state: ls.ParsedLandState, lb_secs: int, hb_secs: int
) -> ls.ParsedLandState:
    now = datetime.now()

    def get_ent_finish_time(item: LandResource) -> datetime:
        return item.get("utcRefresh") or item.get("finishTime") or now

    def predicate(item: LandResource) -> bool:
        if not (dt := get_ent_finish_time(item)):
            return True
        delta = (dt - now).total_seconds()
        return lb_secs < delta < hb_secs

    def filter_and_sort(it: Iterable):
        return sorted([*filter(predicate, it)], key=get_ent_finish_time)

    result: ls.ParsedLandState = {
        **parsed_state,
        "trees": filter_and_sort(parsed_state["trees"]),
        "grills": filter_and_sort(parsed_state["grills"]),
        "kilns": filter_and_sort(parsed_state["kilns"]),
        "windmills": filter_and_sort(parsed_state["windmills"]),
        "wineries": filter_and_sort(parsed_state["wineries"]),
    }
    return result


def format_land_resources_message(parsed_state: ls.ParsedLandState) -> str:
    result = ""

    if parsed_state["is_blocked"]:
        result += f"**#{parsed_state['land_number']}** is Blocked\n"

    def get_description(item: LandResource) -> str:
        if item["entity"].startswith("ent_tree"):
            return f"🌲 Tree [**{item['state']}**]"
        elif item["entity"].startswith("ent_windmill"):
            return "🌀 WindMill"
        elif item["entity"].startswith("ent_landbbq"):
            return "🍖 Grill"
        elif item["entity"].startswith("ent_kiln"):
            return "🪨 Kiln"
        elif item["entity"].startswith("ent_winery"):
            return "🍇 Winery"
        else:
            return f"🤷‍♂️ {item['entity']}"

    def make_message(resource: LandResource) -> str:
        if dt := resource.get("utcRefresh") or resource.get("finishTime"):
            availability = f"<t:{int(dt.timestamp())}:R>"
        else:
            availability = "**Available**"

        return f"**#{parsed_state['land_number']}** {get_description(resource)} {availability}"

    resources = [
        *parsed_state["trees"],
        *parsed_state["grills"],
        *parsed_state["windmills"],
        *parsed_state["wineries"],
        *parsed_state["kilns"],
    ]
    result += "\n".join(map(make_message, resources))
    return result


@tree.command(name="resources")
async def send_land_available_resources(
    interaction: discord.Interaction, land_number: int, threshold: int = 600
):
    if interaction.channel.id != 1233643605650964521:
        return await interaction.response.send_message(
            "**I dont have permission to use this channel :/**"
        )

    threshold = max(60, threshold)

    try:
        await interaction.response.send_message(
            f"**Fetching land {land_number} resources availables in the next {threshold} seconds**"
        )

        async with create_redis_connection() as redis:
            if not (cached_state := await ls.from_cache(land_number, redis=redis)):
                return await interaction.followup.send(
                    "**There is no data for the requested land**"
                )

        if parsed_state := ls.parse(cached_state["state"]):
            await interaction.followup.send(format_land_resources_message(parsed_state))
        else:
            await interaction.followup.send(
                f"**There is no resource available in the next {threshold} seconds**"
            )
    except Exception as error:
        logger.error(repr(error))
        await interaction.followup.send(repr(error))


async def send_land_updates_loop(channel_wh: str):
    async with create_redis_connection() as redis:
        ps = redis.pubsub(ignore_subscribe_messages=True)
        await ps.subscribe("app:lands:states:channel")

        while True:
            try:
                if not (message := await ps.get_message(timeout=None)):
                    continue

                state = json.loads(message["data"])
                parsed = filter_resources(ls.parse(state["state"]), -120, 180)

                if parsed["is_blocked"]:
                    continue

                if fmtd_message := format_land_resources_message(parsed):
                    httpx.post(channel_wh, json={"content": fmtd_message})
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.error(f"send_land_updates_loop: {error!r}")


@client.event
async def on_ready():
    logger.info(f"We have logged in as {client.user}")
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)

    if settings.DISCORD_BOT_TRACK_CHANNEL_WH:
        task = asyncio.create_task(send_land_updates_loop(settings.DISCORD_BOT_TRACK_CHANNEL_WH))
        task.cancel


def main():
    if not settings.DISCORD_BOT_TOKEN:
        raise Exception("DISCORD_BOT_TOKEN env variable is not defined")

    client.run(settings.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
