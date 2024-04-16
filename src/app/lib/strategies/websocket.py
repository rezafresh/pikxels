import time
from typing import TypedDict

import requests as rq
import websocket


class LandRoom(TypedDict):
    roomId: str
    server: str
    metadata: "LandRoomxMetadata"


class LandRoomxMetadata(TypedDict):
    world: int
    mapId: str
    name: str
    tenant: str


class LandSession(TypedDict):
    room: "LandSessionxRoom"
    sessionId: str


class LandSessionxRoom(TypedDict):
    clients: int
    createdAt: str
    maxClients: int
    metadata: "LandSessionxRoomxMetadata"
    name: str
    processId: str
    roomId: str


class LandSessionxRoomxMetadata(TypedDict):
    world: int
    mapId: str
    name: str
    tenant: str


def get_land_room(land_number: int) -> LandRoom:
    epoch_now = int(time.time())
    response = rq.get(
        f"https://pixels-server.pixels.xyz/game/findroom/pixelsNFTFarm-{land_number}/99?v={epoch_now}",
        headers={
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9,pt;q=0.8",
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "Referer": "https://play.pixels.xyz/",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        },
    )
    return response.json()


def get_land_session(land_room: LandRoom) -> LandSession:
    server_id, room_id = land_room["server"], land_room["roomId"]
    response = rq.post(
        f"https://pixels-server.pixels.xyz/matchmake/joinById/{room_id}/{server_id}",
        headers={
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9,pt;q=0.8",
            "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Linux"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "Referer": "https://play.pixels.xyz/",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        },
        json={
            "mapId": land_room["metadata"]["mapId"],
            "token": "iamguest",
            "isGuest": True,
            "cryptoWallet": {},
            "username": "Guest-the-traveling-tourist",
            "world": 99,
            "ver": 6.7,
            "avatar": "{}",
        },
    )
    return response.json()


def _get_land_websocket(land_session: LandSession):
    server_id, room_id, session_id = (
        land_session["room"]["processId"],
        land_session["room"]["roomId"],
        land_session["sessionId"],
    )
    return websocket.WebSocketApp(
        f"wss://pixels-server.pixels.xyz/{server_id}/{room_id}?sessionId={session_id}"
    )


def get_land_websocket(land_number: int):
    room = get_land_room(land_number)
    session = get_land_session(room)
    ws = _get_land_websocket(session)
    return ws
