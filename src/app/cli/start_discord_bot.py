import discord
from discord import app_commands
from ..lib.strategies.scraping import land_state as ls
from ..lib.redis import create_redis_connection
from .. import settings

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
guild = discord.Object(id=1228360466405920850)


@tree.command(name="trees")
async def send_land_trees(interaction: discord.Interaction, land_number: int):
    try:
        await interaction.response.send_message(f"> Fetching land {land_number} state ...")
        raw_state = await ls.from_browser(land_number)

        async with create_redis_connection() as redis:
            cached_state = await ls.to_cache(land_number, raw_state, 0, redis=redis)

        if cached_state:
            await interaction.followup.send(cached_state["state"]["id"])
        else:
            await interaction.followup.send("There is no data for the requested land")
    except Exception as error:
        await interaction.followup.send(repr(error))

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    tree.copy_global_to(guild=guild)
    await tree.sync(guild=guild)


def main():
    if not settings.DISCORD_BOT_TOKEN:
        raise Exception("DISCORD_BOT_TOKEN env variable is not defined")

    client.run(settings.DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    main()