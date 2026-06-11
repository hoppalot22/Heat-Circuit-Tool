from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec
from .model_layout import ComponentLayout, ComponentUIState
from .thermo import state_from_dict, state_to_dict, ThermoState


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


def circuit_to_dict(circuit: Circuit) -> dict[str, Any]:
    """Serialize a Circuit, including layout and UI state, to a dict.

    Layout fields (x, y, width, height) are read from ``circuit.layouts``.
    UI state fields (unit_preferences, inlet/outlet_definition_mode,
    solved_fields, conflicting_fields, is_dirty, report) are read from
    ``circuit.ui_states``.
    """
    components_list = []
    for component in circuit.components.values():
        cid = component.component_id
        layout = circuit.layouts.get(cid, ComponentLayout(component_id=cid))
        ui = circuit.ui_states.get(cid, ComponentUIState(component_id=cid))

        components_list.append({
            "component_id": component.component_id,
            "kind": component.kind.value,
            "process_kind": component.process_kind.value,
            "name": component.name,
            "x": layout.x,
            "y": layout.y,
            "width": layout.width,
            "height": layout.height,
            "inlet_spec": _spec_to_dict(component.inlet_spec),
            "outlet_spec": _spec_to_dict(component.outlet_spec),
            "notes": component.notes,
            "upstream_ids": list(component.upstream_ids),
            "downstream_ids": list(component.downstream_ids),
            "inlet_state": state_to_dict(component.inlet_state),
            "outlet_state": state_to_dict(component.outlet_state),
            "unit_preferences": dict(ui.unit_preferences),
            "inlet_definition_mode": ui.inlet_definition_mode,
            "outlet_definition_mode": ui.outlet_definition_mode,
            "user_input_fields": sorted(component.user_input_fields),
            "solved_fields": sorted(ui.solved_fields),
            "conflicting_fields": sorted(ui.conflicting_fields),
            "is_dirty": ui.is_dirty,
            "report": ui.report,
        })

    return {
        "start_component_id": circuit.start_component_id,
        "seed_state": state_to_dict(circuit.seed_state),
        "seed_description": circuit.seed_description,
        "components": components_list,
    }


def circuit_from_dict(data: dict[str, Any]) -> Circuit:
    """Deserialize a Circuit from a dict, including layout and UI state."""
    circuit = Circuit(
        components={},
        start_component_id=data.get("start_component_id"),
        seed_state=state_from_dict(data.get("seed_state")),
        seed_description=data.get("seed_description", ""),
    )

    for item in data.get("components", []):
        cid = item["component_id"]

        component = Component(
            component_id=cid,
            kind=ComponentKind(item["kind"]),
            process_kind=ProcessKind(item["process_kind"]),
            name=item.get("name", cid),
            inlet_spec=_spec_from_dict(item.get("inlet_spec", {})),
            outlet_spec=_spec_from_dict(item.get("outlet_spec", {})),
            notes=item.get("notes", ""),
            upstream_ids=list(item.get("upstream_ids", [])),
            downstream_ids=list(item.get("downstream_ids", [])),
            inlet_state=state_from_dict(item.get("inlet_state")),
            outlet_state=state_from_dict(item.get("outlet_state")),
            user_input_fields=set(item.get("user_input_fields", [])),
        )

        layout = ComponentLayout(
            component_id=cid,
            x=float(item.get("x", 0.0)),
            y=float(item.get("y", 0.0)),
            width=float(item.get("width", 180.0)),
            height=float(item.get("height", 92.0)),
        )

        ui_state = ComponentUIState(
            component_id=cid,
            unit_preferences=dict(item.get("unit_preferences", {})),
            inlet_definition_mode=item.get("inlet_definition_mode", "Auto"),
            outlet_definition_mode=item.get("outlet_definition_mode", "Auto"),
            solved_fields=set(item.get("solved_fields", [])),
            conflicting_fields=set(item.get("conflicting_fields", [])),
            is_dirty=item.get("is_dirty", True),
            report=item.get("report", ""),
        )

        circuit.add_component(component, layout=layout, ui_state=ui_state)

    return circuit


def save_project_file(path: str, circuit: Circuit,
                      snapshots: list[dict[str, Any]] | None = None,
                      latest_solved: dict[str, Any] | None = None) -> None:
    payload = {
        "active_circuit": circuit_to_dict(circuit),
        "snapshots": snapshots or [],
        "latest_solved": latest_solved,
    }
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_project_file(path: str) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text)