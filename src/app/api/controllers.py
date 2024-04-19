import json

from fastapi import HTTPException, WebSocket, WebSocketDisconnect

from ..lib.redis import get_redis_connection
from ..lib.strategies.scraping import land_state as ls


async def get_land_state(land_number: int):
    if cached := await ls.from_cache(land_number):
        return cached

    raise HTTPException(404, "There is no state cached for this land.")


async def stream_lands_states(websocket: WebSocket):
    try:
        await _stream_lands_states(websocket)
    except WebSocketDisconnect:
        pass


async def _stream_lands_states(websocket: WebSocket):
    await websocket.accept()

    for i in range(5000):
        if state := await ls.from_cache(i + 1):
            await websocket.send_json({"message": {"type": "cached", "landNumber": i + 1, **state}})

    async with get_redis_connection() as redis:
        ps = redis.pubsub(ignore_subscribe_messages=True)
        await ps.subscribe("app:lands:states:channel")

        while True:
            if not (message := await ps.get_message(timeout=None)):
                continue

            await websocket.send_json(
                {"message": {"type": "update", **json.loads(message["data"])}}
            )
