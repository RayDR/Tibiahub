import asyncio

from app.core.config import settings
from app.knowledge.adapters.protocol import CanonicalEntityCandidate, KnowledgeNormalizationResult
from app.knowledge.models import KnowledgeLocalization, LocalizationJob
from app.localization.backfill import LocalizationBackfillService
from app.localization.planner import LocalizationPlanningService
from app.localization.provider import TranslationResult
from app.localization.queue import LocalizationQueueService
from app.localization.service import (
    ContentLocalizationService,
    ContentTranslationService,
    language_fallbacks,
    normalize_language_tag,
    protect_terms,
    restore_terms,
    source_text_hash,
)
from app.models.creature import Creature


def test_normalize_language_tag_preserves_region_semantics():
    assert normalize_language_tag("es_mx") == "es-MX"
    assert normalize_language_tag("PT-br") == "pt-BR"
    assert normalize_language_tag("en") == "en"


def test_language_fallbacks_use_base_language_then_english():
    assert language_fallbacks("es-MX") == ["es-MX", "es", "en"]
    assert language_fallbacks("pt-BR") == ["pt-BR", "pt", "en"]
    assert language_fallbacks(None) == ["en"]


def test_protect_and_restore_terms_keeps_tibia_names_stable():
    source = "Use Sudden Death Runes against Demon near Edron."
    masked, replacements = protect_terms(source, ("Sudden Death Rune", "Demon", "Edron"))

    assert "Sudden Death Rune" not in masked
    assert "Demon" not in masked
    assert "Edron" not in masked
    assert "[[TH_TERM_" in masked
    assert restore_terms(masked, replacements) == source


def test_source_text_hash_is_stable_and_sensitive_to_changes():
    first = source_text_hash("same text")
    assert first == source_text_hash("same text")
    assert first != source_text_hash("changed text")


class FakeTranslationProvider:
    def __init__(self, *, detected_language: str = "en", translated_text: str = "Traducido"):
        self.detected_language = detected_language
        self.translated_text = translated_text
        self.calls = 0

    async def translate(self, request):
        self.calls += 1
        return TranslationResult(
            text=self.translated_text,
            source_language=self.detected_language,
            target_language=request.target_language,
            provider="fake",
            model="fake-v1",
            metadata={"test": True},
        )


def test_translation_persists_provider_detected_source_language(db):
    source = "Um Demon perigoso."
    provider = FakeTranslationProvider(detected_language="pt-BR", translated_text="Un Demon peligroso.")
    service = ContentTranslationService(provider)

    row = asyncio.run(
        service.translate_and_store(
            db,
            resource_type="creature",
            resource_key="demon-pt-source",
            field_path="description",
            source_text=source,
            source_language="auto",
            target_language="es",
            protected_terms=("Demon",),
        )
    )

    assert row.source_language == "pt-BR"
    assert row.source_text == source
    assert row.language == "es"
    assert row.status == "generated"
    assert row.provider == "fake"
    assert provider.calls == 1


def test_approved_translation_becomes_stale_without_provider_call(db):
    old_source = "Old English source"
    row = KnowledgeLocalization(
        resource_type="creature",
        resource_key="demon-approved-stale",
        field_path="description",
        language="es",
        text="Traducción humana aprobada",
        source_language="en",
        source_text=old_source,
        source_text_hash=source_text_hash(old_source),
        origin="human",
        status="approved",
        locked=True,
    )
    from datetime import UTC, datetime

    row.approved_at = datetime.now(UTC)
    db.add(row)
    db.flush()
    provider = FakeTranslationProvider()
    changed_source = "Changed English source"

    result = asyncio.run(
        ContentTranslationService(provider).translate_and_store(
            db,
            resource_type="creature",
            resource_key="demon-approved-stale",
            field_path="description",
            source_text=changed_source,
            source_language="en",
            target_language="es",
        )
    )

    assert result.id == row.id
    assert result.status == "stale"
    assert result.text == "Traducción humana aprobada"
    assert result.source_text == changed_source
    assert provider.calls == 0


def test_locale_resolution_ignores_stale_translation_and_falls_back_to_source(db):
    db.add(
        KnowledgeLocalization(
            resource_type="creature",
            resource_key="demon-stale-fallback",
            field_path="description",
            language="es",
            text="Viejo",
            source_language="en",
            source_text="Old source",
            source_text_hash=source_text_hash("Old source"),
            origin="human",
            status="stale",
            locked=True,
        )
    )
    db.flush()

    result = ContentLocalizationService.resolve_text(
        db,
        resource_type="creature",
        resource_key="demon-stale-fallback",
        field_path="description",
        source_text="Current source",
        source_language="en",
        requested_language="es-MX",
    )

    assert result is not None
    assert result.text == "Current source"
    assert result.language == "en"
    assert result.used_fallback is True


