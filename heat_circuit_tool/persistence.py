from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from .model import Circuit, Component, ComponentKind, Edge, ProcessKind, ThermoSpec
from .thermo import ThermoState

SAVE_FORMAT_VERSION = 2
_THERMO_SPEC_FIELD_NAMES = [f.name for f in fields(ThermoSpec)]


def _spec_to_dict(spec: ThermoSpec) -> dict[str, Any]:
    return {
        "pressure_mpa": spec.pressure_mpa,
        "temperature_c": spec.temperature_c,
        "enthalpy_kj_kg": spec.enthalpy_kj_kg,
        "entropy_kj_kgk": spec.entropy_kj_kgk,
        "quality": spec.quality,
        "specific_volume_m3_kg": spec.specific_volume_m3_kg,
        "efficiency": spec.efficiency,
        "heat_duty_kw": spec.heat_duty_kw,
        "pressure_drop_mpa": spec.pressure_drop_mpa,
        "mass_flow_kg_s": spec.mass_flow_kg_s,
        "pipe_length_m": spec.pipe_length_m,
        "pipe_outer_diameter_m": spec.pipe_outer_diameter_m,
        "pipe_wall_thickness_m": spec.pipe_wall_thickness_m,
        "pipe_roughness_m": spec.pipe_roughness_m,
        "elevation_change_m": spec.elevation_change_m,
        "local_loss_coefficient": spec.local_loss_coefficient,
    }


def _spec_from_dict(data: dict[str, Any]) -> ThermoSpec:
    return ThermoSpec(
        pressure_mpa=data.get("pressure_mpa"),
        temperature_c=data.get("temperature_c"),
        enthalpy_kj_kg=data.get("enthalpy_kj_kg"),
        entropy_kj_kgk=data.get("entropy_kj_kgk"),
        quality=data.get("quality"),
        specific_volume_m3_kg=data.get("specific_volume_m3_kg"),
        efficiency=data.get("efficiency"),
        heat_duty_kw=data.get("heat_duty_kw"),
        pressure_drop_mpa=data.get("pressure_drop_mpa"),
        mass_flow_kg_s=data.get("mass_flow_kg_s"),
        pipe_length_m=data.get("pipe_length_m"),
        pipe_outer_diameter_m=data.get("pipe_outer_diameter_m"),
        pipe_wall_thickness_m=data.get("pipe_wall_thickness_m"),
        pipe_roughness_m=data.get("pipe_roughness_m"),
        elevation_change_m=data.get("elevation_change_m"),
        local_loss_coefficient=data.get("local_loss_coefficient"),
    )


def _state_to_dict(state: ThermoState | None) -> dict[str, Any] | None:
    if state is None:
        return None
    return {
        "pressure_mpa": state.pressure_mpa,
        "temperature_c": state.temperature_c,
        "enthalpy_kj_kg": state.enthalpy_kj_kg,
        "entropy_kj_kgk": state.entropy_kj_kgk,
        "specific_volume_m3_kg": state.specific_volume_m3_kg,
        "dynamic_viscosity_pa_s": state.dynamic_viscosity_pa_s,
        "quality": state.quality,
    }


def _state_from_dict(data: dict[str, Any] | None) -> ThermoState | None:
    if data is None:
        return None
    return ThermoState(
        pressure_mpa=float(data.get("pressure_mpa", 0.0)),
        temperature_c=float(data.get("temperature_c", 0.0)),
        enthalpy_kj_kg=float(data.get("enthalpy_kj_kg", 0.0)),
        entropy_kj_kgk=float(data.get("entropy_kj_kgk", 0.0)),
        specific_volume_m3_kg=float(data.get("specific_volume_m3_kg", 0.0)),
        dynamic_viscosity_pa_s=data.get("dynamic_viscosity_pa_s"),
        quality=data.get("quality"),
    )


def _edge_to_dict(edge: Edge) -> dict[str, Any]:
    return {
        "edge_id": edge.edge_id,
        "spec": _spec_to_dict(edge.spec),
        "state": _state_to_dict(edge.state),
        "user_input_fields": sorted(edge.user_input_fields),
        "solved_fields": sorted(edge.solved_fields),
        "conflicting_fields": sorted(edge.conflicting_fields),
    }


