from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ComponentLayout:
    """Position and dimensions of a component on the canvas.

    This is a presentation concern, not part of the engineering model.
    """
    component_id: str
    x: float = 0.0
    y: float = 0.0
    width: float = 180.0
    height: float = 92.0

    def center(self) -> tuple[float, float]:
        return self.x + self.width / 2.0, self.y + self.height / 2.0

    def inlet_port(self) -> tuple[float, float]:
        return self.x, self.y + self.height / 2.0

    def outlet_port(self) -> tuple[float, float]:
        return self.x + self.width, self.y + self.height / 2.0


@dataclass(slots=True)
class ComponentUIState:
    """Transient UI state for a component.

    This is not persisted as part of the engineering model.
    """
    component_id: str
    is_dirty: bool = True
    report: str = ""
    solved_fields: set[str] = field(default_factory=set)
    conflicting_fields: set[str] = field(default_factory=set)
    unit_preferences: dict[str, str] = field(default_factory=dict)
    inlet_definition_mode: str = "Auto"
    outlet_definition_mode: str = "Auto"
    user_input_fields: set[str] = field(default_factory=set)