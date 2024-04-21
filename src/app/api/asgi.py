from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..lib.utils import get_logger
from .router import router

logger = get_logger("app:asgi")


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


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
