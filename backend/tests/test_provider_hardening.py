from app.knowledge.models import KnowledgeExternalMapping
from app.knowledge.providers import INITIAL_PROVIDERS
from app.knowledge.registry import EntityTypeRegistry, ProviderRegistry
from app.knowledge.schemas import KnowledgeDocumentCreate, KnowledgeEntityCreate
from app.knowledge.services import KnowledgeEntityService
from app.knowledge.storage import KnowledgeDocumentStore
from app.models import Creature, HuntZone, SpawnLocation
from app.services.bestiary_source import _build_creature_payload
from app.services.creature_storage_service import upsert_creature_payload
from app.services.recommendation_engine import RecommendationEngine


def _registry(db):
    EntityTypeRegistry.register_initial(db)
    for definition in INITIAL_PROVIDERS:
        ProviderRegistry.register(db, definition)
    db.flush()


def test_public_tibiadata_reads_are_local_and_include_completeness(client, db):
    _registry(db)
    entity = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="character", canonical_name="Local Knight",
        language_neutral_id="character:tibiadata:local knight",
    ))
    db.add(KnowledgeExternalMapping(
        provider_id="tibiadata", entity_type_id="character", external_id="local knight",
        entity_uuid=entity.uuid,
        provider_metadata={
            "fields": {"name": "Local Knight", "level": 250, "world": "Antica"},
            "supplied_fields": ["level", "name", "world"],
            "source_url": "https://api.tibiadata.com/v4/character/Local%20Knight",
            "data_version": 2,
        },
    ))
    KnowledgeDocumentStore.persist(db, KnowledgeDocumentCreate(
        provider_id="tibiadata", provider_document_id="character:local knight",
        entity_uuid=entity.uuid,
        raw_json={"character": {"character": {"name": "Local Knight", "level": 250, "world": "Antica"}}},
        version="v4",
    ))
    guild = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="guild", canonical_name="Local Guild",
        language_neutral_id="guild:tibiadata:local guild",
    ))
    db.add(KnowledgeExternalMapping(
        provider_id="tibiadata", entity_type_id="guild", external_id="local guild",
        entity_uuid=guild.uuid,
        provider_metadata={
            "fields": {"name": "Local Guild", "world": "Antica", "members": [{"name": "Local Knight"}]},
            "supplied_fields": ["members", "name", "world"], "data_version": 1,
        },
    ))
    KnowledgeDocumentStore.persist(db, KnowledgeDocumentCreate(
        provider_id="tibiadata", provider_document_id="guild:local guild",
        entity_uuid=guild.uuid, raw_json={"guild": {"name": "Local Guild", "world": "Antica", "members": [{"name": "Local Knight"}]}},
        version="v4",
    ))
    world = KnowledgeEntityService.create(db, KnowledgeEntityCreate(
        entity_type="world", canonical_name="Antica",
        language_neutral_id="world:tibiadata:antica",
    ))
    db.add(KnowledgeExternalMapping(
        provider_id="tibiadata", entity_type_id="world", external_id="antica",
        entity_uuid=world.uuid,
        provider_metadata={
            "fields": {"name": "Antica", "status": "online", "location": "Europe", "pvp_type": "Open PvP"},
            "supplied_fields": ["location", "name", "pvp_type", "status"], "data_version": 1,
        },
    ))
    KnowledgeDocumentStore.persist(db, KnowledgeDocumentCreate(
        provider_id="tibiadata", provider_document_id="world:antica",
        entity_uuid=world.uuid, raw_json={"name": "Antica", "status": "online", "location": "Europe", "pvp_type": "Open PvP"},
        version="v4",
    ))
    db.commit()

    response = client.get("/api/v1/tibia/character/Local%20Knight")
    assert response.status_code == 200
    payload = response.json()
    assert payload["canonical_id"] == str(entity.uuid)
    assert payload["source_provider"] == "tibiadata"
    assert payload["data_version"] == 2
    assert payload["supplied_fields"] == ["level", "name", "world"]
    assert "vocation" in payload["missing_fields"]
    assert response.json()["last_synced_at"] is not None
    guild_response = client.get("/api/v1/tibia/guild/Local%20Guild")
    assert guild_response.status_code == 200
    assert guild_response.json()["member_count"] == 1
    assert guild_response.json()["canonical_id"] == str(guild.uuid)
    worlds_response = client.get("/api/v1/tibia/worlds")
    assert worlds_response.status_code == 200 and worlds_response.json()["count"] == 1
    assert worlds_response.json()["worlds"][0]["canonical_id"] == str(world.uuid)
    assert client.get("/api/v1/tibia/character/Not%20Cached").status_code == 404


def test_missing_legacy_creature_stats_and_hunt_levels_remain_unknown(db):
    parsed = _build_creature_payload("Unknown Beast", "{{Infobox Creature|name=Unknown Beast}}")
    assert parsed["hitpoints"] is None
    assert parsed["experience"] is None
    assert parsed["armor"] is None
    assert parsed["speed"] is None

    creature = upsert_creature_payload(db, {
        "id": 991001, "name": "Unknown Beast", "locations": ["Unknown Cave"],
        "hitpoints": None, "experience": None,
    })
    assert creature.hitpoints is None and creature.experience is None
    assert creature.locations == ["Unknown Cave"]
    assert db.query(HuntZone).filter_by(name="Unknown Cave").count() == 0


def test_recommendation_profile_does_not_turn_unknown_creature_stats_into_zero():
    creature = Creature(id=991002, name="Mystery", hitpoints=None, experience=None, is_boss=False)
    zone = HuntZone(id=991003, name="Mystery Cave", min_level=None)
    zone.creature_spawns = [SpawnLocation(creature=creature, quantity="Unknown")]
    profile = RecommendationEngine._spawn_profile(zone)
    assert profile["raw_experience"] is None
    assert profile["suggested_level"] is None
    assert profile["danger"] == "unknown"


def test_legacy_tibiawiki_compatibility_reads_are_local_and_enriched(client, db, monkeypatch):
    creature = Creature(
        id=991004, name="Local Boss", normalized_name="local boss", slug="local-boss",
        external_id="4400", source_name="tibiawiki", source_url="https://example.invalid/local-boss",
        is_boss=True, is_hidden=False, hitpoints=None, experience=None, missing_fields=["hitpoints", "experience"],
    )
    db.add(creature)
    db.commit()
    monkeypatch.setattr(
        "requests.sessions.Session.request",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network forbidden")),
    )

    search = client.get("/api/v1/recommendations/tibiawiki/search", params={"query": "Local Boss"})
    assert search.status_code == 200
    assert search.json()["source"] == "local canonical Knowledge"
    assert search.json()["results"][0]["source_provider"] == "tibiawiki"
    detail = client.get("/api/v1/recommendations/tibiawiki/creature/Local%20Boss")
    assert detail.status_code == 200
    assert detail.json()["data"]["hitpoints"] is None
    assert detail.json()["data"]["missing_fields"] == ["hitpoints", "experience"]
    weekly = client.get("/api/v1/recommendations/weekly-bosses")
    assert weekly.status_code == 200
    assert weekly.json()["bosses"][0]["external_id"] == "4400"
