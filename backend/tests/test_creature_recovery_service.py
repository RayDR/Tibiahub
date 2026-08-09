from app.core.config import settings
from app.models import Creature, Loot
from app.services.creature_recovery_service import (
    build_category_recovery_plan,
    category_coverage,
    clear_legacy_beast_classifications,
    remove_malformed_loot,
)
from app.services.creature_storage_service import (
    upsert_creature_payload,
)
from app.services.text_utils import normalize_search_text


def make_creature(
    name: str,
    *,
    bestiary_class=None,
    creature_class=None,
    classification=None,
    protected_fields=None,
):
    return Creature(
        name=name,
        normalized_name=normalize_search_text(name),
        slug=name.lower().replace(" ", "-"),
        hitpoints=100,
        experience=100,
        source_name="tibiawiki",
        bestiary_class=bestiary_class,
        creature_class=creature_class,
        classification=classification,
        protected_fields=protected_fields or [],
        is_boss=False,
        is_hidden=False,
    )


def test_recovery_plan_fetches_missing_documents_only_for_unresolved(
    db,
):
    unresolved = make_creature(
        "Unknown Special Creature",
        creature_class="Special",
    )
    categorized = make_creature(
        "Known Mammal",
        bestiary_class="Mammal",
    )

    db.add_all(
        [unresolved, categorized]
    )
    db.flush()

    coverage = category_coverage(db)
    plan = build_category_recovery_plan(db)

    assert coverage["total"] == 2
    assert coverage["categorized"] == 1
    assert coverage["unresolved"] == 1

    assert len(plan) == 1
    assert plan[0].creature_name == (
        "Unknown Special Creature"
    )
    assert plan[0].mode == "detail"
    assert plan[0].external_id is None


def test_legacy_beast_cleanup_respects_protected_fields(
    db,
):
    mutable = make_creature(
        "Old Beast",
        classification="Beast",
    )
    mutable.raw_data = {
        "classification": "Beast",
    }

    protected = make_creature(
        "Protected Beast",
        classification="Beast",
        protected_fields=["classification"],
    )

    db.add_all([mutable, protected])
    db.flush()

    changed = (
        clear_legacy_beast_classifications(db)
    )

    assert changed == 1
    assert mutable.classification is None
    assert mutable.raw_data["classification"] is None
    assert protected.classification == "Beast"


def test_malformed_loot_cleanup_is_narrow(
    db,
):
    creature = make_creature(
        "Loot Test Creature"
    )
    db.add(creature)
    db.flush()

    base = (
        settings.TIBIAWIKI_BASE_PAGE_URL
        .rstrip("/")
    )

    bad = Loot(
        creature_id=creature.id,
        item_name="0-98?",
        normalized_name="0 98",
        source_url=f"{base}/0-98%3F",
        item_image_url=(
            f"{base}/Special:FilePath/"
            "0-98%3F.gif"
        ),
        raw_data={
            "item_name": "0-98?",
        },
    )

    good = Loot(
        creature_id=creature.id,
        item_name="Gold Coin",
        normalized_name="gold coin",
        source_url=f"{base}/Gold_Coin",
        item_image_url=(
            f"{base}/Special:FilePath/"
            "Gold_Coin.gif"
        ),
        raw_data={
            "item_name": "Gold Coin",
        },
    )

    db.add_all([bad, good])
    db.flush()

    removed, affected = (
        remove_malformed_loot(db)
    )
    db.flush()

    assert removed == 1
    assert affected == 1
    assert (
        db.query(Loot)
        .filter_by(
            item_name="0-98?"
        )
        .count()
        == 0
    )
    assert (
        db.query(Loot)
        .filter_by(
            item_name="Gold Coin"
        )
        .count()
        == 1
    )


def test_direct_sync_preserves_existing_stable_external_id(
    db,
):
    creature = make_creature(
        "Identity Test"
    )
    creature.external_id = "321"

    db.add(creature)
    db.flush()

    upsert_creature_payload(
        db,
        {
            "id": 987654321,
            "name": "Identity Test",
            "slug": "identity-test",
            "hitpoints": 100,
            "experience": 100,
            "loot_items": [],
            "locations": [],
        },
    )

    assert creature.external_id == "321"

    upsert_creature_payload(
        db,
        {
            "id": 987654321,
            "external_id": "654",
            "name": "Identity Test",
            "slug": "identity-test",
            "hitpoints": 100,
            "experience": 100,
            "loot_items": [],
            "locations": [],
        },
    )

    assert creature.external_id == "654"
