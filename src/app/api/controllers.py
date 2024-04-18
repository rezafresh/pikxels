import json

from fastapi import WebSocket, WebSocketDisconnect

from ..lib.redis import get_redis_connection
from ..lib.strategies.scraping import land_state as ls
from ._concurrency import sema_api


async def get_land_state(land_number: int):
    return await ls.get(land_number, sema_api)


async def stream_lands_states(websocket: WebSocket):
    await websocket.accept()

    async with get_redis_connection() as redis:
        ps = redis.pubsub()
        await ps.subscribe("app:lands:states:channel")

        while True:
            try:
                if not (
                    message := await ps.get_message(ignore_subscribe_messages=True, timeout=None)
                ):
                    continue

                message_as_json = json.loads(message["data"])
                await websocket.send_json(message_as_json)
            except WebSocketDisconnect:
                break
