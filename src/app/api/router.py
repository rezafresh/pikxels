from fastapi.routing import APIRouter

from ..lib.strategies.scraping import LandState

router = APIRouter()


@router.get("/land/{land_number:int}/state/")
async def get_land_state_route(land_number: int):
    return {"state": (await LandState.get(land_number)).state}


@router.get("/land/{land_number:int}/trees/")
async def get_land_trees_route(land_number: int):
    land_state = await LandState.get(land_number)
    return {
        "is_blocked": land_state.state["permissions"]["use"][0] != "ANY",
        "trees": land_state.trees,
    }
