"""
API v1 Router - Combines all API endpoints
"""
from fastapi import APIRouter, Depends

from app.api.v1 import assistant, creatures, hunt_zones, admin as admin_old, recommendations, items, quests, knowledge_graph, npcs_locations, seo, spatial, tibia_map, hunt_analyzer
from app.api.v1.endpoints import auth, guild, profile, admin, hunts, events, catalog, sync, password_reset, email_verification, character_ownership, tibia, sync_admin, raffles, raffle_participants, health, me_activity, notifications, workspaces, leadership, knowledge_admin, maintenance, maintenance_mode, admin_assistance, guild_permissions

api_router = APIRouter()

# Include all routers
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(guild.router, prefix="/guild", tags=["Guild"])
api_router.include_router(profile.router, prefix="/profile", tags=["Profile"])
api_router.include_router(me_activity.router)
api_router.include_router(password_reset.router, prefix="/password", tags=["Password Reset"])
api_router.include_router(email_verification.router, prefix="/email-verification", tags=["Email Verification"])
api_router.include_router(character_ownership.router, prefix="/character-ownership", tags=["Character Ownership"])
api_router.include_router(character_ownership.admin_router, prefix="/admin", tags=["Admin Character Ownership"])
api_router.include_router(admin.router, prefix="/guild-management", tags=["Guild Management"])
api_router.include_router(guild_permissions.router, prefix="/guild-management", tags=["Guild Permissions"])
api_router.include_router(hunts.router, prefix="/hunts", tags=["Hunt Catalog"])
api_router.include_router(catalog.router, prefix="/catalog", tags=["Catalog"])
api_router.include_router(events.router, prefix="/events", tags=["Events & Raffles"])
api_router.include_router(raffle_participants.router, prefix="/raffles", tags=["Raffle Participants"])
api_router.include_router(raffles.router, prefix="/raffles", tags=["Guild Raffles"])
api_router.include_router(notifications.router)
api_router.include_router(workspaces.router, prefix="/admin", tags=["Admin Workspaces"])
api_router.include_router(knowledge_admin.router, prefix="/admin/knowledge", tags=["Knowledge Operations"])
api_router.include_router(maintenance.router, prefix="/admin/maintenance", tags=["Admin Maintenance"])
api_router.include_router(maintenance_mode.router, prefix="/maintenance", tags=["Maintenance"])
api_router.include_router(admin_assistance.router, prefix="/admin/assistance", tags=["Admin Assistance"])
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
api_router.include_router(knowledge_graph.router)
api_router.include_router(npcs_locations.router)
api_router.include_router(spatial.router)
api_router.include_router(tibia_map.router)
api_router.include_router(hunt_analyzer.router)
api_router.include_router(assistant.router)
api_router.include_router(seo.router)
api_router.include_router(
    admin_old.router,
    prefix="/admin",
    tags=["Admin"],
    dependencies=[Depends(auth.get_current_admin_user)],
)
api_router.include_router(recommendations.router, prefix="/recommendations", tags=["Recommendations"])
