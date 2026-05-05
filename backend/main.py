"""
Tibia Bestiary API - Main Application
"""
import logging
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.database import init_db
from app.api.v1.router import api_router


logger = logging.getLogger("app.slow_requests")
SLOW_REQUEST_MS = 1500


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the application"""
    # Startup: Initialize database
    init_db()
    yield
    # Shutdown: Clean up resources if needed


app = FastAPI(
    title="Tibia Bestiary API",
    description="API para consultar el bestiario de Tibia con recomendaciones de hunt",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def slow_request_logger(request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    route_name = request.url.path
    if request.scope.get("route") and isinstance(request.scope["route"], APIRoute):
        route_name = request.scope["route"].path

    if elapsed_ms >= SLOW_REQUEST_MS:
        logger.warning(
            "slow_request method=%s path=%s route=%s status=%s duration_ms=%s",
            request.method,
            request.url.path,
            route_name,
            response.status_code,
            elapsed_ms,
        )

    return response

# Include API routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Tibia Bestiary API",
        "version": "1.0.0",
        "status": "online"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
