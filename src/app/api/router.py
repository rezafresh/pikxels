from fastapi.routing import APIRouter

from . import controllers as ctrls

router = APIRouter()
router.get("/land/{land_number:int}/state/")(ctrls.get_land_state)
router.websocket("/land/states/stream/")(ctrls.stream_lands_states)
