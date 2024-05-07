import asyncio
import json
from datetime import datetime
from typing import Iterable, TypedDict

import discord
from discord import app_commands
from httpx import AsyncClient
from redis.asyncio.client import PubSub

from .. import settings
from ..lib.pixels import land_state as ls
from ..lib.redis import create_redis_connection
from ..lib.utils import get_logger

logger = get_logger("app:discord-bot")
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
cmd_tree = app_commands.CommandTree(client)
guild = discord.Object(id=1228360466405920850)
http = AsyncClient()


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


@cmd_tree.command(name="resources")
async def send_land_available_resources(interaction: discord.Interaction, land_number: int):
    if interaction.channel.id != 1233643605650964521:
        return await interaction.response.send_message(
            "**I dont have permission to use this channel**"
        )

    try:
        await interaction.response.send_message(f"**Fetching land {land_number} resources**")

        async with create_redis_connection() as redis:
            if not (cached_state := await ls.from_cache(land_number, redis=redis)):
                return await interaction.followup.send(
                    "**There is no data for the requested land**"
                )

        parsed_state = ls.parse(cached_state["state"])
        lr_message = format_land_resources_message(parsed_state)
        message = (
            f"> Created => **{cached_state['createdAt']}**\n"
            f"> Expires => **{cached_state['expiresAt']}**\n\n"
            f"{lr_message['trees']}\n{lr_message['industires']}"
        )
        await interaction.followup.send(message)
    except Exception as error:
        logger.error(repr(error))
        await interaction.followup.send(repr(error))


async def _listen_for_land_updates(ps: PubSub):
    if not (message := await ps.get_message(timeout=None)):
        return

    state = json.loads(message["data"])
    parsed = filter_resources(ls.parse(state["state"]), -120, 180)

    if parsed["is_blocked"]:
        return
    elif not (fmtd_message := format_land_resources_message(parsed)):
        return

    await http.post(
        settings.DISCORD_BOT_TRACK_TREES_CHANNEL_WH, json={"content": fmtd_message["trees"]}
    )
    await http.post(
        settings.DISCORD_BOT_TRACK_INDUSTRIES_CHANNEL_WH,
        json={"content": fmtd_message["indutries"]},
    )


async def listen_for_land_updates():
    if not settings.DISCORD_BOT_TRACK_TREES_CHANNEL_WH:
        return logger.warning(
            "The APP_DISCORD_BOT_TRACK_TREES_CHANNEL_WH env variable is not defined."
            "The 'listen for land updates' feature will be disabled."
        )
    elif not settings.DISCORD_BOT_TRACK_INDUSTRIES_CHANNEL_WH:
        return logger.warning(
            "The APP_DISCORD_BOT_TRACK_INDUSTRIES_CHANNEL_WH env variable is not defined."
            "The 'listen for land updates' feature will be disabled."
        )

    logger.info("The 'listen for land updates' feature is running")

    async with create_redis_connection() as redis:
        ps = redis.pubsub(ignore_subscribe_messages=True)
        await ps.subscribe("app:lands:states:channel")

        while True:
            try:
                await _listen_for_land_updates(ps)
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.error(f"listen_for_land_updates: {error!r}")


@client.event
async def on_ready():
    logger.info(f"We have logged in as {client.user}")
    cmd_tree.copy_global_to(guild=guild)
    await cmd_tree.sync(guild=guild)
    asyncio.create_task(listen_for_land_updates())


def _main():
    if not settings.DISCORD_BOT_TOKEN:
        raise Exception("APP_DISCORD_BOT_TOKEN env variable is not defined")

    client.run(settings.DISCORD_BOT_TOKEN)


def main():
    try:
        _main()
    except Exception as error:
        logger.error(repr(error))


if __name__ == "__main__":
    main()
