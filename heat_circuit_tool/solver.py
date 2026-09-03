from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from itertools import combinations
from math import isclose, log10, pi
from typing import Optional

from .model import Circuit, Component, ComponentKind, Edge, ProcessKind, ThermoSpec
from .thermo import StateSpec, SteamPropertyBackend, ThermoState
from .units import almost_equal

_SPEC_FIELD_NAMES = [f.name for f in dataclasses.fields(ThermoSpec)]

# Fields that a process kind conserves across a component regardless of whether
# the full thermodynamic state can be resolved yet (e.g. isobaric outlet pressure
# always equals inlet pressure, minus any user-specified pressure drop).
_CONSERVED_FIELD_BY_PROCESS = {
    ProcessKind.ISOBARIC: "pressure_mpa",
    ProcessKind.ISOCHORIC: "specific_volume_m3_kg",
    ProcessKind.ISENTHALPIC: "enthalpy_kj_kg",
}
_CONSERVATION_EXCLUDED_KINDS = {ComponentKind.PIPE, ComponentKind.MIXER, ComponentKind.SPLITTER}

_PIPE_ONLY_FIELDS = {
    "heat_duty_kw",
    "pressure_drop_mpa",
    "mass_flow_kg_s",
    "pipe_length_m",
    "pipe_outer_diameter_m",
    "pipe_wall_thickness_m",
    "pipe_roughness_m",
    "elevation_change_m",
    "local_loss_coefficient",
}


def _scoped_user_fields(circuit: Circuit, component: Component) -> set[str]:
    """Rebuild the legacy prefixed field-name view ("inlet_x"/"outlet_x") from edges."""
    inlet_edge = circuit.inlet_edge(component)
    outlet_edge = circuit.outlet_edge(component)
    fields: set[str] = {f"inlet_{name}" for name in inlet_edge.user_input_fields}
    for name in outlet_edge.user_input_fields:
        fields.add(name if name in _PIPE_ONLY_FIELDS else f"outlet_{name}")
    return fields


@dataclass(slots=True)
class ComponentResult:
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


@dataclass(slots=True)
class CircuitSolution:
    component_results: list[ComponentResult] = field(default_factory=list)
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
            lines.append("Underconstrained components: " + ", ".join(self.underconstrained_components))
        if self.overconstrained_components:
            lines.append("Overconstrained components: " + ", ".join(self.overconstrained_components))
        if self.unsolved_components:
            lines.append("Unsolved components: " + ", ".join(self.unsolved_components))
        return lines


@dataclass(slots=True)
class ComponentConstraintDiagnostic:
    component_id: str
    component_name: str
    status: str
    message: str
    inlet_available: bool = False
    additional_info_required: int = 0
    missing_fields: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ConstraintDiagnostics:
    system_status: str = "Unknown"
    component_diagnostics: list[ComponentConstraintDiagnostic] = field(default_factory=list)
    underconstrained_components: list[str] = field(default_factory=list)
    overconstrained_components: list[str] = field(default_factory=list)
    blocked_components: list[str] = field(default_factory=list)
    total_additional_info_required: int = 0
    frontier_min_additional_info: int | None = None
    propagation_hint: str = ""

    def summary_lines(self) -> list[str]:
        lines = [f"Live Constraint Status: {self.system_status}"]
        if self.overconstrained_components:
            lines.append("Potentially overconstrained: " + ", ".join(self.overconstrained_components))
        if self.underconstrained_components:
            lines.append("Underconstrained: " + ", ".join(self.underconstrained_components))
        if self.blocked_components:
            lines.append("Blocked by upstream unresolved state: " + ", ".join(self.blocked_components))
        if self.frontier_min_additional_info is not None:
            lines.append(f"Minimum extra inputs to unlock next solvable step: {self.frontier_min_additional_info}")
        lines.append(f"Estimated extra user inputs needed now: {self.total_additional_info_required}")
        if self.propagation_hint:
            lines.append(self.propagation_hint)
        return lines


class SolverError(RuntimeError):
    pass


class ConstraintReport:
    def __init__(self, status: str, message: str):
        self.status = status
        self.message = message


