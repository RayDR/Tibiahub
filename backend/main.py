"""
Tibia Bestiary API - Main Application
"""
import logging
import time
import uuid

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute
from contextlib import asynccontextmanager

from app.core.config import settings
from app.db.database import DatabaseNotReadyError, SessionLocal, verify_connection_and_schema
from app.api.v1.router import api_router
from app.services.sync_service import SyncService
from app.services.maintenance_mode_service import MaintenanceModeService
from app.models.maintenance_sync import MaintenanceHold
from app.models.user import User
from app.core import security
from jose import JWTError, jwt
from sqlalchemy.exc import SQLAlchemyError


logger = logging.getLogger("app.slow_requests")
SLOW_REQUEST_MS = 1000


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the application"""
    # Migrations are an explicit deployment step. Startup only verifies them.
    try:
        verify_connection_and_schema()
    except DatabaseNotReadyError as exc:
        logger.error("application_startup_failed reason=%s", exc)
        raise RuntimeError(str(exc)) from None

    db = SessionLocal()
    try:
        stale_ids = SyncService.recover_stale_running_jobs(db, reason="stale after backend recovery")
        if stale_ids:
            logger.warning("sync_stale_jobs_recovered count=%s jobs=%s", len(stale_ids), ",".join(stale_ids))
        try:
            released = MaintenanceModeService.reconcile(db)
            if released:
                db.commit()
                logger.warning("maintenance_orphan_holds_released count=%s", len(released))
        except SQLAlchemyError:
            db.rollback()
            if settings.APP_ENV != "test":
                raise
    finally:
        db.close()

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


_MAINTENANCE_PUBLIC_PATHS = {
    "/api/v1/maintenance/status",
    "/api/v1/health", "/api/v1/healthz", "/api/v1/ready",
    "/api/v1/auth/login", "/api/v1/auth/me",
}


def _maintenance_admin(request, db) -> bool:
    authorization = request.headers.get("authorization") or ""
    if not authorization.lower().startswith("bearer "):
        return False
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[security.ALGORITHM])
        username = payload.get("sub")
    except JWTError:
        return False
    if not username:
        return False
    user = db.query(User).filter(User.username == username).first()
    return bool(user and user.is_active and user.is_superuser)


@app.middleware("http")
async def maintenance_enforcement(request, call_next):
    path = request.url.path.rstrip("/") or "/"
    if (
        path in _MAINTENANCE_PUBLIC_PATHS
        or path.startswith("/api/v1/password")
        or not path.startswith("/api/")
    ):
        return await call_next(request)
    db = SessionLocal()
    try:
        try:
            hold = db.query(MaintenanceHold).filter(MaintenanceHold.released_at.is_(None)).order_by(MaintenanceHold.enabled_at).first()
        except SQLAlchemyError:
            db.rollback()
            if settings.APP_ENV == "test":
                return await call_next(request)
            raise
        if hold is None or _maintenance_admin(request, db):
            return await call_next(request)
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": "60"},
            content={
                "detail": {
                    "code": "maintenance_mode",
                    "message": hold.public_message,
                    "planned_end_at": hold.planned_end_at.isoformat() if hold.planned_end_at else None,
                }
            },
        )
    finally:
        db.close()


@app.middleware("http")
async def slow_request_logger(request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    response.headers["X-Request-Id"] = request_id

    route_name = request.url.path
    if request.scope.get("route") and isinstance(request.scope["route"], APIRoute):
        route_name = request.scope["route"].path

    if elapsed_ms >= SLOW_REQUEST_MS:
        logger.warning(
            "slow_request warning=slow_request method=%s path=%s route=%s status_code=%s duration_ms=%s request_id=%s",
            request.method,
            request.url.path,
            route_name,
            response.status_code,
            elapsed_ms,
            request_id,
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
        app,
        host=settings.API_HOST,
        port=settings.API_PORT,
    )
