from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose, log10, pi
from typing import Optional

from .model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec
from .thermo import SteamPropertyBackend, ThermoState
from .units import almost_equal


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

        for component in circuit.components.values():
            component.reset_results()

        solution = CircuitSolution()
        order = circuit.traversal_order(circuit.start_component_id)
        if not order:
            raise SolverError("Circuit has no components to solve.")

        results_by_id: dict[str, ComponentResult] = {}
        for _ in range(20):
            changed = False
            for component in order:
                inlet_state = self._resolve_inlet_state(circuit, component)
                if inlet_state is None:
                    continue
                previous_inlet = component.inlet_state
                previous_outlet = component.outlet_state
                result = self.solve_component(component, inlet_state)
                component.inlet_state = result.inlet_state
                component.outlet_state = result.outlet_state
                component.report = result.message
                results_by_id[component.component_id] = result
                if self._state_changed(previous_inlet, component.inlet_state) or self._state_changed(previous_outlet, component.outlet_state):
                    changed = True
            if not changed:
                break

        for component in order:
            result = results_by_id.get(component.component_id)
            if result is None:
                result = ComponentResult(
                    component_id=component.component_id,
                    component_name=component.name,
                    kind=component.kind,
                    process_kind=component.process_kind,
                    inlet_state=component.inlet_state,
                    outlet_state=component.outlet_state,
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

    def _resolve_inlet_state(self, circuit: Circuit, component: Component) -> ThermoState | None:
        upstream_states: list[ThermoState] = []
        for upstream_id in circuit.incoming(component.component_id):
            upstream = circuit.components.get(upstream_id)
            if upstream and upstream.outlet_state is not None:
                upstream_states.append(upstream.outlet_state)
        if not upstream_states:
            if component.component_id == circuit.start_component_id and circuit.seed_state is not None:
                return circuit.seed_state
            return None
        if len(upstream_states) == 1:
            return upstream_states[0]
        return self._mix_states(upstream_states)

    def _mix_states(self, states: list[ThermoState]) -> ThermoState:
        mean_pressure = sum(state.pressure_mpa for state in states) / len(states)
        mean_enthalpy = sum(state.enthalpy_kj_kg for state in states) / len(states)
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
        returning_states: list[ThermoState] = []
        for upstream_id in circuit.incoming(circuit.start_component_id):
            upstream = circuit.components.get(upstream_id)
            if upstream and upstream.outlet_state is not None:
                returning_states.append(upstream.outlet_state)
        if not returning_states:
            return
        loop_return = self._mix_states(returning_states)
        reference_state = None
        start_component = circuit.components.get(circuit.start_component_id)
        if start_component is not None and start_component.inlet_state is not None:
            reference_state = start_component.inlet_state
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

    def solve_component(self, component: Component, inlet_state: ThermoState) -> ComponentResult:
        process = component.process_kind
        outlet_spec = component.outlet_spec
        inlet_spec = component.inlet_spec
        outlet_state: Optional[ThermoState] = None
        work = 0.0
        heat = 0.0
        status = "Solved"
        notes: list[str] = []

        if component.kind == ComponentKind.PIPE:
            outlet_state, pipe_note = self._solve_pipe_component(component, inlet_state)
            notes.append(pipe_note)
        elif component.kind in {ComponentKind.MIXER, ComponentKind.SPLITTER}:
            outlet_state = self._solve_pass_through_component(component, inlet_state)
        elif process == ProcessKind.ISENTROPIC:
            outlet_state, work, heat = self._solve_isentropic_component(component, inlet_state)
        elif process == ProcessKind.ISENTHALPIC:
            outlet_state = self._solve_isenthalpic_component(component, inlet_state, outlet_spec)
        elif process == ProcessKind.ISOBARIC:
            outlet_state = self._solve_isobaric_component(component, inlet_state, outlet_spec)
            heat = outlet_state.enthalpy_kj_kg - inlet_state.enthalpy_kj_kg
        elif process == ProcessKind.ISOCHORIC:
            outlet_state = self._solve_isochoric_component(component, inlet_state, outlet_spec)
            heat = outlet_state.enthalpy_kj_kg - inlet_state.enthalpy_kj_kg
        elif process == ProcessKind.ADIABATIC:
            outlet_state = self._solve_adiabatic_component(component, inlet_state, outlet_spec)
        elif process == ProcessKind.GENERAL:
            outlet_state = self._solve_general_component(outlet_spec)
            heat = outlet_state.enthalpy_kj_kg - inlet_state.enthalpy_kj_kg
        else:
            raise SolverError(f"Unsupported process kind: {process}")

        if outlet_state is None:
            raise SolverError(f"Unable to solve component {component.name}.")

        if process == ProcessKind.ISENTROPIC and component.kind == ComponentKind.PUMP:
            work = outlet_state.enthalpy_kj_kg - inlet_state.enthalpy_kj_kg
        elif process == ProcessKind.ISENTROPIC and component.kind == ComponentKind.TURBINE:
            work = inlet_state.enthalpy_kj_kg - outlet_state.enthalpy_kj_kg
        elif component.kind == ComponentKind.PUMP and work == 0.0:
            work = outlet_state.enthalpy_kj_kg - inlet_state.enthalpy_kj_kg
        elif component.kind == ComponentKind.TURBINE and work == 0.0:
            work = inlet_state.enthalpy_kj_kg - outlet_state.enthalpy_kj_kg

        status, message = self._constraint_report(component, inlet_state, outlet_state)
        conflicts = self._fixed_constraint_conflicts(component, inlet_state, outlet_state)
        if conflicts:
            status = "Overconstrained"
            message = "User-entered fixed constraints conflict with solved state."
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
            inlet_state=inlet_state,
            outlet_state=outlet_state,
            work_kj_kg=work,
            heat_kj_kg=heat,
            status=status,
            conflicting_fields=conflicts,
            message=" | ".join(notes),
        )

    def _fixed_constraint_conflicts(
        self,
        component: Component,
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
        for field_name in sorted(component.user_input_fields):
            if field_name.startswith("inlet_"):
                suffix = field_name.replace("inlet_", "", 1)
                if suffix not in mapping:
                    continue
                expected = getattr(component.inlet_spec, suffix)
                actual = getattr(inlet_state, mapping[suffix])
                if self._is_conflict(expected, actual, tolerances[suffix]):
                    conflicts.append(field_name)
            elif field_name.startswith("outlet_"):
                suffix = field_name.replace("outlet_", "", 1)
                if suffix not in mapping:
                    continue
                expected = getattr(component.outlet_spec, suffix)
                actual = getattr(outlet_state, mapping[suffix])
                if self._is_conflict(expected, actual, tolerances[suffix]):
                    conflicts.append(field_name)
            elif field_name == "pressure_drop_mpa":
                expected = component.outlet_spec.pressure_drop_mpa
                actual = max(0.0, inlet_state.pressure_mpa - outlet_state.pressure_mpa)
                if self._is_conflict(expected, actual, tolerances["pressure_drop_mpa"]):
                    conflicts.append(field_name)
        return conflicts

    def _is_conflict(self, expected: float | None, actual: float | None, tolerance: float) -> bool:
        if expected is None:
            return False
        if actual is None:
            return True
        return not isclose(float(expected), float(actual), rel_tol=tolerance, abs_tol=tolerance)

    def _solve_pipe_component(self, component: Component, inlet_state: ThermoState) -> tuple[ThermoState, str]:
        spec = component.outlet_spec
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

    def _solve_pass_through_component(self, component: Component, inlet_state: ThermoState) -> ThermoState:
        target_pressure = component.outlet_spec.pressure_mpa
        pressure_drop = component.outlet_spec.pressure_drop_mpa
        if target_pressure is None and pressure_drop is not None:
            target_pressure = inlet_state.pressure_mpa - pressure_drop
        if target_pressure is None or abs(target_pressure - inlet_state.pressure_mpa) < 1e-9:
            return inlet_state
        return self.backend.state_from_pressure_enthalpy(target_pressure, inlet_state.enthalpy_kj_kg)

    def _solve_isentropic_component(self, component: Component, inlet_state: ThermoState) -> tuple[ThermoState, float, float]:
        target_pressure = component.outlet_spec.pressure_mpa or component.inlet_spec.pressure_mpa or inlet_state.pressure_mpa
        if target_pressure is None:
            raise SolverError(f"{component.name} needs an outlet pressure for an isentropic solve.")

        efficiency = component.outlet_spec.efficiency or component.inlet_spec.efficiency or 1.0
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

    def _solve_adiabatic_component(self, component: Component, inlet_state: ThermoState, outlet_spec: ThermoSpec) -> ThermoState:
        if component.kind in {ComponentKind.TURBINE, ComponentKind.PUMP}:
            return self._solve_isentropic_component(component, inlet_state)[0]
        return self._solve_isenthalpic_component(component, inlet_state, outlet_spec)

    def _solve_general_component(self, outlet_spec: ThermoSpec) -> ThermoState:
        spec = outlet_spec.to_state_spec()
        if spec.is_empty():
            raise SolverError("General process requires a fully defined outlet state.")
        return self.backend.make_state(spec)

    def _constraint_report(self, component: Component, inlet_state: ThermoState, outlet_state: ThermoState) -> tuple[str, str]:
        outlet_defined = component.outlet_spec.defined_count()
        if component.kind in {ComponentKind.MIXER, ComponentKind.SPLITTER} and outlet_defined == 0:
            return "Solved", f"{component.name} passes through mixed state from graph connectivity."
        if component.kind == ComponentKind.PIPE:
            required = (
                component.outlet_spec.mass_flow_kg_s,
                component.outlet_spec.pipe_length_m,
                component.outlet_spec.pipe_outer_diameter_m,
                component.outlet_spec.pipe_wall_thickness_m,
            )
            if any(value is None for value in required):
                return "Underconstrained", f"{component.name} requires mass flow, length, OD, and wall thickness."
            return "Solved", f"{component.name} solved with hydraulic pressure-loss model."
        if outlet_defined == 0 and component.process_kind in {ProcessKind.ISOBARIC, ProcessKind.ISOCHORIC, ProcessKind.GENERAL}:
            return "Underconstrained", f"{component.name} needs at least one outlet target property."

        if component.kind == ComponentKind.TURBINE:
            efficiency = component.outlet_spec.efficiency or component.inlet_spec.efficiency
            if efficiency is None:
                return "Underconstrained", f"{component.name} needs an efficiency to compute actual work."
        if component.kind == ComponentKind.PUMP:
            efficiency = component.outlet_spec.efficiency or component.inlet_spec.efficiency
            if efficiency is None:
                return "Underconstrained", f"{component.name} needs an efficiency to compute actual work."

        temp_is_user = "outlet_temperature_c" in component.user_input_fields
        h_is_user = "outlet_enthalpy_kj_kg" in component.user_input_fields
        if temp_is_user and h_is_user and component.outlet_spec.temperature_c is not None and component.outlet_spec.enthalpy_kj_kg is not None:
            if not isclose(outlet_state.temperature_c, component.outlet_spec.temperature_c, abs_tol=1e-2):
                return "Overconstrained", f"{component.name} outlet temperature conflicts with other outlet targets."
            if not isclose(outlet_state.enthalpy_kj_kg, component.outlet_spec.enthalpy_kj_kg, abs_tol=1e-2):
                return "Overconstrained", f"{component.name} outlet enthalpy conflicts with other outlet targets."
        return "Solved", f"{component.name} solved successfully."


def solve_circuit(circuit: Circuit, backend: SteamPropertyBackend | None = None) -> CircuitSolution:
    return ThermoSolver(backend).solve_circuit(circuit)