class ThermoSolver:
    def __init__(self, backend: SteamPropertyBackend | None = None):
        self.backend = backend or SteamPropertyBackend()

    def solve_circuit(self, circuit: Circuit) -> CircuitSolution:
        if circuit.start_component_id is None:
            raise SolverError("Circuit has no start component.")
        if circuit.seed_state is None:
            raise SolverError("Circuit needs a seed state before it can be solved.")

        solution = CircuitSolution()
        order = circuit.traversal_order(circuit.start_component_id)
        if not order:
            raise SolverError("Circuit has no components to solve.")

        results_by_id = self.propagate(circuit, reset=True)

        for component in order:
            result = results_by_id.get(component.component_id)
            if result is None:
                result = ComponentResult(
                    component_id=component.component_id,
                    component_name=component.name,
                    kind=component.kind,
                    process_kind=component.process_kind,
                    inlet_state=circuit.inlet_edge(component).state,
                    outlet_state=circuit.outlet_edge(component).state,
                    status="Undeterminable",
                    message="No solvable inlet state could be resolved from upstream links.",
                )
                component.report = result.message
            solution.component_results.append(result)

        self._accumulate_metrics(solution)
        self._evaluate_closure(circuit, solution)
        self._evaluate_constraints(solution)
        self._evaluate_connectivity(circuit, solution)
        return solution

    def propagate(self, circuit: Circuit, reset: bool = True) -> dict[str, ComponentResult]:
        """Run a forward/backward fixed-point propagation pass across the whole circuit.

        Unlike `solve_circuit`, this does not require a seed state or start component
        and never raises for components that cannot yet be solved (they are simply
        skipped). This lets a single field edit cascade to every component whose
        state is now derivable, not just the one that was just edited.
        """
        if reset:
            for component in circuit.components.values():
                component.reset_results()
            for edge in circuit.edges.values():
                for field_name in _SPEC_FIELD_NAMES:
                    if field_name not in edge.user_input_fields:
                        setattr(edge.spec, field_name, None)
                edge.state = None
                edge.solved_fields.clear()
                edge.conflicting_fields.clear()

        order = circuit.traversal_order(circuit.start_component_id) if circuit.components else []
        results_by_id: dict[str, ComponentResult] = {}
        for _ in range(20):
            changed, blocked_ids = self._infer_conserved_fields(circuit, results_by_id)
            for component in order:
                if component.component_id in blocked_ids:
                    continue
                inlet_state = self._resolve_inlet_state(circuit, component)
                outlet_state_hint = self._resolve_outlet_state(circuit, component)
                if inlet_state is None and outlet_state_hint is None:
                    continue
                inlet_edge = circuit.inlet_edge(component)
                outlet_edge = circuit.outlet_edge(component)
                previous_inlet = inlet_edge.state
                previous_outlet = outlet_edge.state
                try:
                    result = self.solve_component(circuit, component, inlet_state, outlet_state_hint)
                except SolverError:
                    continue
                inlet_edge.state = result.inlet_state
                outlet_edge.state = result.outlet_state
                for connection_edge in circuit.outlet_edges(component):
                    if connection_edge is outlet_edge or connection_edge.user_input_fields:
                        continue
                    connection_edge.state = result.outlet_state
                component.report = result.message
                results_by_id[component.component_id] = result
                if self._state_changed(previous_inlet, inlet_edge.state) or self._state_changed(previous_outlet, outlet_edge.state):
                    changed = True
            if not changed:
                break
        return results_by_id

    def _infer_conserved_fields(
        self, circuit: Circuit, results_by_id: dict[str, ComponentResult]
    ) -> tuple[bool, set[str]]:
        """Carry a process-conserved field (e.g. isobaric pressure) across a component.

        This works even when neither side has enough properties yet for a full
        thermodynamic state, so a single user-defined field can light up its
        conserved counterpart on the other side of the same component immediately.
        If both sides are already defined and disagree, the component is flagged
        Overconstrained and returned in `blocked_ids` so the caller skips solving
        it (and anything depending solely on it) until the conflict is resolved.
        """
        changed = False
        blocked_ids: set[str] = set()
        for component in circuit.components.values():
            if component.kind in _CONSERVATION_EXCLUDED_KINDS:
                continue
            field_name = _CONSERVED_FIELD_BY_PROCESS.get(component.process_kind)
            if field_name is None:
                continue
            inlet_edge = circuit.inlet_edge(component)
            outlet_edge = circuit.outlet_edge(component)
            inlet_value = getattr(inlet_edge.spec, field_name)
            outlet_value = getattr(outlet_edge.spec, field_name)
            drop = outlet_edge.spec.pressure_drop_mpa or 0.0 if field_name == "pressure_mpa" else 0.0
            if inlet_value is not None and outlet_value is not None:
                expected_outlet = inlet_value - drop
                if not isclose(expected_outlet, outlet_value, rel_tol=1e-6, abs_tol=1e-6):
                    inlet_edge.conflicting_fields.add(field_name)
                    outlet_edge.conflicting_fields.add(field_name)
                    blocked_ids.add(component.component_id)
                    message = (
                        f"{component.name}: inlet and outlet {field_name} disagree for a "
                        f"{component.process_kind.value} process (expected outlet={expected_outlet:.4g}, "
                        f"got {outlet_value:.4g})."
                    )
                    component.report = message
                    component.is_dirty = False
                    results_by_id[component.component_id] = ComponentResult(
                        component_id=component.component_id,
                        component_name=component.name,
                        kind=component.kind,
                        process_kind=component.process_kind,
                        inlet_state=None,
                        outlet_state=None,
                        status="Overconstrained",
                        conflicting_fields=[f"inlet_{field_name}", f"outlet_{field_name}"],
                        message=message,
                    )
                continue
            if inlet_value is not None and outlet_value is None:
                setattr(outlet_edge.spec, field_name, inlet_value - drop)
                outlet_edge.solved_fields.add(field_name)
                component.is_dirty = False
                changed = True
            elif outlet_value is not None and inlet_value is None:
                setattr(inlet_edge.spec, field_name, outlet_value + drop)
                inlet_edge.solved_fields.add(field_name)
                component.is_dirty = False
                changed = True
        return changed, blocked_ids

    def _resolve_inlet_state(self, circuit: Circuit, component: Component) -> ThermoState | None:
        inlet_edge = circuit.inlet_edge(component)
        user_inlet = self._state_from_thermo_spec(inlet_edge.spec)
        if user_inlet is not None:
            return user_inlet
        inlet_edges = circuit.inlet_edges(component)
        upstream_states = [edge.state for edge in inlet_edges if edge.state is not None]
        if not upstream_states:
            if component.component_id == circuit.start_component_id and circuit.seed_state is not None:
                return circuit.seed_state
            return None
        if len(upstream_states) == 1:
            return upstream_states[0]
        upstream_weights = [edge.spec.mass_flow_kg_s for edge in inlet_edges if edge.state is not None]
        return self._mix_states(upstream_states, upstream_weights)

    def _resolve_outlet_state(self, circuit: Circuit, component: Component) -> ThermoState | None:
        outlet_edge = circuit.outlet_edge(component)
        user_outlet = self._state_from_thermo_spec(outlet_edge.spec)
        if user_outlet is not None:
            return user_outlet
        outlet_edges = circuit.outlet_edges(component)
        downstream_states = [edge.state for edge in outlet_edges if edge.state is not None]
        if not downstream_states:
            return None
        if len(downstream_states) == 1:
            return downstream_states[0]
        downstream_weights = [edge.spec.mass_flow_kg_s for edge in outlet_edges if edge.state is not None]
        return self._mix_states(downstream_states, downstream_weights)

    def _state_from_thermo_spec(self, spec: ThermoSpec) -> ThermoState | None:
        full = spec.to_state_spec()
        fields = full.defined_fields()
        if len(fields) < 2:
            return None

        best_state: ThermoState | None = None
        for pair in combinations(fields, 2):
            if frozenset(pair) not in self.backend.supported_pairs:
                continue
            candidate = StateSpec(
                pressure_mpa=full.pressure_mpa if "pressure_mpa" in pair else None,
                temperature_c=full.temperature_c if "temperature_c" in pair else None,
                enthalpy_kj_kg=full.enthalpy_kj_kg if "enthalpy_kj_kg" in pair else None,
                entropy_kj_kgk=full.entropy_kj_kgk if "entropy_kj_kgk" in pair else None,
                quality=full.quality if "quality" in pair else None,
                specific_volume_m3_kg=full.specific_volume_m3_kg if "specific_volume_m3_kg" in pair else None,
            )
            try:
                state = self.backend.make_state(candidate)
            except Exception:
                continue
            if self._state_matches_optional_fields(state, full):
                return state
            if best_state is None:
                best_state = state
        return best_state

    def _state_matches_optional_fields(self, state: ThermoState, spec: StateSpec) -> bool:
        checks: list[tuple[float | None, float | None, float]] = [
            (spec.pressure_mpa, state.pressure_mpa, 1e-5),
            (spec.temperature_c, state.temperature_c, 1e-3),
            (spec.enthalpy_kj_kg, state.enthalpy_kj_kg, 1e-2),
            (spec.entropy_kj_kgk, state.entropy_kj_kgk, 1e-4),
            (spec.specific_volume_m3_kg, state.specific_volume_m3_kg, 1e-7),
            (spec.quality, state.quality, 1e-4),
        ]
        for expected, actual, tol in checks:
            if expected is None:
                continue
            if actual is None:
                return False
            if not isclose(float(expected), float(actual), rel_tol=tol, abs_tol=tol):
                return False
        return True

    def _mix_states(self, states: list[ThermoState], weights: list[float | None] | None = None) -> ThermoState:
        """Return a common-pressure mixture state with mass-weighted enthalpy.

        A real mixer cannot gain pressure by averaging inlet pressures. The
        lowest inlet pressure is therefore used as the common outlet pressure;
        any configured mixer pressure drop is applied by the component solver.
        Enthalpy is conserved across the adiabatic mixing step.
        """
        usable_weights = (
            [weight for weight in weights if weight is not None and weight > 0.0]
            if weights is not None
            else []
        )
        if weights is not None and len(usable_weights) == len(states):
            total_weight = sum(usable_weights)
            normalized_weights = [weight / total_weight for weight in usable_weights]
        else:
            normalized_weights = [1.0 / len(states)] * len(states)
        mean_pressure = min(state.pressure_mpa for state in states)
        mean_enthalpy = sum(state.enthalpy_kj_kg * weight for state, weight in zip(states, normalized_weights))
        try:
            return self.backend.state_from_pressure_enthalpy(mean_pressure, mean_enthalpy)
        except Exception:
            return states[0]

    def _state_changed(self, previous: ThermoState | None, current: ThermoState | None) -> bool:
        if previous is None and current is None:
            return False
        if previous is None or current is None:
            return True
        return not self.backend.same_state(previous, current, tolerance=1e-5)

    def _accumulate_metrics(self, solution: CircuitSolution) -> None:
        for result in solution.component_results:
            solution.total_heat_in_kj_kg += max(0.0, result.heat_kj_kg)
            solution.total_heat_out_kj_kg += max(0.0, -result.heat_kj_kg)
            if result.kind == ComponentKind.TURBINE:
                solution.total_turbine_work_kj_kg += max(0.0, result.work_kj_kg)
            if result.kind == ComponentKind.PUMP:
                solution.total_pump_work_kj_kg += max(0.0, result.work_kj_kg)
        solution.net_work_kj_kg = solution.total_turbine_work_kj_kg - solution.total_pump_work_kj_kg
        if solution.total_heat_in_kj_kg > 1e-9:
            solution.thermal_efficiency = solution.net_work_kj_kg / solution.total_heat_in_kj_kg
        if solution.total_turbine_work_kj_kg > 1e-9:
            solution.back_work_ratio = solution.total_pump_work_kj_kg / solution.total_turbine_work_kj_kg

    def _evaluate_closure(self, circuit: Circuit, solution: CircuitSolution) -> None:
        if circuit.start_component_id is None:
            return
        returning_states = [edge.state for edge in circuit.inlet_edges(circuit.components[circuit.start_component_id]) if edge.state is not None]
        if not returning_states:
            return
        loop_return = self._mix_states(returning_states)
        reference_state = None
        start_component = circuit.components.get(circuit.start_component_id)
        if start_component is not None and circuit.inlet_edge(start_component).state is not None:
            reference_state = circuit.inlet_edge(start_component).state
        elif circuit.seed_state is not None:
            reference_state = circuit.seed_state
        else:
            return
        solution.closure_error_h_kj_kg = loop_return.enthalpy_kj_kg - reference_state.enthalpy_kj_kg
        solution.closure_error_p_mpa = loop_return.pressure_mpa - reference_state.pressure_mpa
        if not almost_equal(loop_return.enthalpy_kj_kg, reference_state.enthalpy_kj_kg, tolerance=1e-3):
            solution.messages.append("Loop closure enthalpy mismatch is non-zero.")
        if not almost_equal(loop_return.pressure_mpa, reference_state.pressure_mpa, tolerance=1e-4):
            solution.messages.append("Loop closure pressure mismatch is non-zero.")

    def _evaluate_constraints(self, solution: CircuitSolution) -> None:
        for result in solution.component_results:
            if result.status == "Underconstrained":
                solution.underconstrained_components.append(result.component_name)
            if result.status == "Overconstrained":
                solution.overconstrained_components.append(result.component_name)
            if result.status in {"Unsolved", "Undeterminable"}:
                solution.unsolved_components.append(result.component_name)

        if solution.overconstrained_components:
            solution.system_status = "Overconstrained"
        elif solution.underconstrained_components or solution.unsolved_components:
            solution.system_status = "Underconstrained"
        else:
            solution.system_status = "Well-defined"

    def _evaluate_connectivity(self, circuit: Circuit, solution: CircuitSolution) -> None:
        isolated = [
            component.name
            for component in circuit.components.values()
            if not component.upstream_ids and not component.downstream_ids and component.component_id != circuit.start_component_id
        ]
        if isolated:
            solution.messages.append("Isolated components detected: " + ", ".join(isolated))

    def solve_component(
        self,
        circuit: Circuit,
        component: Component,
        inlet_state: ThermoState | None,
        outlet_state_hint: ThermoState | None,
    ) -> ComponentResult:
        process = component.process_kind
        inlet_edge = circuit.inlet_edge(component)
        outlet_edge = circuit.outlet_edge(component)
        outlet_spec = outlet_edge.spec
        inlet_spec = inlet_edge.spec
        outlet_state: Optional[ThermoState] = None
        solved_inlet: Optional[ThermoState] = inlet_state
        work = 0.0
        heat = 0.0
        status = "Solved"
        notes: list[str] = []

        if inlet_state is None and outlet_state_hint is None:
            raise SolverError(f"Unable to solve component {component.name}: no inlet or outlet state available.")

        if inlet_state is None and outlet_state_hint is not None:
            solved_inlet, outlet_state, work, heat, reverse_note = self._solve_component_reverse(
                component, inlet_spec, outlet_spec, outlet_state_hint
            )
            notes.append(reverse_note)
        elif inlet_state is not None:
            solved_inlet = inlet_state

        if outlet_state is None and solved_inlet is not None:
            if component.kind == ComponentKind.PIPE:
                outlet_state, pipe_note = self._solve_pipe_component(component, solved_inlet, outlet_spec)
                notes.append(pipe_note)
            elif component.kind in {ComponentKind.MIXER, ComponentKind.SPLITTER}:
                outlet_state = self._solve_pass_through_component(component, solved_inlet, outlet_spec)
            elif process == ProcessKind.ISENTROPIC:
                outlet_state, work, heat = self._solve_isentropic_component(component, solved_inlet, inlet_spec, outlet_spec)
            elif process == ProcessKind.ISENTHALPIC:
                outlet_state = self._solve_isenthalpic_component(component, solved_inlet, outlet_spec)
            elif process == ProcessKind.ISOBARIC:
                outlet_state = self._solve_isobaric_component(component, solved_inlet, outlet_spec)
                heat = outlet_state.enthalpy_kj_kg - solved_inlet.enthalpy_kj_kg
            elif process == ProcessKind.ISOCHORIC:
                outlet_state = self._solve_isochoric_component(component, solved_inlet, outlet_spec)
                heat = outlet_state.enthalpy_kj_kg - solved_inlet.enthalpy_kj_kg
            elif process == ProcessKind.ADIABATIC:
                outlet_state = self._solve_adiabatic_component(component, solved_inlet, inlet_spec, outlet_spec)
            elif process == ProcessKind.GENERAL:
                outlet_state = self._solve_general_component(outlet_spec)
                heat = outlet_state.enthalpy_kj_kg - solved_inlet.enthalpy_kj_kg
            else:
                raise SolverError(f"Unsupported process kind: {process}")

        if solved_inlet is None or outlet_state is None:
            raise SolverError(f"Unable to solve component {component.name}.")

        if process == ProcessKind.ISENTROPIC and component.kind == ComponentKind.PUMP:
            work = outlet_state.enthalpy_kj_kg - solved_inlet.enthalpy_kj_kg
        elif process == ProcessKind.ISENTROPIC and component.kind == ComponentKind.TURBINE:
            work = solved_inlet.enthalpy_kj_kg - outlet_state.enthalpy_kj_kg
        elif component.kind == ComponentKind.PUMP and work == 0.0:
            work = outlet_state.enthalpy_kj_kg - solved_inlet.enthalpy_kj_kg
        elif component.kind == ComponentKind.TURBINE and work == 0.0:
            work = solved_inlet.enthalpy_kj_kg - outlet_state.enthalpy_kj_kg

        overdefined_endpoints = (
            process != ProcessKind.GENERAL
            and self._has_state_definition(inlet_spec)
            and self._has_state_definition(outlet_spec)
        )
        if overdefined_endpoints:
            notes.append("Both inlet and outlet states are user-defined for a non-General process.")

        status, message = self._constraint_report(component, inlet_edge, outlet_edge, solved_inlet, outlet_state)
        conflicts = self._fixed_constraint_conflicts(inlet_edge, outlet_edge, solved_inlet, outlet_state)
        if conflicts:
            status = "Overconstrained"
            message = "User-entered fixed constraints conflict with solved state."
        elif overdefined_endpoints:
            status = "Overconstrained"
            message = "Inlet and outlet states are both user-defined for a non-General process."
        notes.append(message)
        if outlet_spec.defined_count() > 0:
            notes.append(f"Outlet target: {outlet_spec.pretty()}")
        if inlet_spec.defined_count() > 0:
            notes.append(f"Inlet target: {inlet_spec.pretty()}")
        return ComponentResult(
            component_id=component.component_id,
            component_name=component.name,
            kind=component.kind,
            process_kind=component.process_kind,
            inlet_state=solved_inlet,
            outlet_state=outlet_state,
            work_kj_kg=work,
            heat_kj_kg=heat,
            status=status,
            conflicting_fields=conflicts,
            message=" | ".join(notes),
        )

    def _solve_component_reverse(
        self,
        component: Component,
        inlet_spec: ThermoSpec,
        outlet_spec: ThermoSpec,
        outlet_state: ThermoState,
    ) -> tuple[ThermoState, ThermoState, float, float, str]:
        process = component.process_kind
        if process == ProcessKind.ISENTHALPIC:
            inlet_state = self._reverse_isenthalpic_component(component, inlet_spec, outlet_spec, outlet_state)
            return inlet_state, outlet_state, 0.0, 0.0, "Solved from outlet state (reverse isenthalpic)."
        if process == ProcessKind.ADIABATIC and component.kind not in {ComponentKind.TURBINE, ComponentKind.PUMP}:
            inlet_state = self._reverse_isenthalpic_component(component, inlet_spec, outlet_spec, outlet_state)
            return inlet_state, outlet_state, 0.0, 0.0, "Solved from outlet state (reverse adiabatic/isenthalpic)."
        if process in {ProcessKind.ISENTROPIC, ProcessKind.ADIABATIC} and component.kind in {
            ComponentKind.TURBINE,
            ComponentKind.PUMP,
        }:
            inlet_state = self._reverse_isentropic_machine(component, inlet_spec, outlet_spec, outlet_state)
            work = inlet_state.enthalpy_kj_kg - outlet_state.enthalpy_kj_kg if component.kind == ComponentKind.TURBINE else outlet_state.enthalpy_kj_kg - inlet_state.enthalpy_kj_kg
            return inlet_state, outlet_state, work, 0.0, "Solved from outlet state (reverse isentropic machine)."
        raise SolverError(
            f"{component.name} cannot be reverse-solved from outlet state only for process {process.value}. "
            "Provide inlet definition or additional process constraints."
        )

    def _reverse_isenthalpic_component(
        self, component: Component, inlet_spec: ThermoSpec, outlet_spec: ThermoSpec, outlet_state: ThermoState
    ) -> ThermoState:
        inlet_pressure = inlet_spec.pressure_mpa
        if inlet_pressure is None:
            if outlet_spec.pressure_drop_mpa is not None:
                inlet_pressure = outlet_state.pressure_mpa + outlet_spec.pressure_drop_mpa
            else:
                inlet_pressure = outlet_state.pressure_mpa
        return self.backend.state_from_pressure_enthalpy(inlet_pressure, outlet_state.enthalpy_kj_kg)

    def _reverse_isentropic_machine(
        self, component: Component, inlet_spec: ThermoSpec, outlet_spec: ThermoSpec, outlet_state: ThermoState
    ) -> ThermoState:
        inlet_pressure = inlet_spec.pressure_mpa
        if inlet_pressure is None:
            raise SolverError(f"{component.name} reverse solve needs inlet pressure.")

        efficiency = outlet_spec.efficiency or inlet_spec.efficiency
        if efficiency is None or efficiency <= 0.0 or efficiency > 1.0:
            raise SolverError(f"{component.name} reverse solve needs efficiency in (0,1].")

        pout = outlet_state.pressure_mpa
        hout = outlet_state.enthalpy_kj_kg

        def residual(h_in: float) -> float:
            inlet_state = self.backend.state_from_pressure_enthalpy(inlet_pressure, h_in)
            ideal_out = self.backend.state_from_pressure_entropy(pout, inlet_state.entropy_kj_kgk)
            if component.kind == ComponentKind.TURBINE:
                predicted = h_in - efficiency * (h_in - ideal_out.enthalpy_kj_kg)
            else:
                predicted = h_in + (ideal_out.enthalpy_kj_kg - h_in) / efficiency
            return predicted - hout

        lo = hout - 2500.0
        hi = hout + 2500.0
        f_lo = residual(lo)
        f_hi = residual(hi)
        if f_lo == 0.0:
            return self.backend.state_from_pressure_enthalpy(inlet_pressure, lo)
        if f_hi == 0.0:
            return self.backend.state_from_pressure_enthalpy(inlet_pressure, hi)
        if f_lo * f_hi > 0.0:
            steps = 80
            prev_h = lo
            prev_f = f_lo
            found = False
            for idx in range(1, steps + 1):
                h = lo + (hi - lo) * idx / steps
                f = residual(h)
                if prev_f == 0.0:
                    return self.backend.state_from_pressure_enthalpy(inlet_pressure, prev_h)
                if f == 0.0:
                    return self.backend.state_from_pressure_enthalpy(inlet_pressure, h)
                if prev_f * f < 0.0:
                    lo, hi = prev_h, h
                    f_lo, f_hi = prev_f, f
                    found = True
                    break
                prev_h, prev_f = h, f
            if not found:
                raise SolverError(f"{component.name} reverse solve could not bracket a valid inlet state.")

        for _ in range(80):
            mid = 0.5 * (lo + hi)
            f_mid = residual(mid)
            if abs(f_mid) < 1e-6:
                return self.backend.state_from_pressure_enthalpy(inlet_pressure, mid)
            if f_lo * f_mid <= 0.0:
                hi = mid
                f_hi = f_mid
            else:
                lo = mid
                f_lo = f_mid
        return self.backend.state_from_pressure_enthalpy(inlet_pressure, 0.5 * (lo + hi))

    def _has_state_definition(self, spec: ThermoSpec) -> bool:
        return len(spec.to_state_spec().defined_fields()) >= 2

    def _fixed_constraint_conflicts(
        self,
        inlet_edge: Edge,
        outlet_edge: Edge,
        inlet_state: ThermoState,
        outlet_state: ThermoState,
    ) -> list[str]:
        tolerances = {
            "pressure_mpa": 1e-5,
            "temperature_c": 1e-3,
            "enthalpy_kj_kg": 1e-2,
            "entropy_kj_kgk": 1e-4,
            "specific_volume_m3_kg": 1e-7,
            "quality": 1e-4,
            "pressure_drop_mpa": 1e-5,
        }
        mapping = {
            "pressure_mpa": "pressure_mpa",
            "temperature_c": "temperature_c",
            "enthalpy_kj_kg": "enthalpy_kj_kg",
            "entropy_kj_kgk": "entropy_kj_kgk",
            "specific_volume_m3_kg": "specific_volume_m3_kg",
            "quality": "quality",
        }
        conflicts: list[str] = []
        for suffix in sorted(inlet_edge.user_input_fields):
            if suffix not in mapping:
                continue
            expected = getattr(inlet_edge.spec, suffix)
            actual = getattr(inlet_state, mapping[suffix])
            if self._is_conflict(expected, actual, tolerances[suffix]):
                conflicts.append(f"inlet_{suffix}")
        for suffix in sorted(outlet_edge.user_input_fields):
            if suffix == "pressure_drop_mpa":
                expected = outlet_edge.spec.pressure_drop_mpa
                actual = max(0.0, inlet_state.pressure_mpa - outlet_state.pressure_mpa)
                if self._is_conflict(expected, actual, tolerances["pressure_drop_mpa"]):
                    conflicts.append("pressure_drop_mpa")
                continue
            if suffix not in mapping:
                continue
            expected = getattr(outlet_edge.spec, suffix)
            actual = getattr(outlet_state, mapping[suffix])
            if self._is_conflict(expected, actual, tolerances[suffix]):
                conflicts.append(f"outlet_{suffix}")
        return conflicts

    def _is_conflict(self, expected: float | None, actual: float | None, tolerance: float) -> bool:
        if expected is None:
            return False
        if actual is None:
            return True
        return not isclose(float(expected), float(actual), rel_tol=tolerance, abs_tol=tolerance)

    def _solve_pipe_component(self, component: Component, inlet_state: ThermoState, spec: ThermoSpec) -> tuple[ThermoState, str]:
        mass_flow = spec.mass_flow_kg_s
        length_m = spec.pipe_length_m
        outer_diameter_m = spec.pipe_outer_diameter_m
        wall_thickness_m = spec.pipe_wall_thickness_m
        roughness_m = spec.pipe_roughness_m or 4.5e-5
        elevation_change_m = spec.elevation_change_m or 0.0
        local_loss = spec.local_loss_coefficient or 0.0

        if mass_flow is None or mass_flow <= 0.0:
            raise SolverError(f"{component.name} needs a positive mass flow for pipe loss calculations.")
        if length_m is None or length_m < 0.0:
            raise SolverError(f"{component.name} needs a non-negative pipe length.")
        if outer_diameter_m is None or wall_thickness_m is None:
            raise SolverError(f"{component.name} needs OD and wall thickness.")

        inner_diameter_m = outer_diameter_m - 2.0 * wall_thickness_m
        if inner_diameter_m <= 0.0:
            raise SolverError(f"{component.name} has invalid geometry; ID must be positive.")

        area_m2 = pi * inner_diameter_m ** 2 / 4.0
        rho_in = max(inlet_state.density_kg_m3, 1e-6)
        velocity_in = mass_flow / (rho_in * area_m2)
        mu = inlet_state.dynamic_viscosity_pa_s if inlet_state.dynamic_viscosity_pa_s and inlet_state.dynamic_viscosity_pa_s > 0.0 else 1e-3
        reynolds = max(rho_in * velocity_in * inner_diameter_m / mu, 1.0)

        if reynolds < 2300.0:
            friction_factor = 64.0 / reynolds
        else:
            relative_roughness = max(roughness_m / inner_diameter_m, 1e-12)
            friction_factor = 0.25 / (log10(relative_roughness / 3.7 + 5.74 / (reynolds ** 0.9)) ** 2)

        dp_friction_pa = friction_factor * (length_m / inner_diameter_m) * 0.5 * rho_in * velocity_in ** 2
        dp_local_pa = local_loss * 0.5 * rho_in * velocity_in ** 2
        dp_static_pa = rho_in * 9.81 * elevation_change_m
        dp_total_pa = dp_friction_pa + dp_local_pa + dp_static_pa
        dp_total_mpa = dp_total_pa / 1_000_000.0

        if spec.pressure_drop_mpa is not None:
            dp_total_mpa = spec.pressure_drop_mpa
        target_pressure = spec.pressure_mpa if spec.pressure_mpa is not None else inlet_state.pressure_mpa - dp_total_mpa
        if target_pressure <= 0.0001:
            target_pressure = 0.0001

        outlet_state = self.backend.state_from_pressure_enthalpy(target_pressure, inlet_state.enthalpy_kj_kg)
        rho_out = max(outlet_state.density_kg_m3, 1e-6)
        velocity_out = mass_flow / (rho_out * area_m2)

        note = (
            f"Pipe hydraulics: ID={inner_diameter_m:.4f} m, Re={reynolds:.1f}, f={friction_factor:.4f}, "
            f"v_in={velocity_in:.3f} m/s, v_out={velocity_out:.3f} m/s, dP={dp_total_mpa:.5f} MPa"
        )
        return outlet_state, note

    def _solve_pass_through_component(self, component: Component, inlet_state: ThermoState, outlet_spec: ThermoSpec) -> ThermoState:
        target_pressure = outlet_spec.pressure_mpa
        pressure_drop = outlet_spec.pressure_drop_mpa
        if target_pressure is None and pressure_drop is not None:
            target_pressure = inlet_state.pressure_mpa - pressure_drop
        if target_pressure is None or abs(target_pressure - inlet_state.pressure_mpa) < 1e-9:
            return inlet_state
        return self.backend.state_from_pressure_enthalpy(target_pressure, inlet_state.enthalpy_kj_kg)

    def _solve_isentropic_component(
        self, component: Component, inlet_state: ThermoState, inlet_spec: ThermoSpec, outlet_spec: ThermoSpec
    ) -> tuple[ThermoState, float, float]:
        target_pressure = outlet_spec.pressure_mpa or inlet_spec.pressure_mpa or inlet_state.pressure_mpa
        if target_pressure is None:
            raise SolverError(f"{component.name} needs an outlet pressure for an isentropic solve.")

        efficiency = outlet_spec.efficiency or inlet_spec.efficiency or 1.0
        if efficiency <= 0.0 or efficiency > 1.0:
            raise SolverError(f"{component.name} has invalid efficiency {efficiency}.")

        ideal = self.backend.state_from_pressure_entropy(target_pressure, inlet_state.entropy_kj_kgk)
        if component.kind == ComponentKind.TURBINE:
            actual_h = inlet_state.enthalpy_kj_kg - efficiency * (inlet_state.enthalpy_kj_kg - ideal.enthalpy_kj_kg)
            actual = self.backend.state_from_pressure_enthalpy(target_pressure, actual_h)
            return actual, inlet_state.enthalpy_kj_kg - actual.enthalpy_kj_kg, 0.0
        if component.kind == ComponentKind.PUMP:
            actual_h = inlet_state.enthalpy_kj_kg + (ideal.enthalpy_kj_kg - inlet_state.enthalpy_kj_kg) / efficiency
            actual = self.backend.state_from_pressure_enthalpy(target_pressure, actual_h)
            return actual, actual.enthalpy_kj_kg - inlet_state.enthalpy_kj_kg, 0.0

        actual = ideal
        return actual, 0.0, 0.0

    def _solve_isenthalpic_component(self, component: Component, inlet_state: ThermoState, outlet_spec: ThermoSpec) -> ThermoState:
        target_pressure = outlet_spec.pressure_mpa or inlet_state.pressure_mpa
        if target_pressure is None:
            raise SolverError(f"{component.name} needs an outlet pressure for an isenthalpic solve.")
        return self.backend.state_from_pressure_enthalpy(target_pressure, inlet_state.enthalpy_kj_kg)

    def _solve_isobaric_component(self, component: Component, inlet_state: ThermoState, outlet_spec: ThermoSpec) -> ThermoState:
        target_pressure = outlet_spec.pressure_mpa or inlet_state.pressure_mpa
        if target_pressure is None:
            raise SolverError(f"{component.name} needs a pressure for an isobaric solve.")
        spec = outlet_spec.to_state_spec()
        spec.pressure_mpa = target_pressure
        if spec.temperature_c is None and spec.enthalpy_kj_kg is None and spec.entropy_kj_kgk is None and spec.quality is None:
            raise SolverError(f"{component.name} is underconstrained: add outlet T, h, s, or x.")
        return self.backend.make_state(spec)

    def _solve_isochoric_component(self, component: Component, inlet_state: ThermoState, outlet_spec: ThermoSpec) -> ThermoState:
        target_pressure = outlet_spec.pressure_mpa or inlet_state.pressure_mpa
        if target_pressure is None:
            raise SolverError(f"{component.name} needs an outlet pressure for an isochoric solve.")
        target_volume = outlet_spec.specific_volume_m3_kg or inlet_state.specific_volume_m3_kg
        if target_volume is None:
            raise SolverError(f"{component.name} needs a specific volume to preserve for an isochoric solve.")

        lower_c = 0.0
        upper_c = 800.0
        lower = self.backend.state_from_pressure_temperature(target_pressure, lower_c)
        upper = self.backend.state_from_pressure_temperature(target_pressure, upper_c)
        lower_error = lower.specific_volume_m3_kg - target_volume
        upper_error = upper.specific_volume_m3_kg - target_volume
        if lower_error == 0.0:
            return lower
        if upper_error == 0.0:
            return upper
        if lower_error * upper_error > 0.0:
            raise SolverError(f"{component.name} cannot bracket an isochoric solution at {target_pressure:.4f} MPa.")

        for _ in range(60):
            midpoint = 0.5 * (lower_c + upper_c)
            candidate = self.backend.state_from_pressure_temperature(target_pressure, midpoint)
            error = candidate.specific_volume_m3_kg - target_volume
            if abs(error) < 1e-8:
                return candidate
            if error * lower_error > 0.0:
                lower_c = midpoint
                lower = candidate
                lower_error = error
            else:
                upper_c = midpoint
                upper = candidate
                upper_error = error
        return candidate

    def _solve_adiabatic_component(
        self, component: Component, inlet_state: ThermoState, inlet_spec: ThermoSpec, outlet_spec: ThermoSpec
    ) -> ThermoState:
        if component.kind in {ComponentKind.TURBINE, ComponentKind.PUMP}:
            return self._solve_isentropic_component(component, inlet_state, inlet_spec, outlet_spec)[0]
        return self._solve_isenthalpic_component(component, inlet_state, outlet_spec)

    def _solve_general_component(self, outlet_spec: ThermoSpec) -> ThermoState:
        spec = outlet_spec.to_state_spec()
        if spec.is_empty():
            raise SolverError("General process requires a fully defined outlet state.")
        return self.backend.make_state(spec)

    def _constraint_report(
        self, component: Component, inlet_edge: Edge, outlet_edge: Edge, inlet_state: ThermoState, outlet_state: ThermoState
    ) -> tuple[str, str]:
        inlet_spec = inlet_edge.spec
        outlet_spec = outlet_edge.spec
        outlet_defined = outlet_spec.defined_count()
        if component.kind in {ComponentKind.MIXER, ComponentKind.SPLITTER} and outlet_defined == 0:
            return "Solved", f"{component.name} passes through mixed state from graph connectivity."
        if component.kind == ComponentKind.PIPE:
            required = (
                outlet_spec.mass_flow_kg_s,
                outlet_spec.pipe_length_m,
                outlet_spec.pipe_outer_diameter_m,
                outlet_spec.pipe_wall_thickness_m,
            )
            if any(value is None for value in required):
                return "Underconstrained", f"{component.name} requires mass flow, length, OD, and wall thickness."
            return "Solved", f"{component.name} solved with hydraulic pressure-loss model."
        if outlet_defined == 0 and component.process_kind in {ProcessKind.ISOBARIC, ProcessKind.ISOCHORIC, ProcessKind.GENERAL}:
            return "Underconstrained", f"{component.name} needs at least one outlet target property."

        if component.kind == ComponentKind.TURBINE:
            efficiency = outlet_spec.efficiency or inlet_spec.efficiency
            if efficiency is None:
                return "Underconstrained", f"{component.name} needs an efficiency to compute actual work."
        if component.kind == ComponentKind.PUMP:
            efficiency = outlet_spec.efficiency or inlet_spec.efficiency
            if efficiency is None:
                return "Underconstrained", f"{component.name} needs an efficiency to compute actual work."

        temp_is_user = "temperature_c" in outlet_edge.user_input_fields
        h_is_user = "enthalpy_kj_kg" in outlet_edge.user_input_fields
        if temp_is_user and h_is_user and outlet_spec.temperature_c is not None and outlet_spec.enthalpy_kj_kg is not None:
            if not isclose(outlet_state.temperature_c, outlet_spec.temperature_c, abs_tol=1e-2):
                return "Overconstrained", f"{component.name} outlet temperature conflicts with other outlet targets."
            if not isclose(outlet_state.enthalpy_kj_kg, outlet_spec.enthalpy_kj_kg, abs_tol=1e-2):
                return "Overconstrained", f"{component.name} outlet enthalpy conflicts with other outlet targets."
        return "Solved", f"{component.name} solved successfully."