def test_review_and_approval_lock_human_text(db):
    row = KnowledgeLocalization(
        resource_type="item",
        resource_key="sudden-death-rune-review",
        field_path="description",
        language="es",
        text="Borrador",
        source_language="en",
        source_text="Source",
        source_text_hash=source_text_hash("Source"),
        origin="machine",
        status="generated",
    )
    db.add(row)
    db.flush()

    ContentLocalizationService.review(db, row, reviewer_id=42, text="Texto revisado")
    assert row.status == "reviewed"
    assert row.origin == "human"
    assert row.text == "Texto revisado"
    assert row.locked is False

    ContentLocalizationService.approve(db, row, reviewer_id=42)
    assert row.status == "approved"
    assert row.locked is True
    assert row.approved_by_id == 42
    assert row.approved_at is not None


def test_queue_is_opt_in_and_idempotent(db, monkeypatch):
    monkeypatch.setattr(settings, "LOCALIZATION_ENABLED", True)
    monkeypatch.setattr(settings, "LOCALIZATION_AUTO_ENQUEUE", False)
    resource_key = "queue-idempotency-demon"

    assert LocalizationQueueService.enqueue_field(
        db,
        resource_type="creature",
        resource_key=resource_key,
        field_path="description",
        source_text="Demons are dangerous.",
        source_language="en",
        target_language="es",
    ) is None

    first = LocalizationQueueService.enqueue_field(
        db,
        resource_type="creature",
        resource_key=resource_key,
        field_path="description",
        source_text="Demons are dangerous.",
        source_language="en",
        target_language="es",
        force=True,
    )
    second = LocalizationQueueService.enqueue_field(
        db,
        resource_type="creature",
        resource_key=resource_key,
        field_path="description",
        source_text="Demons are dangerous.",
        source_language="en",
        target_language="es",
        force=True,
    )

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert (
        db.query(LocalizationJob)
        .filter_by(resource_type="creature", resource_key=resource_key, field_path="description", target_language="es")
        .count()
        == 1
    )


def test_planner_enqueues_only_translatable_fields_and_protects_tibia_terms(db, monkeypatch):
    monkeypatch.setattr(settings, "LOCALIZATION_ENABLED", True)
    monkeypatch.setattr(settings, "LOCALIZATION_AUTO_ENQUEUE", True)
    monkeypatch.setattr(settings, "LOCALIZATION_TARGET_LANGUAGES", "es")

    result = KnowledgeNormalizationResult(
        action="upsert",
        provider_code="tibiawiki",
        external_id="planner-creature-123",
        candidate=CanonicalEntityCandidate(
            entity_type="creature",
            canonical_name="Demon",
            language_neutral_id="creature:tibiawiki:planner-creature-123",
            aliases=("The Demon",),
        ),
        canonical_data={
            "canonical_name": "Demon",
            "description": "Demon lives near Edron.",
            "hitpoints": 8200,
            "locations": [{"name": "Edron"}],
            "provider_metadata": {"language": "en"},
        },
    )

    queued = LocalizationPlanningService.plan_normalization(
        db,
        result=result,
        entity_uuid=None,
        applied_status="updated",
    )

    assert queued == 1
    job = (
        db.query(LocalizationJob)
        .filter_by(
            resource_type="creature",
            resource_key="planner-creature-123",
            field_path="description",
            target_language="es",
        )
        .one()
    )
    assert set(job.protected_terms) >= {"Demon", "The Demon", "Edron"}


def test_existing_content_backfill_is_paginated_and_idempotent(db, monkeypatch):
    monkeypatch.setattr(settings, "LOCALIZATION_ENABLED", True)
    monkeypatch.setattr(settings, "LOCALIZATION_AUTO_ENQUEUE", False)

    first_creature = Creature(name="Backfill Demon", description="A dangerous creature.")
    second_creature = Creature(name="Backfill Dragon", description="A fire-breathing creature.")
    db.add_all([first_creature, second_creature])
    db.flush()

    first_page = LocalizationBackfillService.backfill(
        db,
        resource_type="creature",
        after_id=first_creature.id - 1,
        limit=1,
        target_languages=("es",),
    )
    assert first_page.scanned == 1
    assert first_page.queued == 1
    assert first_page.next_cursor == first_creature.id
    assert first_page.exhausted is False

    repeated = LocalizationBackfillService.backfill(
        db,
        resource_type="creature",
        after_id=first_creature.id - 1,
        limit=1,
        target_languages=("es",),
    )
    assert repeated.queued == 0
    resource_keys = (str(first_creature.id), str(second_creature.id))
    scoped_jobs = db.query(LocalizationJob).filter(
        LocalizationJob.resource_type == "creature",
        LocalizationJob.resource_key.in_(resource_keys),
        LocalizationJob.target_language == "es",
    )
    assert scoped_jobs.count() == 1

    second_page = LocalizationBackfillService.backfill(
        db,
        resource_type="creature",
        after_id=first_page.next_cursor or 0,
        limit=1,
        target_languages=("es",),
    )
    assert second_page.scanned == 1
    assert second_page.queued == 1
    assert second_page.next_cursor is None
    assert second_page.exhausted is True
    assert scoped_jobs.count() == 2