def _edge_from_dict(data: dict[str, Any]) -> Edge:
    return Edge(
        edge_id=data["edge_id"],
        spec=_spec_from_dict(data.get("spec", {})),
        state=_state_from_dict(data.get("state")),
        user_input_fields=set(data.get("user_input_fields", [])),
        solved_fields=set(data.get("solved_fields", [])),
        conflicting_fields=set(data.get("conflicting_fields", [])),
    )


def circuit_to_dict(circuit: Circuit) -> dict[str, Any]:
    return {
        "start_component_id": circuit.start_component_id,
        "seed_state": _state_to_dict(circuit.seed_state),
        "seed_description": circuit.seed_description,
        "edges": [_edge_to_dict(edge) for edge in circuit.edges.values()],
        "components": [
            {
                "component_id": component.component_id,
                "kind": component.kind.value,
                "process_kind": component.process_kind.value,
                "name": component.name,
                "x": component.x,
                "y": component.y,
                "width": component.width,
                "height": component.height,
                "notes": component.notes,
                "upstream_ids": list(component.upstream_ids),
                "downstream_ids": list(component.downstream_ids),
                "inlet_edge_id": component.inlet_edge_id,
                "outlet_edge_id": component.outlet_edge_id,
                "unit_preferences": dict(component.unit_preferences),
                "inlet_definition_mode": component.inlet_definition_mode,
                "outlet_definition_mode": component.outlet_definition_mode,
                "is_dirty": component.is_dirty,
                "report": component.report,
            }
            for component in circuit.components.values()
        ],
    }


def circuit_from_dict(data: dict[str, Any]) -> Circuit:
    if "edges" not in data:
        return _circuit_from_legacy_dict(data)

    circuit = Circuit(
        components={},
        edges={},
        start_component_id=data.get("start_component_id"),
        seed_state=_state_from_dict(data.get("seed_state")),
        seed_description=data.get("seed_description", ""),
    )

    for edge_item in data.get("edges", []):
        edge = _edge_from_dict(edge_item)
        circuit.edges[edge.edge_id] = edge

    for item in data.get("components", []):
        component = Component(
            component_id=item["component_id"],
            kind=ComponentKind(item["kind"]),
            process_kind=ProcessKind(item["process_kind"]),
            name=item.get("name", item["component_id"]),
            x=float(item.get("x", 0.0)),
            y=float(item.get("y", 0.0)),
            width=float(item.get("width", 180.0)),
            height=float(item.get("height", 92.0)),
            notes=item.get("notes", ""),
            upstream_ids=list(item.get("upstream_ids", [])),
            downstream_ids=list(item.get("downstream_ids", [])),
            inlet_edge_id=item.get("inlet_edge_id", ""),
            outlet_edge_id=item.get("outlet_edge_id", ""),
            unit_preferences=dict(item.get("unit_preferences", {})),
            inlet_definition_mode=item.get("inlet_definition_mode", "Auto"),
            outlet_definition_mode=item.get("outlet_definition_mode", "Auto"),
            is_dirty=bool(item.get("is_dirty", True)),
            report=item.get("report", ""),
        )
        circuit.add_component(component)
    return circuit


