from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .model_layout import ComponentLayout, ComponentUIState
from .thermo import StateSpec, ThermoState


class ComponentKind(str, Enum):
    PUMP = "Pump"
    BOILER = "Boiler"
    TURBINE = "Turbine"
    REHEATER = "Reheater"
    CONDENSER = "Condenser"
    VALVE = "Valve"
    HEAT_EXCHANGER = "Heat Exchanger"
    PIPE = "Pipe"
    MIXER = "Mixer"
    SPLITTER = "Splitter"
    CUSTOM = "Custom"


class ProcessKind(str, Enum):
    GENERAL = "General"
    ISOBARIC = "Isobaric"
    ISOCHORIC = "Isochoric"
    ISENTROPIC = "Isentropic"
    ISENTHALPIC = "Isenthalpic"
    ADIABATIC = "Adiabatic"


class PortRole(str, Enum):
    INLET = "Inlet"
    OUTLET = "Outlet"


@dataclass(slots=True)
class ThermoSpec:
    pressure_mpa: float | None = None
    temperature_c: float | None = None
    enthalpy_kj_kg: float | None = None
    entropy_kj_kgk: float | None = None
    quality: float | None = None
    specific_volume_m3_kg: float | None = None
    efficiency: float | None = None
    heat_duty_kw: float | None = None
    pressure_drop_mpa: float | None = None
    mass_flow_kg_s: float | None = None
    pipe_length_m: float | None = None
    pipe_outer_diameter_m: float | None = None
    pipe_wall_thickness_m: float | None = None
    pipe_roughness_m: float | None = None
    elevation_change_m: float | None = None
    local_loss_coefficient: float | None = None

    def to_state_spec(self) -> StateSpec:
        return StateSpec(
            pressure_mpa=self.pressure_mpa,
            temperature_c=self.temperature_c,
            enthalpy_kj_kg=self.enthalpy_kj_kg,
            entropy_kj_kgk=self.entropy_kj_kgk,
            quality=self.quality,
            specific_volume_m3_kg=self.specific_volume_m3_kg,
        )

    def defined_count(self) -> int:
        return sum(
            value is not None
            for value in (
                self.pressure_mpa,
                self.temperature_c,
                self.enthalpy_kj_kg,
                self.entropy_kj_kgk,
                self.quality,
                self.specific_volume_m3_kg,
                self.efficiency,
                self.heat_duty_kw,
                self.pressure_drop_mpa,
                self.mass_flow_kg_s,
                self.pipe_length_m,
                self.pipe_outer_diameter_m,
                self.pipe_wall_thickness_m,
                self.pipe_roughness_m,
                self.elevation_change_m,
                self.local_loss_coefficient,
            )
        )

    def pretty(self) -> str:
        parts: list[str] = []
        if self.pressure_mpa is not None:
            parts.append(f"P={self.pressure_mpa:.4f} MPa")
        if self.temperature_c is not None:
            parts.append(f"T={self.temperature_c:.2f} C")
        if self.enthalpy_kj_kg is not None:
            parts.append(f"h={self.enthalpy_kj_kg:.2f} kJ/kg")
        if self.entropy_kj_kgk is not None:
            parts.append(f"s={self.entropy_kj_kgk:.4f} kJ/kg-K")
        if self.quality is not None:
            parts.append(f"x={self.quality:.4f}")
        if self.specific_volume_m3_kg is not None:
            parts.append(f"v={self.specific_volume_m3_kg:.6f} m3/kg")
        if self.efficiency is not None:
            parts.append(f"eta={self.efficiency:.4f}")
        if self.heat_duty_kw is not None:
            parts.append(f"Q={self.heat_duty_kw:.2f} kW")
        if self.pressure_drop_mpa is not None:
            parts.append(f"dP={self.pressure_drop_mpa:.4f} MPa")
        if self.mass_flow_kg_s is not None:
            parts.append(f"m_dot={self.mass_flow_kg_s:.3f} kg/s")
        if self.pipe_length_m is not None:
            parts.append(f"L={self.pipe_length_m:.2f} m")
        if self.pipe_outer_diameter_m is not None:
            parts.append(f"OD={self.pipe_outer_diameter_m:.4f} m")
        if self.pipe_wall_thickness_m is not None:
            parts.append(f"t={self.pipe_wall_thickness_m:.4f} m")
        if self.pipe_roughness_m is not None:
            parts.append(f"eps={self.pipe_roughness_m:.6f} m")
        if self.elevation_change_m is not None:
            parts.append(f"dz={self.elevation_change_m:.2f} m")
        if self.local_loss_coefficient is not None:
            parts.append(f"K={self.local_loss_coefficient:.3f}")
        return ", ".join(parts) if parts else "(none)"


