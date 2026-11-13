"""FastAPI application entry point for SatBhoomi Score + Raksha.

Implements versioned API Contract v1 (blueprint section 8) with mock server mode.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from satbhoomi.api.routes import api_v1_router
from satbhoomi.config.settings import get_settings

API_CONTRACT_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager validating security and environment constraints at startup."""
    current_settings = get_settings()
    if current_settings.is_production and current_settings.mock_api:
        raise RuntimeError("FATAL: MOCK_API cannot be enabled in production environment.")
    yield


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=API_CONTRACT_VERSION,
    description=(
        "AI farm credit scoring and early-warning decision-support tool for bank loan officers"
    ),
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan,
)

# Cross-Origin Resource Sharing (CORS) middleware with configurable origins (no wildcard *)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Exception handler ensuring all validation errors match blueprint error body
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    if exc.errors():
        first_error = exc.errors()[0]
    else:
        first_error = {"msg": "Validation failed", "loc": ["body"]}
    field_name = str(first_error["loc"][-1]) if first_error.get("loc") else None
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": first_error.get("msg", "Validation error"),
                "field": field_name,
            }
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.detail},
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail),
                "field": None,
            }
        },
    )


# System Health Route
@app.get("/health", tags=["System"])
def health_check() -> dict[str, Any]:
    """Health check endpoint to verify API operational readiness."""
    current_settings = get_settings()
    return {
        "status": "ok",
        "app": current_settings.app_name,
        "version": API_CONTRACT_VERSION,
        "environment": current_settings.app_env,
        "mock_api": current_settings.mock_api,
    }


# Include Versioned API Routes (/api/v1)
app.include_router(api_v1_router)