def solve_circuit(circuit: Circuit, backend: SteamPropertyBackend | None = None) -> CircuitSolution:
    return ThermoSolver(backend).solve_circuit(circuit)


def analyze_constraint_system(circuit: Circuit) -> ConstraintDiagnostics:
    diagnostics = ConstraintDiagnostics()
    if not circuit.components:
        diagnostics.system_status = "Underconstrained"
        diagnostics.propagation_hint = "Add components and constraints to begin solving."
        return diagnostics

    order = circuit.traversal_order(circuit.start_component_id)
    if not order:
        diagnostics.system_status = "Underconstrained"
        diagnostics.propagation_hint = "No traversal path available from the current start component."
        return diagnostics

    start_id = circuit.start_component_id
    has_seed = circuit.seed_state is not None
    outlet_available: set[str] = set()

    changed = True
    while changed:
        changed = False
        for component in order:
            inlet_available = _diagnostic_inlet_available(circuit, component, outlet_available, start_id, has_seed)
            missing_fields = _diagnostic_missing_fields(circuit, component, inlet_available)
            is_over, _ = _diagnostic_overconstraint_flags(circuit, component)
            if inlet_available and not missing_fields and not is_over:
                if component.component_id not in outlet_available:
                    outlet_available.add(component.component_id)
                    changed = True

    total_missing = 0
    frontier_missing_counts: list[int] = []
    component_diags: list[ComponentConstraintDiagnostic] = []
    for component in order:
        inlet_available = _diagnostic_inlet_available(circuit, component, outlet_available, start_id, has_seed)
        missing_fields = _diagnostic_missing_fields(circuit, component, inlet_available)
        is_over, over_messages = _diagnostic_overconstraint_flags(circuit, component)

        if is_over:
            status = "Overconstrained"
            message = over_messages[0]
            diagnostics.overconstrained_components.append(component.name)
        elif component.component_id in outlet_available:
            status = "Well-defined"
            message = "Sufficient user constraints and upstream state are available."
        elif inlet_available:
            status = "Underconstrained"
            total_missing += len(missing_fields)
            if missing_fields:
                frontier_missing_counts.append(len(missing_fields))
            diagnostics.underconstrained_components.append(component.name)
            pretty_missing = ", ".join(missing_fields) if missing_fields else "additional process inputs"
            message = f"Needs {len(missing_fields)} more input(s): {pretty_missing}."
        else:
            status = "Blocked"
            diagnostics.blocked_components.append(component.name)
            message = "Cannot be solved yet because upstream state is unresolved."

        component_diags.append(
            ComponentConstraintDiagnostic(
                component_id=component.component_id,
                component_name=component.name,
                status=status,
                message=message,
                inlet_available=inlet_available,
                additional_info_required=len(missing_fields),
                missing_fields=missing_fields,
            )
        )

    diagnostics.component_diagnostics = component_diags
    diagnostics.total_additional_info_required = total_missing
    diagnostics.frontier_min_additional_info = min(frontier_missing_counts) if frontier_missing_counts else None

    if diagnostics.overconstrained_components:
        diagnostics.system_status = "Overconstrained"
    elif diagnostics.underconstrained_components or diagnostics.blocked_components:
        diagnostics.system_status = "Underconstrained"
    else:
        diagnostics.system_status = "Well-defined"

    if diagnostics.system_status == "Underconstrained" and diagnostics.frontier_min_additional_info == 1:
        diagnostics.propagation_hint = (
            "At least one upstream-ready component needs only 1 more user input; "
            "adding it may allow the full solution to propagate."
        )

    return diagnostics


