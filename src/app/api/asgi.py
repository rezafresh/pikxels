import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..lib.utils import get_logger
from .router import router
from .tasks import resource_hunter

logger = get_logger("app:asgi")


@asynccontextmanager
async def lifespan(app: FastAPI):
    current_loop = asyncio.get_running_loop()
    logger.info("Starting Resource Hunter Worker")
    rs_task = current_loop.create_task(resource_hunter.main(), name="resource-hunter")
    yield
    logger.info("Stopping Resource Hunter Worker")
    rs_task.cancel()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(HTTPException)
def _(request: Request, exc: HTTPException):
    return JSONResponse({"message": exc.detail, "details": repr(exc)}, exc.status_code)


@app.exception_handler(Exception)
def _(request: Request, exc: Exception):
    return JSONResponse({"message": "An unexpected error has ocurred", "details": repr(exc)}, 500)
