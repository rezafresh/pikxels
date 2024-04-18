import json

from fastapi import WebSocket

from ..lib.redis import get_redis_connection
from ..lib.strategies.scraping import land_state as ls


async def get_land_state(land_number: int):
    return await ls.get(land_number)


async def stream_lands_states(websocket: WebSocket):
    await websocket.accept()

    async with get_redis_connection() as redis:
        ps = redis.pubsub()
        await ps.subscribe("app:lands:states:channel")

        while True:
            if message := await ps.get_message(ignore_subscribe_messages=True, timeout=None):
                message_as_json = json.loads(message["data"])
                await websocket.send_json(message_as_json)
