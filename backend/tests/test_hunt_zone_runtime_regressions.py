from __future__ import annotations

from app.knowledge.adapters.tibiawiki_hunt_zones import _hunt_zone_parts
from app.knowledge.registry.relationship_types import INITIAL_RELATIONSHIP_TYPES


def test_hunt_zone_location_removes_mapper_coords_without_promoting_spatial_data():
    raw = {
        "parse": {
            "pageid": 101544,
            "title": "Iksupan",
            "wikitext": {
                "*": """
{{Infobox Hunt
| name = Iksupan
| city = Port Hope
| location = Entered through a secret passage in [[Tiquanda]], {{Mapper Coords|127.215|128.108|7|1|text=here}}.
| vocation = All vocations
| lvlknights = 150
}}
Access to Iksupan is obtained through the [[Adventures of Galthen Quest]].
""",
            },
        },
    }

    _external_id, _page_title, _wikitext, dto = _hunt_zone_parts(raw)

    assert dto.location == "Entered through a secret passage in Tiquanda."
    assert "127.215" not in dto.location
    assert "128.108" not in dto.location
    assert "location" in dto.supplied_fields


def test_runtime_relationship_registry_allows_hunt_zone_normalization_edges():
    definitions = {definition.code: definition for definition in INITIAL_RELATIONSHIP_TYPES}

    assert "hunt_zone" in definitions["has_creature"].sources
    assert set(definitions["has_creature"].targets) == {"creature", "boss"}
    assert definitions["requires_hunt_quest"].sources == ("hunt_zone",)
    assert definitions["requires_hunt_quest"].targets == ("quest",)
    assert "hunt_zone" in definitions["located_at"].sources
    assert set(definitions["located_at"].targets) == {"area", "town", "location"}
