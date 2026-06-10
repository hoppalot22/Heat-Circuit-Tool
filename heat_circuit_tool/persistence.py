from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec
from .thermo import ThermoState


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


def circuit_to_dict(circuit: Circuit) -> dict[str, Any]:
    return {
        "start_component_id": circuit.start_component_id,
        "seed_state": _state_to_dict(circuit.seed_state),
        "seed_description": circuit.seed_description,
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
                "inlet_spec": _spec_to_dict(component.inlet_spec),
                "outlet_spec": _spec_to_dict(component.outlet_spec),
                "notes": component.notes,
                "upstream_ids": list(component.upstream_ids),
                "downstream_ids": list(component.downstream_ids),
                "inlet_state": _state_to_dict(component.inlet_state),
                "outlet_state": _state_to_dict(component.outlet_state),
                "unit_preferences": dict(component.unit_preferences),
                "inlet_definition_mode": component.inlet_definition_mode,
                "outlet_definition_mode": component.outlet_definition_mode,
                "user_input_fields": sorted(component.user_input_fields),
                "solved_fields": sorted(component.solved_fields),
                "conflicting_fields": sorted(component.conflicting_fields),
                "is_dirty": component.is_dirty,
                "report": component.report,
            }
            for component in circuit.components.values()
        ],
    }


def circuit_from_dict(data: dict[str, Any]) -> Circuit:
    circuit = Circuit(
        components={},
        start_component_id=data.get("start_component_id"),
        seed_state=_state_from_dict(data.get("seed_state")),
        seed_description=data.get("seed_description", ""),
    )

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
            inlet_spec=_spec_from_dict(item.get("inlet_spec", {})),
            outlet_spec=_spec_from_dict(item.get("outlet_spec", {})),
            notes=item.get("notes", ""),
            upstream_ids=list(item.get("upstream_ids", [])),
            downstream_ids=list(item.get("downstream_ids", [])),
            inlet_state=_state_from_dict(item.get("inlet_state")),
            outlet_state=_state_from_dict(item.get("outlet_state")),
            unit_preferences=dict(item.get("unit_preferences", {})),
            inlet_definition_mode=item.get("inlet_definition_mode", "Auto"),
            outlet_definition_mode=item.get("outlet_definition_mode", "Auto"),
            user_input_fields=set(item.get("user_input_fields", [])),
            solved_fields=set(item.get("solved_fields", [])),
            conflicting_fields=set(item.get("conflicting_fields", [])),
            is_dirty=bool(item.get("is_dirty", True)),
            report=item.get("report", ""),
        )
        circuit.components[component.component_id] = component
    return circuit


def save_project_file(
    file_path: str,
    circuit: Circuit,
    snapshots: list[dict[str, Any]],
    latest_solved: dict[str, Any] | None = None,
) -> None:
    payload = {
        "version": 1,
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
