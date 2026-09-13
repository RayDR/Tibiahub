from app.localization.service import (
    language_fallbacks,
    normalize_language_tag,
    protect_terms,
    restore_terms,
    source_text_hash,
)


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
