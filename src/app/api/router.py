from fastapi.routing import APIRouter

from . import controllers as ctrls

router = APIRouter()
router.get("/land/{land_number:int}/state/")(ctrls.get_land_state)
router.get("/lands/resources/")(ctrls.get_cached_lands_available_resources)
router.get("/metrics/cached/lands/")(ctrls.get_cached_lands)
