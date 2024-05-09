from ... import settings
from ._core import create_discord_client, logger


def main():
    try:
        if not settings.DISCORD_BOT_TOKEN:
            raise Exception("APP_DISCORD_BOT_TOKEN env variable is not defined")
        elif not settings.DISCORD_BOT_TRACK_TREES_CHANNEL_ID:
            raise Exception(
                "The APP_DISCORD_BOT_TRACK_TREES_CHANNEL_ID env variable is not defined."
            )
        elif not settings.DISCORD_BOT_TRACK_INDUSTRIES_CHANNEL_ID:
            raise Exception(
                "The APP_DISCORD_BOT_TRACK_INDUSTRIES_CHANNEL_ID env variable is not defined."
            )

        client = create_discord_client()
        client.run(settings.DISCORD_BOT_TOKEN)
    except Exception as error:
        logger.error(repr(error))


main()