def _diagnostic_inlet_available(
    circuit: Circuit,
    component: Component,
    outlet_available: set[str],
    start_id: str | None,
    has_seed: bool,
) -> bool:
    if component.component_id == start_id and has_seed:
        return True
    return any(upstream_id in outlet_available for upstream_id in circuit.incoming(component.component_id))


def _diagnostic_missing_fields(circuit: Circuit, component: Component, inlet_available: bool) -> list[str]:
    if not inlet_available:
        return []

    user = _scoped_user_fields(circuit, component)
    process = component.process_kind

    if component.kind in {ComponentKind.MIXER, ComponentKind.SPLITTER}:
        return []

    if component.kind == ComponentKind.PIPE:
        required = [
            "mass_flow_kg_s",
            "pipe_length_m",
            "pipe_outer_diameter_m",
            "pipe_wall_thickness_m",
        ]
        return [field for field in required if field not in user and f"outlet_{field}" not in user]

    if process == ProcessKind.ISOBARIC:
        options = [
            "outlet_temperature_c",
            "outlet_enthalpy_kj_kg",
            "outlet_entropy_kj_kgk",
            "outlet_quality",
        ]
        return ["one of: outlet_temperature / outlet_enthalpy / outlet_entropy / outlet_quality"] if not any(
            key in user for key in options
        ) else []

    if process == ProcessKind.GENERAL:
        state_keys = [
            "outlet_pressure_mpa",
            "outlet_temperature_c",
            "outlet_enthalpy_kj_kg",
            "outlet_entropy_kj_kgk",
            "outlet_quality",
            "outlet_specific_volume_m3_kg",
        ]
        count = sum(1 for key in state_keys if key in user)
        need = max(0, 2 - count)
        return ["additional outlet state property"] * need

    if process in {ProcessKind.ISENTROPIC, ProcessKind.ADIABATIC} and component.kind in {
        ComponentKind.TURBINE,
        ComponentKind.PUMP,
    }:
        missing: list[str] = []
        if "outlet_pressure_mpa" not in user and "pressure_drop_mpa" not in user and "outlet_pressure_drop_mpa" not in user:
            missing.append("outlet_pressure or pressure_drop")
        if "outlet_efficiency" not in user and "inlet_efficiency" not in user:
            missing.append("efficiency")
        return missing

    if process == ProcessKind.ISOCHORIC:
        if "outlet_pressure_mpa" not in user and "pressure_drop_mpa" not in user and "outlet_pressure_drop_mpa" not in user:
            return ["outlet_pressure or pressure_drop"]

    return []