def _circuit_from_legacy_dict(data: dict[str, Any]) -> Circuit:
    """Migrate a pre-refactor (version < 2) save file into the edge-owned model.

    Legacy files stored per-component ``inlet_spec``/``outlet_spec`` (and their
    solved-state/field-tracking counterparts) instead of shared edges. For each
    connected pair, the upstream outlet data and downstream inlet data described
    the same physical state, so they are merged into one new edge (preferring
    user-entered values, then falling back to whichever side has a value).
    """
    circuit = Circuit(
        components={},
        edges={},
        start_component_id=data.get("start_component_id"),
        seed_state=_state_from_dict(data.get("seed_state")),
        seed_description=data.get("seed_description", ""),
    )

    legacy_items = {item["component_id"]: item for item in data.get("components", [])}

    for item in legacy_items.values():
        component = Component(
            component_id=item["component_id"],
            kind=ComponentKind(item["kind"]),
            process_kind=ProcessKind(item["process_kind"]),
            name=item.get("name", item["component_id"]),
            x=float(item.get("x", 0.0)),
            y=float(item.get("y", 0.0)),
            width=float(item.get("width", 180.0)),
            height=float(item.get("height", 92.0)),
            notes=item.get("notes", ""),
            upstream_ids=list(item.get("upstream_ids", [])),
            downstream_ids=list(item.get("downstream_ids", [])),
            unit_preferences=dict(item.get("unit_preferences", {})),
            inlet_definition_mode=item.get("inlet_definition_mode", "Auto"),
            outlet_definition_mode=item.get("outlet_definition_mode", "Auto"),
            is_dirty=bool(item.get("is_dirty", True)),
            report=item.get("report", ""),
        )
        circuit.add_component(component)

    # First pass: seed each component's own boundary edges from its legacy data.
    for item in legacy_items.values():
        component = circuit.components[item["component_id"]]
        inlet_edge = circuit.inlet_edge(component)
        outlet_edge = circuit.outlet_edge(component)
        inlet_edge.spec = _spec_from_dict(item.get("inlet_spec", {}))
        outlet_edge.spec = _spec_from_dict(item.get("outlet_spec", {}))
        inlet_edge.state = _state_from_dict(item.get("inlet_state"))
        outlet_edge.state = _state_from_dict(item.get("outlet_state"))
        legacy_user_fields = set(item.get("user_input_fields", []))
        legacy_solved_fields = set(item.get("solved_fields", []))
        legacy_conflicting_fields = set(item.get("conflicting_fields", []))
        for field_name in legacy_user_fields:
            if field_name.startswith("inlet_"):
                inlet_edge.user_input_fields.add(field_name[len("inlet_"):])
            elif field_name.startswith("outlet_"):
                outlet_edge.user_input_fields.add(field_name[len("outlet_"):])
            else:
                outlet_edge.user_input_fields.add(field_name)
        for field_name in legacy_solved_fields:
            if field_name.startswith("inlet_"):
                inlet_edge.solved_fields.add(field_name[len("inlet_"):])
            elif field_name.startswith("outlet_"):
                outlet_edge.solved_fields.add(field_name[len("outlet_"):])
            else:
                outlet_edge.solved_fields.add(field_name)
        for field_name in legacy_conflicting_fields:
            if field_name.startswith("inlet_"):
                inlet_edge.conflicting_fields.add(field_name[len("inlet_"):])
            elif field_name.startswith("outlet_"):
                outlet_edge.conflicting_fields.add(field_name[len("outlet_"):])
            else:
                outlet_edge.conflicting_fields.add(field_name)

    # Second pass: for each connected pair, merge the upstream outlet edge and
    # downstream inlet edge into a single shared edge (upstream's edge wins,
    # preferring user-entered fields from either side over solved-only values).
    for item in legacy_items.values():
        downstream = circuit.components[item["component_id"]]
        for upstream_id in item.get("upstream_ids", []):
            upstream = circuit.components.get(upstream_id)
            if upstream is None or upstream_id not in legacy_items:
                continue
            if len(downstream.upstream_ids) != 1 or len(upstream.downstream_ids) != 1:
                # Mixer/splitter junction: keep each side's own edge (out of scope).
                continue
            shared_edge = circuit.outlet_edge(upstream)
            downstream_edge = circuit.inlet_edge(downstream)
            if shared_edge is downstream_edge:
                continue
            merged_user_fields = shared_edge.user_input_fields | downstream_edge.user_input_fields
            for attr in _THERMO_SPEC_FIELD_NAMES:
                downstream_value = getattr(downstream_edge.spec, attr)
                if downstream_value is None:
                    continue
                upstream_value = getattr(shared_edge.spec, attr)
                if upstream_value is None or (attr in downstream_edge.user_input_fields and attr not in shared_edge.user_input_fields):
                    setattr(shared_edge.spec, attr, downstream_value)
            shared_edge.user_input_fields = merged_user_fields
            shared_edge.state = shared_edge.state or downstream_edge.state
            circuit.edges.pop(downstream.inlet_edge_id, None)
            downstream.inlet_edge_id = shared_edge.edge_id

    return circuit


def save_project_file(
    file_path: str,
    circuit: Circuit,
    snapshots: list[dict[str, Any]],
    latest_solved: dict[str, Any] | None = None,
) -> None:
    payload = {
        "version": SAVE_FORMAT_VERSION,
        "active_circuit": circuit_to_dict(circuit),
        "snapshots": snapshots,
        "latest_solved": latest_solved,
    }
    Path(file_path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_project_file(file_path: str) -> dict[str, Any]:
    payload = json.loads(Path(file_path).read_text(encoding="utf-8"))
    if "active_circuit" not in payload:
        raise ValueError("Invalid project file: missing active_circuit")
    return payload
