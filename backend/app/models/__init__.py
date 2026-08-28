# Models module
from app.models.media_asset import MediaAsset
from app.models.creature import Creature, creature_weaknesses, creature_resistances
from app.models.element import Element
from app.models.loot import Loot
from app.models.spawn_location import SpawnLocation
from app.models.hunt_zone import HuntZone
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.auth_security import AuthOneTimeToken, AuthRequestEvent
from app.models.character_ownership import CharacterOwnershipClaim, CharacterOwnershipHistory
from app.models.quest import Quest
from app.models.quest_progress import QuestCompletion
from app.models.settings import SystemSettings
from app.models.user_activity import UserActivity
from app.models.catalog import Catalog
from app.models.hunt import GuildHunt, GuildHuntParticipant, HuntCatalog
from app.models.external_data import (
    APISync, CachedResource, HuntingPlace, Item, SyncJob, SyncJobError,
    QuestMission, TibiaWikiLocation, TibiaWikiNpc, TibiaWikiQuest,
)
from app.models.guild import GuildEvent, EventAttendance, Announcement, Recruitment
from app.models.events import Event, EventParticipant, PublicEventParticipant
from app.models.entity_metadata import EntityMetadata
from app.models.raffle import (
    Raffle, RaffleEligibilityEntry, RaffleEligibilitySnapshot, RaffleManagerGrant,
    RaffleParticipant, RafflePrize, RafflePrizeDelivery, RaffleDeliveryAudit, RaffleRerunAudit,
    RaffleRun, RaffleRunResult, RaffleWinner,
    RaffleSchedulerAttempt, RaffleSchedulerState, RaffleTestAudit, InternalNotification,
)
from app.models.guild_member_snapshot import GuildMemberSnapshot
from app.models.guild_management import GuildDirectory, GuildManagementGrant, GuildRosterCharacter
from app.models.email_delivery import EmailOutbox, EmailWorkerHeartbeat
from app.models.workspace_audit import WorkspaceAudit
from app.models.world_map import WorldMapDataset, WorldMapFloor, WorldMapMarker
from app.models.hunt_analyzer import HuntAnalyzerSubmission
from app.models.maintenance_sync import MaintenanceHold, SyncJobPhase, SyncWorkerHeartbeat
from app.models.leadership import (
    GuildLeadershipRole, GuildLeadershipOpening, GuildLeadershipApplication,
    GuildLeadershipAssignment, GuildLeadershipApplicationHistory,
    GuildLeadershipApplicationMessage, GuildLeadershipInterview, GuildLeadershipVote,
)
# Alembic and test metadata registration only; Knowledge Platform behavior stays
# inside app.knowledge.
from app.knowledge.models import (
    KnowledgeDocument, KnowledgeDomainEvent, KnowledgeEntity, KnowledgeEntityAlias,
    KnowledgeEntityType, KnowledgeProvider, KnowledgeSearchMetadata,
    KnowledgeJob, KnowledgeJobAttempt, KnowledgeProviderCursor, KnowledgeWorkerHeartbeat,
    KnowledgeExternalMapping,
    KnowledgeProviderObservation,
    KnowledgeCreatureItemDrop,
    KnowledgeAccess, KnowledgeQuestRelation,
    KnowledgeRelationship, KnowledgeRelationshipType,
    SpatialEntityLocationLink, SpatialMapPoint, SpatialMapRegion, SpatialRoute, SpatialRouteStep,
)

__all__ = [
    "Creature",
    "Element",
    "Loot",
    "SpawnLocation",
    "HuntZone",
    "User",
    "UserCharacter",
    "AuthOneTimeToken",
    "AuthRequestEvent",
    "CharacterOwnershipClaim",
    "CharacterOwnershipHistory",
    "Quest",
    "QuestCompletion",
    "SystemSettings",
    "UserActivity",
    "Catalog",
    "HuntCatalog",
    "GuildHunt",
    "GuildHuntParticipant",
    "Item",
    "HuntingPlace",
    "TibiaWikiQuest",
    "TibiaWikiNpc",
    "TibiaWikiLocation",
    "QuestMission",
    "APISync",
    "SyncJob",
    "SyncJobError",
    "CachedResource",
    "EntityMetadata",
    "GuildEvent",
    "EventAttendance",
    "Announcement",
    "Recruitment",
    "Event",
    "EventParticipant",
    "PublicEventParticipant",
    "Raffle",
    "RaffleParticipant",
    "RafflePrize",
    "RaffleWinner",
    "RaffleManagerGrant",
    "RaffleEligibilitySnapshot",
    "RaffleEligibilityEntry",
    "RaffleRun",
    "RaffleRunResult",
    "RafflePrizeDelivery",
    "RaffleDeliveryAudit",
    "RaffleRerunAudit",
    "RaffleSchedulerAttempt",
    "RaffleSchedulerState",
    "RaffleTestAudit",
    "InternalNotification",
    "GuildMemberSnapshot",
    "GuildManagementGrant",
    "GuildRosterCharacter",
    "MediaAsset",
    "WorkspaceAudit",
    "WorldMapDataset", "WorldMapFloor", "WorldMapMarker", "HuntAnalyzerSubmission",
    "MaintenanceHold", "SyncJobPhase", "SyncWorkerHeartbeat",
    "GuildLeadershipRole", "GuildLeadershipOpening", "GuildLeadershipApplication",
    "GuildLeadershipAssignment", "GuildLeadershipApplicationHistory",
    "GuildLeadershipApplicationMessage", "GuildLeadershipInterview", "GuildLeadershipVote",
    "creature_weaknesses",
    "creature_resistances",
    "KnowledgeProvider", "KnowledgeEntityType", "KnowledgeEntity",
    "KnowledgeEntityAlias", "KnowledgeDocument", "KnowledgeSearchMetadata",
    "KnowledgeDomainEvent",
    "KnowledgeJob", "KnowledgeJobAttempt", "KnowledgeProviderCursor", "KnowledgeWorkerHeartbeat",
    "KnowledgeExternalMapping",
    "KnowledgeProviderObservation",
    "KnowledgeCreatureItemDrop",
    "KnowledgeAccess", "KnowledgeQuestRelation",
    "KnowledgeRelationship", "KnowledgeRelationshipType",
    "SpatialMapPoint", "SpatialMapRegion", "SpatialRoute", "SpatialRouteStep", "SpatialEntityLocationLink",
]
