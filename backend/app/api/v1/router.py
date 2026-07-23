"""
API v1 Router - Combines all API endpoints
"""
from fastapi import APIRouter, Depends

from app.api.v1 import creatures, hunt_zones, admin as admin_old, recommendations, items, quests
from app.api.v1.endpoints import auth, guild, profile, admin, hunts, events, catalog, sync, password_reset, tibia, sync_admin, raffles, health, me_activity, notifications, workspaces, leadership

api_router = APIRouter()

# Include all routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(guild.router, prefix="/guild", tags=["Guild"])
api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])
api_router.include_router(me_activity.router)
api_router.include_router(password_reset.router, prefix="/password", tags=["Password Reset"])
api_router.include_router(admin.router, prefix="/guild-management", tags=["Guild Management"])
api_router.include_router(hunts.router, prefix="/hunts", tags=["Hunt Catalog"])
api_router.include_router(catalog.router, prefix="/catalog", tags=["Catalog"])
api_router.include_router(events.router, prefix="/events", tags=["Events & Raffles"])
api_router.include_router(raffles.router, prefix="/raffles", tags=["Guild Raffles"])
api_router.include_router(notifications.router)
api_router.include_router(workspaces.router, prefix="/admin", tags=["Admin Workspaces"])
api_router.include_router(leadership.router, prefix="/guild", tags=["Guild Leadership"])
api_router.include_router(leadership.admin_router, prefix="/admin", tags=["Admin Leadership Assistance"])
api_router.include_router(sync.router, prefix="/sync", tags=["Database Sync"])
api_router.include_router(sync_admin.router, prefix="/admin/sync", tags=["Sync Admin"])
api_router.include_router(tibia.router, tags=["TibiaData API"])
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(creatures.router)
api_router.include_router(hunt_zones.router)
api_router.include_router(items.router)
api_router.include_router(quests.router)
api_router.include_router(
    admin_old.router,
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(auth.get_current_admin_user)],
)
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
