from fastapi.routing import APIRouter

from . import services

router = APIRouter()
router.get("/land/{land_number:int}/state/")(services.get_land_state)
router.get("/marketplace/listing/")(services.get_marketplace_listing)
router.get("/land/states/")(services.get_cached_lands_states)
