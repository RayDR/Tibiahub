# Models module
from app.models.media_asset import MediaAsset
from app.models.creature import Creature, creature_weaknesses, creature_resistances
from app.models.element import Element
from app.models.loot import Loot
from app.models.spawn_location import SpawnLocation
from app.models.hunt_zone import HuntZone
from app.models.user import User
from app.models.user_character import UserCharacter
from app.models.quest import Quest
from app.models.settings import SystemSettings
from app.models.user_activity import UserActivity
from app.models.catalog import Catalog
from app.models.hunt import HuntCatalog
from app.models.external_data import (
    APISync, CachedResource, HuntingPlace, Item, SyncJob, SyncJobError,
    TibiaWikiQuest,
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
from app.models.workspace_audit import WorkspaceAudit
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
)

__all__ = [
    "Creature",
    "Element",
    "Loot",
    "SpawnLocation",
    "HuntZone",
    "User",
    "UserCharacter",
    "Quest",
    "SystemSettings",
    "UserActivity",
    "Catalog",
    "HuntCatalog",
    "Item",
    "HuntingPlace",
    "TibiaWikiQuest",
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
    "MediaAsset",
    "WorkspaceAudit",
    "GuildLeadershipRole", "GuildLeadershipOpening", "GuildLeadershipApplication",
    "GuildLeadershipAssignment", "GuildLeadershipApplicationHistory",
    "GuildLeadershipApplicationMessage", "GuildLeadershipInterview", "GuildLeadershipVote",
    "creature_weaknesses",
    "creature_resistances",
    "KnowledgeProvider", "KnowledgeEntityType", "KnowledgeEntity",
    "KnowledgeEntityAlias", "KnowledgeDocument", "KnowledgeSearchMetadata",
    "KnowledgeDomainEvent",
]
