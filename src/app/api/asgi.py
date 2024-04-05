from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .router import router

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
def _(request: Request, exc: HTTPException):
    return JSONResponse({"message": exc.detail, "details": repr(exc)}, exc.status_code)


@app.exception_handler(Exception)
def _(request: Request, exc: Exception):
    return JSONResponse({"message": "An unexpected error has ocurred", "details": repr(exc)}, 500)


app.include_router(router)
