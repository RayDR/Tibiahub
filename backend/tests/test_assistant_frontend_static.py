from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_home_uses_functional_assistant_with_loading_and_failure_states():
    home = read("frontend/src/pages/HomePage.tsx")
    chat = read("frontend/src/components/assistant/AssistantChat.tsx")
    service = read("frontend/src/services/assistant.ts")
    assert "<AssistantChat />" in home
    assert "assistantApi.ask" in chat
    assert 'role="status"' in chat and 'role="alert"' in chat
    assert "disabled={loading" in chat
    assert "'/assistant/'" in service


def test_structured_response_renders_entity_links_routes_and_maps():
    message = read("frontend/src/components/assistant/AssistantMessage.tsx")
    entity = read("frontend/src/components/assistant/AssistantEntity.tsx")
    routes = read("frontend/src/components/assistant/AssistantRouteSteps.tsx")
    maps = read("frontend/src/components/assistant/AssistantMapReference.tsx")
    assert 'data-testid="assistant-structured-response"' in message
    assert "<AssistantEntity" in message
    assert "to={entity.detail_route}" in entity
    assert "route.steps.map" in routes
    assert "<AssistantMapReference" in routes
    assert "src={map.image_url}" in maps


def test_conversation_context_and_bilingual_strings_are_wired():
    chat = read("frontend/src/components/assistant/AssistantChat.tsx")
    translations = read("frontend/src/i18n.ts")
    assert "known_access_unlocks" in chat
    assert "sessionStorage.setItem" in chat
    assert "Where can I hunt Werewolves?" in translations
    assert "¿Dónde puedo cazar Werewolves?" in translations
