import json

from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from ..lib.pixels import land_state as ls
from ..lib.redis import create_redis_connection


async def get_land_state(land_number: int):
    async with create_redis_connection() as redis:
        if cached := await ls.from_cache(land_number, redis=redis):
            return cached

    raise HTTPException(404, "There is no state cached for this land.")


async def stream_lands_states(websocket: WebSocket):
    try:
        await _stream_lands_states(websocket)
    except WebSocketDisconnect:
        pass


async def _stream_lands_states(websocket: WebSocket):
    await websocket.accept()

    while (await websocket.receive_text()) != "1":
        continue

    async with create_redis_connection() as redis:
        for i in range(5000):
            if state := await ls.from_cache(i + 1, redis=redis):
                await websocket.send_json(
                    {"message": {"type": "cached", "landNumber": i + 1, **state}}
                )

        ps = redis.pubsub(ignore_subscribe_messages=True)
        await ps.subscribe("app:lands:states:channel")

        while True:
            if not (message := await ps.get_message(timeout=None)):
                continue

            await websocket.send_json(
                {"message": {"type": "update", **json.loads(message["data"])}}
            )