@dataclass(slots=True)
class Component:
    """Engineering model for a circuit component.

    Contains thermodynamic / process data plus the constraint-tracking
    ``user_input_fields`` that the solver needs. Layout (x, y, width,
    height) lives in ``ComponentLayout`` and transient UI state (is_dirty,
    report, solved_fields, …) lives in ``ComponentUIState``.
    """
    component_id: str
    kind: ComponentKind
    process_kind: ProcessKind
    name: str
    inlet_spec: ThermoSpec = field(default_factory=ThermoSpec)
    outlet_spec: ThermoSpec = field(default_factory=ThermoSpec)
    notes: str = ""
    upstream_ids: list[str] = field(default_factory=list)
    downstream_ids: list[str] = field(default_factory=list)
    inlet_state: Optional[ThermoState] = None
    outlet_state: Optional[ThermoState] = None
    user_input_fields: set[str] = field(default_factory=set)

    @property
    def upstream_id(self) -> Optional[str]:
        return self.upstream_ids[0] if self.upstream_ids else None

    @upstream_id.setter
    def upstream_id(self, value: Optional[str]) -> None:
        self.upstream_ids = [value] if value else []

    @property
    def downstream_id(self) -> Optional[str]:
        return self.downstream_ids[0] if self.downstream_ids else None

    @downstream_id.setter
    def downstream_id(self, value: Optional[str]) -> None:
        self.downstream_ids = [value] if value else []

    def reset_results(self) -> None:
        self.inlet_state = None
        self.outlet_state = None

    def label(self) -> str:
        return f"{self.name}\n{self.kind.value}"


@dataclass(slots=True)
class Circuit:
    components: dict[str, Component] = field(default_factory=dict)
    layouts: dict[str, ComponentLayout] = field(default_factory=dict)
    ui_states: dict[str, ComponentUIState] = field(default_factory=dict)
    start_component_id: str | None = None
    seed_state: ThermoState | None = None
    seed_description: str = ""

    # ── Convenience accessors ──────────────────────────────────────────

    def layout(self, component_id: str) -> ComponentLayout:
        """Return the layout for *component_id*, creating one if needed."""
        if component_id not in self.layouts:
            self.layouts[component_id] = ComponentLayout(component_id=component_id)
        return self.layouts[component_id]

    def ui_state(self, component_id: str) -> ComponentUIState:
        """Return the UI state for *component_id*, creating one if needed."""
        if component_id not in self.ui_states:
            self.ui_states[component_id] = ComponentUIState(component_id=component_id)
        return self.ui_states[component_id]

    def add_component(self, component: Component,
                      layout: ComponentLayout | None = None,
                      ui_state: ComponentUIState | None = None) -> None:
        self.components[component.component_id] = component
        cid = component.component_id
        if layout is not None:
            self.layouts[cid] = layout
        else:
            self.layouts.setdefault(cid, ComponentLayout(component_id=cid))
        if ui_state is not None:
            self.ui_states[cid] = ui_state
        else:
            self.ui_states.setdefault(cid, ComponentUIState(component_id=cid))
        if self.start_component_id is None:
            self.start_component_id = cid

    def remove_component(self, component_id: str) -> None:
        component = self.components.pop(component_id, None)
        if component is None:
            return
        self.layouts.pop(component_id, None)
        self.ui_states.pop(component_id, None)
        for other in self.components.values():
            other.upstream_ids = [item for item in other.upstream_ids if item != component_id]
            other.downstream_ids = [item for item in other.downstream_ids if item != component_id]
        if self.start_component_id == component_id:
            self.start_component_id = next(iter(self.components), None)

    def connect(self, source_id: str, target_id: str) -> None:
        if source_id == target_id:
            return
        source = self.components[source_id]
        target = self.components[target_id]
        if target_id not in source.downstream_ids:
            source.downstream_ids.append(target_id)
        if source_id not in target.upstream_ids:
            target.upstream_ids.append(source_id)

    def disconnect(self, source_id: str, target_id: str) -> None:
        source = self.components.get(source_id)
        target = self.components.get(target_id)
        if source:
            source.downstream_ids = [item for item in source.downstream_ids if item != target_id]
        if target:
            target.upstream_ids = [item for item in target.upstream_ids if item != source_id]

    def outgoing(self, component_id: str) -> list[str]:
        component = self.components.get(component_id)
        if component is None:
            return []
        return [target for target in component.downstream_ids if target in self.components]

    def incoming(self, component_id: str) -> list[str]:
        component = self.components.get(component_id)
        if component is None:
            return []
        return [source for source in component.upstream_ids if source in self.components]

    def ordered_path(self, start_id: str | None = None, max_steps: int = 100) -> list[Component]:
        if not self.components:
            return []
        current_id = start_id or self.start_component_id or next(iter(self.components))
        path: list[Component] = []
        visited: set[str] = set()
        for _ in range(max_steps):
            if current_id is None or current_id in visited:
                break
            component = self.components.get(current_id)
            if component is None:
                break
            path.append(component)
            visited.add(current_id)
            current_id = component.downstream_ids[0] if component.downstream_ids else None
        return path

    def traversal_order(self, start_id: str | None = None, max_steps: int = 1000) -> list[Component]:
        if not self.components:
            return []
        root_id = start_id or self.start_component_id or next(iter(self.components))
        stack: list[str] = [root_id]
        seen: set[str] = set()
        order: list[Component] = []
        steps = 0
        while stack and steps < max_steps:
            steps += 1
            current_id = stack.pop(0)
            if current_id in seen:
                continue
            component = self.components.get(current_id)
            if component is None:
                continue
            seen.add(current_id)
            order.append(component)
            for downstream_id in component.downstream_ids:
                if downstream_id in self.components and downstream_id not in seen:
                    stack.append(downstream_id)
        for component_id, component in self.components.items():
            if component_id not in seen:
                order.append(component)
        return order
