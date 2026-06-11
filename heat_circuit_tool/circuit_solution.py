"""Immutable solution models produced by the solver.

These dataclasses represent the results of solving a circuit without
mutating the original Component objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose
from typing import Optional

from .model import ComponentKind, ProcessKind
from .thermo import ThermoState


@dataclass(slots=True, frozen=True)
class ComponentSolution:
    """Results for a single component after solving.

    This is an immutable record — the solver creates one per component
    rather than mutating Component's inlet_state / outlet_state.
    """
    component_id: str
    component_name: str
    kind: ComponentKind
    process_kind: ProcessKind
    inlet_state: Optional[ThermoState] = None
    outlet_state: Optional[ThermoState] = None
    work_kj_kg: float = 0.0
    heat_kj_kg: float = 0.0
    status: str = "Unsolved"
    conflicting_fields: list[str] = field(default_factory=list)
    message: str = ""


@dataclass(slots=True, frozen=True)
class CircuitSolution:
    """Overall results for a solved circuit.

    This is an immutable record. Components dict maps component_id
    to its ComponentSolution.
    """
    components: dict[str, ComponentSolution] = field(default_factory=dict)
    total_heat_in_kj_kg: float = 0.0
    total_heat_out_kj_kg: float = 0.0
    total_turbine_work_kj_kg: float = 0.0
    total_pump_work_kj_kg: float = 0.0
    net_work_kj_kg: float = 0.0
    thermal_efficiency: float | None = None
    back_work_ratio: float | None = None
    closure_error_h_kj_kg: float | None = None
    closure_error_p_mpa: float | None = None
    system_status: str = "Unknown"
    underconstrained_components: list[str] = field(default_factory=list)
    overconstrained_components: list[str] = field(default_factory=list)
    unsolved_components: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)

    @classmethod
    def from_results(cls, results: list[ComponentSolution]) -> CircuitSolution:
        """Build a CircuitSolution from a list of ComponentSolutions."""
        if not results:
            return cls(system_status="Unknown")
        return cls(
            components={r.component_id: r for r in results},
        )

    def result_for(self, component_id: str) -> Optional[ComponentSolution]:
        return self.components.get(component_id)

    def summary_lines(self) -> list[str]:
        lines = [
            f"Heat in: {self.total_heat_in_kj_kg:.2f} kJ/kg",
            f"Heat out: {self.total_heat_out_kj_kg:.2f} kJ/kg",
            f"Turbine work: {self.total_turbine_work_kj_kg:.2f} kJ/kg",
            f"Pump work: {self.total_pump_work_kj_kg:.2f} kJ/kg",
            f"Net work: {self.net_work_kj_kg:.2f} kJ/kg",
        ]
        if self.thermal_efficiency is not None:
            lines.append(f"Thermal efficiency: {self.thermal_efficiency * 100.0:.2f}%")
        if self.back_work_ratio is not None:
            lines.append(f"Back work ratio: {self.back_work_ratio:.4f}")
        if self.closure_error_h_kj_kg is not None:
            lines.append(f"Loop closure h error: {self.closure_error_h_kj_kg:.4f} kJ/kg")
        if self.closure_error_p_mpa is not None:
            lines.append(f"Loop closure P error: {self.closure_error_p_mpa:.6f} MPa")
        lines.append(f"Constraint status: {self.system_status}")
        if self.underconstrained_components:
            lines.append("Underconstrained components: "
                         + ", ".join(self.underconstrained_components))
        if self.overconstrained_components:
            lines.append("Overconstrained components: "
                         + ", ".join(self.overconstrained_components))
        if self.unsolved_components:
            lines.append("Unsolved components: "
                         + ", ".join(self.unsolved_components))
        return lines