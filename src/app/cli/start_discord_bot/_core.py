import asyncio
import json

import discord
from discord import app_commands

from ... import settings
from ...lib.pixels import land_state as ls
from ...lib.redis import create_redis_connection
from ...lib.utils import get_logger
from ._utils import filter_resources, format_land_resources_message

# import re



logger = get_logger("app:discord-bot")


# async def send_from_cache():
#     async with create_redis_connection() as redis:
#         while True:
#             keys = await redis.keys("app:land:*:state")
#             land_numbers = [int(re.search("\d+", _).group(0)) for _ in keys]
#             states = [ls.parse(await ls.from_cache(_, redis=redis)) for _ in land_numbers]


class Client(discord.Client):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

    async def on_ready(self):
        logger.info(f"We have logged in as {self.user}")
        self._guild = await self.fetch_guild(settings.DISCORD_BOT_GUILD_ID)
        self._trees_tracker_channel = await self._guild.fetch_channel(
            settings.DISCORD_BOT_TRACK_TREES_CHANNEL_ID
        )
        self._industries_tracker_channel = await self._guild.fetch_channel(
            settings.DISCORD_BOT_TRACK_INDUSTRIES_CHANNEL_ID
        )
        self._cmd_tree = app_commands.CommandTree(self)
        self._cmd_tree.command(name="resources")(self.send_land_available_resources)
        self._cmd_tree.copy_global_to(guild=self._guild)
        await self._cmd_tree.sync(guild=self._guild)
        asyncio.create_task(self.listen_for_land_updates())

    async def send_land_available_resources(interaction: discord.Interaction, land_number: int):
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
                f"{lr_message['trees']}\n{lr_message['indutries']}"
            )
            await interaction.followup.send(message)
        except Exception as error:
            logger.error(repr(error))
            await interaction.followup.send(repr(error))

    async def listen_for_land_updates(self):
        logger.info("The 'listen for land updates' feature is running")

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
                    elif not (fmtd_message := format_land_resources_message(parsed)):
                        continue

                    if fmtd_message["trees"]:
                        await self._trees_tracker_channel.send(fmtd_message["trees"])

                    if fmtd_message["indutries"]:
                        await self._industries_tracker_channel.send(fmtd_message["indutries"])
                except asyncio.CancelledError:
                    break
                except Exception as error:
                    logger.error(f"listen_for_land_updates: {error!r}")


def create_discord_client() -> discord.Client:
    return Client()
