from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

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
    ISOTHERMAL = "Isothermal"


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
class Edge:
    """Shared thermodynamic state for one connection (or boundary port) between components.

    An edge is the single owner of the spec/state/field-tracking data for the physical
    state at a point in the circuit. Both the upstream component's outlet and the
    downstream component's inlet reference the *same* `Edge` instance once connected.
    """

    edge_id: str
    spec: ThermoSpec = field(default_factory=ThermoSpec)
    state: Optional[ThermoState] = None
    user_input_fields: set[str] = field(default_factory=set)
    solved_fields: set[str] = field(default_factory=set)
    conflicting_fields: set[str] = field(default_factory=set)


@dataclass(slots=True)
class Component:
    component_id: str
    kind: ComponentKind
    process_kind: ProcessKind
    name: str
    x: float = 0.0
    y: float = 0.0
    width: float = 180.0
    height: float = 92.0
    notes: str = ""
    upstream_ids: list[str] = field(default_factory=list)
    downstream_ids: list[str] = field(default_factory=list)
    inlet_edge_id: str = ""
    outlet_edge_id: str = ""
    inlet_edge_ids: list[str] = field(default_factory=list)
    outlet_edge_ids: list[str] = field(default_factory=list)
    unit_preferences: dict[str, str] = field(default_factory=dict)
    inlet_definition_mode: str = "Auto"
    outlet_definition_mode: str = "Auto"
    is_dirty: bool = True
    report: str = ""

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

    def center(self) -> tuple[float, float]:
        return self.x + self.width / 2.0, self.y + self.height / 2.0

    def inlet_port(self) -> tuple[float, float]:
        return self.x, self.y + self.height / 2.0

    def outlet_port(self) -> tuple[float, float]:
        return self.x + self.width, self.y + self.height / 2.0

    def reset_results(self) -> None:
        self.report = ""

    def label(self) -> str:
        return f"{self.name}\n{self.kind.value}"


