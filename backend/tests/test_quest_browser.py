from app.knowledge.models import KnowledgeEntity, KnowledgeEntityType
from app.models.external_data import TibiaWikiQuest


def _seed_quest(db, *, name: str, external_id: str, min_level: int | None = None, category: str | None = None, access_unlocks: list | None = None, canonical: bool = True, is_group: bool = False, source_url: str | None = None):
    slug = name.lower().replace("'", "").replace(" ", "-")
    entity_id = None
    if canonical:
        entity = KnowledgeEntity(entity_type="quest", canonical_name=name, slug=slug, language_neutral_id=f"quest:{external_id}")
        db.add(entity)
        db.flush()
        entity_id = entity.uuid
    row = TibiaWikiQuest(
        name=name,
        normalized_name=name.lower(),
        slug=slug,
        external_id=external_id,
        source_name="tibiawiki",
        source_url=source_url,
        knowledge_entity_id=entity_id,
        min_level=min_level,
        category=category,
        access_unlocks=access_unlocks or [],
        is_group=is_group,
        parser_metadata={"supplied_fields": ["minimum_level"] if min_level is not None else []},
    )
    db.add(row)
    db.flush()
    return row


def _seed_catalog(db):
    db.add(KnowledgeEntityType(entity_type="quest", display_name="Quest"))
    db.flush()
    _seed_quest(db, name="A First Quest", external_id="1", min_level=20)
    _seed_quest(db, name="Access to Somewhere", external_id="2", min_level=50, category="Access Quests")
    _seed_quest(db, name="Door Opener", external_id="3", min_level=80, access_unlocks=[{"name": "Secret Area"}])
    _seed_quest(db, name="Unknown Level Quest", external_id="4")
    _seed_quest(db, name="Quest Group", external_id="5", is_group=True)
    _seed_quest(db, name="Legacy Only Quest", external_id="6", canonical=False)
    _seed_quest(
        db,
        name="Lion's Rock Quest/Spoiler",
        external_id="7",
        source_url="https://tibia.fandom.com/wiki/Lion%27s_Rock_Quest/Spoiler",
    )
    _seed_quest(
        db,
        name="Aliased Quest",
        external_id="8",
        source_url="https://tibia.fandom.com/wiki/Aliased_Quest/Spoiler",
    )


def test_quest_facets_count_only_canonical_non_group_overview_rows(client, db):
    _seed_catalog(db)
    response = client.get("/api/v1/quests/facets")
    assert response.status_code == 200
    assert response.json() == {
        "total": 4,
        "access_quests": 2,
        "minimum_level_known": 3,
        "minimum_level_min": 20,
        "minimum_level_max": 80,
    }


def test_quest_browser_filters_access_sorts_levels_paginates_and_hides_spoilers(client, db):
    _seed_catalog(db)

    access = client.get("/api/v1/quests/browse", params={"access_only": True, "limit": 20})
    assert access.status_code == 200
    assert [row["name"] for row in access.json()] == ["Access to Somewhere", "Door Opener"]
    assert all(row["is_access_quest"] for row in access.json())

    levels = client.get("/api/v1/quests/browse", params={"sort_by": "min_level", "sort_order": "desc", "limit": 20})
    assert levels.status_code == 200
    assert [(row["name"], row["min_level"]) for row in levels.json()] == [
        ("Door Opener", 80),
        ("Access to Somewhere", 50),
        ("A First Quest", 20),
        ("Unknown Level Quest", None),
    ]

    paged = client.get("/api/v1/quests/browse", params={"sort_by": "name", "sort_order": "asc", "skip": 1, "limit": 2})
    assert paged.status_code == 200
    assert [row["name"] for row in paged.json()] == ["Access to Somewhere", "Door Opener"]

    searched = client.get("/api/v1/quests/browse", params={"search": "door", "limit": 20})
    assert searched.status_code == 200
    assert [row["name"] for row in searched.json()] == ["Door Opener"]

    spoilers = client.get("/api/v1/quests/browse", params={"search": "spoiler", "limit": 20})
    assert spoilers.status_code == 200
    assert spoilers.json() == []