def _diagnostic_overconstraint_flags(circuit: Circuit, component: Component) -> tuple[bool, list[str]]:
    user = _scoped_user_fields(circuit, component)
    process = component.process_kind
    messages: list[str] = []

    inlet_state_keys = [
        "inlet_pressure_mpa",
        "inlet_temperature_c",
        "inlet_enthalpy_kj_kg",
        "inlet_entropy_kj_kgk",
        "inlet_quality",
        "inlet_specific_volume_m3_kg",
    ]
    outlet_state_keys = [
        "outlet_pressure_mpa",
        "outlet_temperature_c",
        "outlet_enthalpy_kj_kg",
        "outlet_entropy_kj_kgk",
        "outlet_quality",
        "outlet_specific_volume_m3_kg",
    ]
    inlet_count = sum(1 for key in inlet_state_keys if key in user)
    outlet_count = sum(1 for key in outlet_state_keys if key in user)
    if process != ProcessKind.GENERAL and inlet_count >= 2 and outlet_count >= 2:
        messages.append("Both inlet and outlet states are fully user-defined for a non-General process.")

    state_keys = [
        "outlet_pressure_mpa",
        "outlet_temperature_c",
        "outlet_enthalpy_kj_kg",
        "outlet_entropy_kj_kgk",
        "outlet_quality",
        "outlet_specific_volume_m3_kg",
    ]
    user_state_count = sum(1 for key in state_keys if key in user)

    if process == ProcessKind.ISOBARIC and user_state_count > 2:
        messages.append("Too many outlet state targets for an isobaric component.")
    if process == ProcessKind.GENERAL and user_state_count > 2:
        messages.append("General process may be overconstrained with more than two outlet state targets.")
    if process == ProcessKind.ISENTROPIC and component.kind in {ComponentKind.TURBINE, ComponentKind.PUMP}:
        non_pressure_state = [
            "outlet_temperature_c",
            "outlet_enthalpy_kj_kg",
            "outlet_entropy_kj_kgk",
            "outlet_quality",
            "outlet_specific_volume_m3_kg",
        ]
        if sum(1 for key in non_pressure_state if key in user) > 1:
            messages.append("Multiple outlet state targets may overconstrain this isentropic machine.")
    if "outlet_pressure_mpa" in user and ("pressure_drop_mpa" in user or "outlet_pressure_drop_mpa" in user):
        messages.append("Both outlet pressure and pressure drop are fixed.")

    return (len(messages) > 0, messages)
