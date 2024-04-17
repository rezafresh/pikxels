from fastapi.routing import APIRouter

from . import controllers

router = APIRouter()
router.get("/land/{land_number:int}/state/")(controllers.get_land_state)
router.get("/lands/resources/")(controllers.get_cached_lands_available_resources)
