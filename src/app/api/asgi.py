from cachetools import TTLCache, cached
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..strategies.scraping import get_land_state as _get_land_state
from ..strategies.scraping import parse_tree_data

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@cached(cache=TTLCache(maxsize=5000, ttl=30))
def get_land_state(land_number: int):
    return _get_land_state(land_number)


@app.get("/land/{land_number:int}/state/")
def get_land_state_route(land_number: int):
    return {"state": get_land_state(land_number)}


@app.get("/land/{land_number:int}/trees/")
def get_trees_route(land_number: int):
    state = get_land_state(land_number)
    return {
        "is_blocked": state["permissions"]["use"][0] != "ANY",
        "trees": parse_tree_data(state),
    }
