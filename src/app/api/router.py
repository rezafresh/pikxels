from fastapi import HTTPException
from fastapi.routing import APIRouter

from ..lib.strategies.scraping import LandState

router = APIRouter()


@router.get("/land/{land_number:int}/state/")
def get_land_raw_state_route(land_number: int, cached: bool = True):
    if land_state := LandState.get(land_number, cached):
        return {"state": land_state.state}
    raise HTTPException(422, "Could not retrieve the land state. Try again later.")
