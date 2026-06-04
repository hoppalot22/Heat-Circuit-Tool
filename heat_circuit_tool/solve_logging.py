from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .model import Circuit
from .solver import CircuitSolution
from .thermo import ThermoState


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


def _component_debug(circuit: Circuit) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for component in circuit.components.values():
        rows.append(
            {
                "component_id": component.component_id,
                "name": component.name,
                "kind": component.kind.value,
                "process_kind": component.process_kind.value,
                "upstream_ids": list(component.upstream_ids),
                "downstream_ids": list(component.downstream_ids),
                "inlet_spec": component.inlet_spec.pretty(),
                "outlet_spec": component.outlet_spec.pretty(),
                "unit_preferences": dict(component.unit_preferences),
                "user_input_fields": sorted(component.user_input_fields),
                "solved_fields": sorted(component.solved_fields),
                "conflicting_fields": sorted(component.conflicting_fields),
                "report": component.report,
                "inlet_state": _state_to_dict(component.inlet_state),
                "outlet_state": _state_to_dict(component.outlet_state),
            }
        )
    return rows


def append_solve_log(log_file_path: str, circuit: Circuit, solution: CircuitSolution) -> None:
    path = Path(log_file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    entry: dict[str, Any] = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "system_status": solution.system_status,
        "summary_lines": solution.summary_lines(),
        "metrics": {
            "heat_in_kj_kg": solution.total_heat_in_kj_kg,
            "heat_out_kj_kg": solution.total_heat_out_kj_kg,
            "turbine_work_kj_kg": solution.total_turbine_work_kj_kg,
            "pump_work_kj_kg": solution.total_pump_work_kj_kg,
            "net_work_kj_kg": solution.net_work_kj_kg,
            "thermal_efficiency": solution.thermal_efficiency,
            "back_work_ratio": solution.back_work_ratio,
            "closure_error_h_kj_kg": solution.closure_error_h_kj_kg,
            "closure_error_p_mpa": solution.closure_error_p_mpa,
        },
        "messages": list(solution.messages),
        "component_results": [
            {
                "component_id": result.component_id,
                "component_name": result.component_name,
                "kind": result.kind.value,
                "process_kind": result.process_kind.value,
                "status": result.status,
                "conflicting_fields": list(result.conflicting_fields),
                "work_kj_kg": result.work_kj_kg,
                "heat_kj_kg": result.heat_kj_kg,
                "message": result.message,
                "inlet_state": _state_to_dict(result.inlet_state),
                "outlet_state": _state_to_dict(result.outlet_state),
            }
            for result in solution.component_results
        ],
    }

    if solution.system_status in {"Underconstrained", "Overconstrained"}:
        entry["debug"] = {
            "start_component_id": circuit.start_component_id,
            "seed_description": circuit.seed_description,
            "seed_state": _state_to_dict(circuit.seed_state),
            "underconstrained_components": list(solution.underconstrained_components),
            "overconstrained_components": list(solution.overconstrained_components),
            "unsolved_components": list(solution.unsolved_components),
            "components": _component_debug(circuit),
        }

    with path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(entry, ensure_ascii=True) + "\n")
