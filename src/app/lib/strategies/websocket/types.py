from typing import TypedDict


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