@dataclass(slots=True)
class Circuit:
    components: dict[str, Component] = field(default_factory=dict)
    edges: dict[str, Edge] = field(default_factory=dict)
    start_component_id: str | None = None
    seed_state: ThermoState | None = None
    seed_description: str = ""

    def add_component(self, component: Component) -> None:
        if component.component_id in self.components:
            raise ValueError(f"Duplicate component_id '{component.component_id}' is not allowed.")
        self.components[component.component_id] = component
        if self.start_component_id is None:
            self.start_component_id = component.component_id
        if not component.inlet_edge_id:
            component.inlet_edge_id = f"{component.component_id}:inlet"
        if component.inlet_edge_id not in self.edges:
            self.edges[component.inlet_edge_id] = Edge(edge_id=component.inlet_edge_id)
        if component.inlet_edge_id not in component.inlet_edge_ids:
            component.inlet_edge_ids.insert(0, component.inlet_edge_id)
        if not component.outlet_edge_id:
            component.outlet_edge_id = f"{component.component_id}:outlet"
        if component.outlet_edge_id not in self.edges:
            self.edges[component.outlet_edge_id] = Edge(edge_id=component.outlet_edge_id)
        if component.outlet_edge_id not in component.outlet_edge_ids:
            component.outlet_edge_ids.insert(0, component.outlet_edge_id)

    def inlet_edge(self, component: Component) -> Edge:
        return self.edges.setdefault(component.inlet_edge_id, Edge(edge_id=component.inlet_edge_id))

    def outlet_edge(self, component: Component) -> Edge:
        return self.edges.setdefault(component.outlet_edge_id, Edge(edge_id=component.outlet_edge_id))

    def inlet_edges(self, component: Component) -> list[Edge]:
        return [self.edges[edge_id] for edge_id in component.inlet_edge_ids if edge_id in self.edges]

    def outlet_edges(self, component: Component) -> list[Edge]:
        return [self.edges[edge_id] for edge_id in component.outlet_edge_ids if edge_id in self.edges]

    def edge_for(self, component_id: str, side: str) -> Optional[Edge]:
        component = self.components.get(component_id)
        if component is None:
            return None
        return self.inlet_edge(component) if side == "inlet" else self.outlet_edge(component)

    def _fresh_boundary_edge(self, component: Component, side: str) -> None:
        edge_id = f"{component.component_id}:{side}"
        self.edges[edge_id] = Edge(edge_id=edge_id)
        if side == "inlet":
            component.inlet_edge_id = edge_id
        else:
            component.outlet_edge_id = edge_id

    def remove_component(self, component_id: str) -> None:
        component = self.components.pop(component_id, None)
        if component is None:
            return
        removed_edge_ids = set(component.inlet_edge_ids) | set(component.outlet_edge_ids)
        removed_edge_ids.update({component.inlet_edge_id, component.outlet_edge_id})
        for other in self.components.values():
            other.upstream_ids = [item for item in other.upstream_ids if item != component_id]
            other.downstream_ids = [item for item in other.downstream_ids if item != component_id]
            other.inlet_edge_ids = [edge_id for edge_id in other.inlet_edge_ids if edge_id not in removed_edge_ids]
            other.outlet_edge_ids = [edge_id for edge_id in other.outlet_edge_ids if edge_id not in removed_edge_ids]
            if not other.inlet_edge_ids:
                self._fresh_boundary_edge(other, "inlet")
                other.inlet_edge_ids = [other.inlet_edge_id]
            elif other.inlet_edge_id not in other.inlet_edge_ids:
                other.inlet_edge_id = other.inlet_edge_ids[0]
            if not other.outlet_edge_ids:
                self._fresh_boundary_edge(other, "outlet")
                other.outlet_edge_ids = [other.outlet_edge_id]
            elif other.outlet_edge_id not in other.outlet_edge_ids:
                other.outlet_edge_id = other.outlet_edge_ids[0]
        for edge_id in removed_edge_ids:
            self.edges.pop(edge_id, None)
        if self.start_component_id == component_id:
            self.start_component_id = next(iter(self.components), None)

    def connect(self, source_id: str, target_id: str) -> None:
        if source_id == target_id:
            raise ValueError(f"Cannot create a self-link from '{source_id}' to itself.")
        source = self.components.get(source_id)
        target = self.components.get(target_id)
        if source is None or target is None:
            raise ValueError(f"Invalid connection endpoints: '{source_id}' -> '{target_id}'.")
        if target_id in source.downstream_ids and source_id in target.upstream_ids:
            return
        if target_id not in source.downstream_ids:
            source.downstream_ids.append(target_id)
        if source_id not in target.upstream_ids:
            target.upstream_ids.append(source_id)
        if not source.outlet_edge_ids:
            source.outlet_edge_ids.append(source.outlet_edge_id)
        if not target.inlet_edge_ids:
            target.inlet_edge_ids.append(target.inlet_edge_id)
        if len(source.downstream_ids) == 1:
            edge_id = source.outlet_edge_id
        else:
            edge_id = f"{source.component_id}:outlet:{target.component_id}"
            if edge_id not in self.edges:
                self.edges[edge_id] = Edge(edge_id=edge_id)
            source.outlet_edge_ids.append(edge_id)
        if len(target.upstream_ids) == 1:
            if target.inlet_edge_id != edge_id:
                self.edges.pop(target.inlet_edge_id, None)
                target.inlet_edge_id = edge_id
                target.inlet_edge_ids[0] = edge_id
        else:
            target.inlet_edge_ids.append(edge_id)
        if edge_id not in source.outlet_edge_ids:
            source.outlet_edge_ids.append(edge_id)

    def disconnect(self, source_id: str, target_id: str) -> None:
        source = self.components.get(source_id)
        target = self.components.get(target_id)
        if source:
            source.downstream_ids = [item for item in source.downstream_ids if item != target_id]
        if target:
            target.upstream_ids = [item for item in target.upstream_ids if item != source_id]
        if source and target:
            shared_ids = set(source.outlet_edge_ids) & set(target.inlet_edge_ids)
            for edge_id in shared_ids:
                source.outlet_edge_ids.remove(edge_id)
                target.inlet_edge_ids.remove(edge_id)
                self.edges.pop(edge_id, None)
            if not source.outlet_edge_ids:
                self._fresh_boundary_edge(source, "outlet")
                source.outlet_edge_ids = [source.outlet_edge_id]
            elif source.outlet_edge_id not in source.outlet_edge_ids:
                source.outlet_edge_id = source.outlet_edge_ids[0]
            if not target.inlet_edge_ids:
                self._fresh_boundary_edge(target, "inlet")
                target.inlet_edge_ids = [target.inlet_edge_id]
            elif target.inlet_edge_id not in target.inlet_edge_ids:
                target.inlet_edge_id = target.inlet_edge_ids[0]

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
