import logging

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def http_exception_handler(request: Request, exc: HTTPException):
    # Standardized error shape
    payload = {
        "error": {
            "code": exc.status_code,
            "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "details": None,
        }
    }
    return JSONResponse(status_code=exc.status_code, content=payload)


def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception")
    payload = {
        "error": {
            "code": 500,
            "message": "Internal Server Error",
            "details": str(exc),
        }
    }
    return JSONResponse(status_code=500, content=payload)
