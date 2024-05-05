from datetime import datetime

import discord
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
channel = discord.Object(id=1233643605650964521)


def prepare_resources(
    parsed_state: ls.ParsedLandState, lower_bound_seconds: int, higher_bound_seconds: int
) -> list[ls.ParsedLandTree | ls.ParsedLandIndustry]:
    now = datetime.now()

    def get_ent_finish_time(item: ls.ParsedLandTree | ls.ParsedLandIndustry) -> datetime:
        return item.get("utcRefresh") or item.get("finishTime") or now

    def predicate(item: ls.ParsedLandTree | ls.ParsedLandIndustry) -> bool:
        if not (dt := get_ent_finish_time(item)):
            return True
        delta = (dt - now).total_seconds()
        return lower_bound_seconds < delta < higher_bound_seconds

    resources = [
        *filter(predicate, parsed_state["trees"]),
        *filter(predicate, parsed_state["grills"]),
        *filter(predicate, parsed_state["kilns"]),
        *filter(predicate, parsed_state["windmills"]),
        *filter(predicate, parsed_state["wineries"]),
    ]
    return sorted(resources, key=get_ent_finish_time)


def format_resources_message(resources: list[ls.ParsedLandTree | ls.ParsedLandIndustry]) -> str:
    def get_description(item: ls.ParsedLandTree | ls.ParsedLandIndustry, availability: str) -> str:
        if item["entity"].startswith("ent_tree"):
            description = f"🌲 Tree [**{item['state']}**]"
        elif item["entity"].startswith("ent_windmill"):
            description = "🌀 WindMill"
        elif item["entity"].startswith("ent_landbbq"):
            description = "🍖 Grill"
        elif item["entity"].startswith("ent_kiln"):
            description = "🪨 Kiln"
        elif item["entity"].startswith("ent_winery"):
            description = "🍇 Winery"
        else:
            description = f"🤷‍♂️ {item['entity']}"

        return f"{description} {availability}"

    def make_message(item: ls.ParsedLandTree | ls.ParsedLandIndustry) -> str:
        if dt := item.get("utcRefresh") or item.get("finishTime"):
            availability = f"<t:{int(dt.timestamp())}:R> "
        else:
            availability = "**Available**"

        return get_description(item, availability)

    result = "\n".join(make_message(_) for _ in resources)
    return result


@tree.command(name="resources")
async def send_land_available_resources(
    interaction: discord.Interaction, land_number: int, threshold: int = 600
):
    if interaction.channel.id != channel.id:
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

        parsed_state = ls.parse(land_number, cached_state["state"])

        if resources := prepare_resources(parsed_state, -120, threshold):
            message = format_resources_message(resources)
            await interaction.followup.send(message)
        else:
            await interaction.followup.send(
                f"**There is no resource available in the next {threshold} seconds**"
            )
    except Exception as error:
        logger.error(repr(error))
        await interaction.followup.send(repr(error))


@client.event
async def on_ready():
    logger.info(f"We have logged in as {client.user}")
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)


def main():
    if not settings.DISCORD_BOT_TOKEN:
        raise Exception("DISCORD_BOT_TOKEN env variable is not defined")

    client.run(settings.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    main()
