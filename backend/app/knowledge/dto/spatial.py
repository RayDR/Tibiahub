"""Provider-neutral spatial transfer objects with conservative validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MAX_TIBIA_COORDINATE = 65_535
MAX_TIBIA_FLOOR = 15
MAX_ROUTE_STEPS = 250
SPATIAL_LOCATION_ENTITY_TYPES = frozenset({"area", "town", "location", "hunt_zone", "access"})


def _coordinate(value: int | None, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_TIBIA_COORDINATE:
        raise ValueError(f"{name} must be an integer between 0 and {MAX_TIBIA_COORDINATE}")
    return value


def _floor(value: int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_TIBIA_FLOOR:
        raise ValueError(f"z must be an integer between 0 and {MAX_TIBIA_FLOOR}")
    return value


def _positions(value: Any):
    if isinstance(value, (list, tuple)) and value and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _positions(item)


@dataclass(frozen=True, slots=True)
class MapPointDTO:
    external_id: str
    name: str
    x: int | None = None
    y: int | None = None
    z: int | None = None
    location_name: str | None = None
    location_entity_type: str | None = None
    confidence: str = "unknown"
    source_reference: str | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _coordinate(self.x, "x"); _coordinate(self.y, "y"); _floor(self.z)
        if self.location_entity_type is not None and self.location_entity_type not in SPATIAL_LOCATION_ENTITY_TYPES:
            raise ValueError("Unsupported spatial location entity type")
        supplied = (self.x, self.y, self.z)
        if any(value is None for value in supplied) and any(value is not None for value in supplied):
            raise ValueError("Point coordinates must be complete or entirely unresolved")

    @property
    def resolved(self) -> bool:
        return self.x is not None


@dataclass(frozen=True, slots=True)
class MapRegionDTO:
    external_id: str
    name: str
    geometry: dict[str, Any] | None = None
    location_name: str | None = None
    location_entity_type: str | None = None
    minimum_z: int | None = None
    maximum_z: int | None = None
    confidence: str = "unknown"
    source_reference: str | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _floor(self.minimum_z); _floor(self.maximum_z)
        if self.location_entity_type is not None and self.location_entity_type not in SPATIAL_LOCATION_ENTITY_TYPES:
            raise ValueError("Unsupported spatial location entity type")
        if self.minimum_z is not None and self.maximum_z is not None and self.minimum_z > self.maximum_z:
            raise ValueError("minimum_z cannot exceed maximum_z")
        if self.geometry is not None and self.geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Regions accept only Polygon or MultiPolygon GeoJSON")
        if self.geometry is not None:
            positions = list(_positions(self.geometry.get("coordinates")))
            if not positions or any(len(position) != 3 for position in positions):
                raise ValueError("Region geometry must contain trusted three-dimensional positions")
            for x, y, z in positions:
                if int(x) != x or int(y) != y or int(z) != z:
                    raise ValueError("Tibia region coordinates must be integers")
                _coordinate(int(x), "x"); _coordinate(int(y), "y"); _floor(int(z))
            geometry_floors = [int(position[2]) for position in positions]
            if self.minimum_z is not None and self.minimum_z != min(geometry_floors):
                raise ValueError("minimum_z must match the trusted geometry")
            if self.maximum_z is not None and self.maximum_z != max(geometry_floors):
                raise ValueError("maximum_z must match the trusted geometry")

    @property
    def geometry_bounds(self) -> tuple[int, int, int, int, int, int] | None:
        """Return trusted XYZ bounds without requiring a PostGIS round trip."""
        if self.geometry is None:
            return None
        positions = [
            tuple(int(value) for value in position)
            for position in _positions(self.geometry.get("coordinates"))
        ]
        return (
            min(position[0] for position in positions),
            min(position[1] for position in positions),
            min(position[2] for position in positions),
            max(position[0] for position in positions),
            max(position[1] for position in positions),
            max(position[2] for position in positions),
        )


@dataclass(frozen=True, slots=True)
class RouteStepDTO:
    sequence: int
    instruction: str | None = None
    location_name: str | None = None
    x: int | None = None
    y: int | None = None
    z: int | None = None
    step_kind: str = "travel"
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.sequence, bool) or not 1 <= self.sequence <= MAX_ROUTE_STEPS:
            raise ValueError(f"Route step sequence must be between 1 and {MAX_ROUTE_STEPS}")
        _coordinate(self.x, "x"); _coordinate(self.y, "y"); _floor(self.z)
        supplied = (self.x, self.y, self.z)
        if any(value is None for value in supplied) and any(value is not None for value in supplied):
            raise ValueError("Route-step coordinates must be complete or entirely unresolved")
        if not (self.instruction or self.location_name or self.x is not None):
            raise ValueError("Route steps require an instruction, location, or trusted point")


@dataclass(frozen=True, slots=True)
class RouteDTO:
    external_id: str
    name: str
    steps: tuple[RouteStepDTO, ...]
    start_location_name: str | None = None
    end_location_name: str | None = None
    confidence: str = "unknown"
    source_reference: str | None = None
    provider_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.steps) > MAX_ROUTE_STEPS:
            raise ValueError(f"Routes cannot exceed {MAX_ROUTE_STEPS} steps")
        sequences = [step.sequence for step in self.steps]
        if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
            raise ValueError("Route steps must have unique ascending sequence numbers")
