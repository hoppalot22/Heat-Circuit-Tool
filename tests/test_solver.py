"""Tests for the circuit solver, including physics validation."""

import pytest
from heat_circuit_tool.model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec
from heat_circuit_tool.solver import (
    CircuitSolution,
    ComponentResult,
    SolverError,
    analyze_constraint_system,
    solve_circuit,
)
from heat_circuit_tool.thermo import SteamPropertyBackend
from heat_circuit_tool.demo import build_reheat_rankine_demo


backend = SteamPropertyBackend()


# ── Demo Rankine cycle ──────────────────────────────────────────────────


class TestReheatRankineDemo:
    """Validate the demo circuit solves to expected values."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.circuit = build_reheat_rankine_demo()
        self.solution = solve_circuit(self.circuit)

    def test_demo_solves_well_defined(self):
        assert self.solution.system_status == "Well-defined"

    def test_demo_thermal_efficiency(self):
        # Known value from verified run: ~38.96%
        eff = self.solution.thermal_efficiency
        assert eff is not None
        assert 0.38 <= eff <= 0.40

    def test_demo_net_work_positive(self):
        assert self.solution.net_work_kj_kg > 1400.0

    def test_demo_pump_work(self):
        # Known: ~17.76 kJ/kg
        assert 15.0 <= self.solution.total_pump_work_kj_kg <= 20.0

    def test_demo_turbine_work(self):
        # Known: HP ~403, LP ~1072, total ~1475
        assert self.solution.total_turbine_work_kj_kg > 1400.0

    def test_demo_heat_in(self):
        # Known: boiler ~3214, reheater ~527, total ~3741
        assert self.solution.total_heat_in_kj_kg > 3500.0

    def test_demo_heat_out(self):
        # Known: condenser ~2283
        assert self.solution.total_heat_out_kj_kg > 2000.0

    def test_demo_no_errors(self):
        assert len(self.solution.underconstrained_components) == 0
        assert len(self.solution.overconstrained_components) == 0
        assert len(self.solution.unsolved_components) == 0

    def test_demo_has_all_results(self):
        assert len(self.solution.component_results) == len(self.circuit.components)

    def test_demo_component_statuses(self):
        for result in self.solution.component_results:
            assert result.status == "Solved", f"{result.component_name}: {result.status}"


# ── Simple component physics ────────────────────────────────────────────


class TestIsentropicTurbine:
    """Validate isentropic turbine expansion calculations."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.circuit = Circuit()
        self.circuit.seed_state = backend.state_from_pressure_temperature(15.0, 540.0)
        self.circuit.seed_description = "Boiler outlet"
        turbine = Component(
            component_id="T1",
            kind=ComponentKind.TURBINE,
            process_kind=ProcessKind.ISENTROPIC,
            name="HP Turbine",
            outlet_spec=ThermoSpec(pressure_mpa=3.0, efficiency=0.88),
        )
        self.circuit.add_component(turbine)
        self.circuit.start_component_id = "T1"
        self.solution = solve_circuit(self.circuit)
        self.result = self.solution.component_results[0]

    def test_turbine_solves(self):
        assert self.result.status == "Solved"

    def test_turbine_outlet_enthalpy(self):
        # Known from iapws: ~3020 kJ/kg for 15MPa/540C → 3MPa with eff=0.88
        h_out = self.result.outlet_state.enthalpy_kj_kg if self.result.outlet_state else None
        assert h_out is not None
        assert 2900 <= h_out <= 3100

    def test_turbine_work(self):
        # Work = h_in - h_out
        assert self.result.work_kj_kg > 300
        assert self.result.work_kj_kg < 600


class TestIsentropicPump:
    """Validate isentropic pump compression."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.circuit = Circuit()
        self.circuit.seed_state = backend.state_from_pressure_quality(0.01, 0.0)
        self.circuit.seed_description = "Condenser outlet / saturated liquid"
        pump = Component(
            component_id="P1",
            kind=ComponentKind.PUMP,
            process_kind=ProcessKind.ISENTROPIC,
            name="Feed Pump",
            outlet_spec=ThermoSpec(pressure_mpa=15.0, efficiency=0.85),
        )
        self.circuit.add_component(pump)
        self.circuit.start_component_id = "P1"
        self.solution = solve_circuit(self.circuit)
        self.result = self.solution.component_results[0]

    def test_pump_solves(self):
        assert self.result.status == "Solved"

    def test_pump_outlet_enthalpy(self):
        h_out = self.result.outlet_state.enthalpy_kj_kg if self.result.outlet_state else None
        assert h_out is not None
        assert 180 <= h_out <= 250  # subcooled liquid at 15MPa

    def test_pump_work(self):
        assert self.result.work_kj_kg > 0
        assert self.result.work_kj_kg < 50  # small relative to turbine


class TestIsenthalpicValve:
    """Validate isenthalpic (constant enthalpy) valve."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.circuit = Circuit()
        self.circuit.seed_state = backend.state_from_pressure_temperature(15.0, 300.0)
        self.circuit.seed_description = "Hot high-pressure water"
        valve = Component(
            component_id="V1",
            kind=ComponentKind.VALVE,
            process_kind=ProcessKind.ISENTHALPIC,
            name="Throttle Valve",
            outlet_spec=ThermoSpec(pressure_mpa=1.5),
        )
        self.circuit.add_component(valve)
        self.circuit.start_component_id = "V1"
        self.solution = solve_circuit(self.circuit)
        self.result = self.solution.component_results[0]

    def test_valve_solves(self):
        assert self.result.status == "Solved"

    def test_valve_conserves_enthalpy(self):
        h_in = self.result.inlet_state.enthalpy_kj_kg if self.result.inlet_state else None
        h_out = self.result.outlet_state.enthalpy_kj_kg if self.result.outlet_state else None
        assert h_in is not None and h_out is not None
        assert abs(h_out - h_in) < 1e-6

    def test_valve_pressure_drops(self):
        p_in = self.result.inlet_state.pressure_mpa if self.result.inlet_state else None
        p_out = self.result.outlet_state.pressure_mpa if self.result.outlet_state else None
        assert p_in is not None and p_out is not None
        assert p_out < p_in


class TestIsobaricBoiler:
    """Validate isobaric heating."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.circuit = Circuit()
        # Feed pump outlet conditions (~15 MPa, subcooled)
        self.circuit.seed_state = backend.state_from_pressure_enthalpy(15.0, 210.0)
        self.circuit.seed_description = "Feed pump outlet"
        boiler = Component(
            component_id="B1",
            kind=ComponentKind.BOILER,
            process_kind=ProcessKind.ISOBARIC,
            name="Boiler",
            outlet_spec=ThermoSpec(pressure_mpa=15.0, temperature_c=540.0),
        )
        self.circuit.add_component(boiler)
        self.circuit.start_component_id = "B1"
        self.solution = solve_circuit(self.circuit)
        self.result = self.solution.component_results[0]

    def test_boiler_solves(self):
        assert self.result.status == "Solved"

    def test_boiler_pressure_constant(self):
        if self.result.inlet_state and self.result.outlet_state:
            assert abs(self.result.outlet_state.pressure_mpa - 15.0) < 1e-3

    def test_boiler_heat_added(self):
        assert self.result.heat_kj_kg > 3000.0  # significant heat addition


# ── Constraint diagnostics ─────────────────────────────────────────────


class TestConstraintDiagnostics:
    def test_single_turbine_is_well_defined(self):
        """A turbine with outlet pressure and efficiency set should be well-defined."""
        circuit = Circuit()
        circuit.seed_state = backend.state_from_pressure_temperature(15.0, 540.0)
        circuit.seed_description = "Steam source"
        turbine = Component(
            component_id="T1",
            kind=ComponentKind.TURBINE,
            process_kind=ProcessKind.ISENTROPIC,
            name="Turbine",
            outlet_spec=ThermoSpec(pressure_mpa=3.0, efficiency=0.88),
        )
        # Mark the user-defined fields
        turbine.user_input_fields.update(["outlet_pressure_mpa", "outlet_efficiency"])
        # Mark seed fields on start component
        for field in ("inlet_pressure_mpa", "inlet_temperature_c",
                      "inlet_enthalpy_kj_kg", "inlet_entropy_kj_kgk",
                      "inlet_specific_volume_m3_kg", "inlet_quality"):
            turbine.user_input_fields.add(field)
        circuit.add_component(turbine)
        circuit.start_component_id = "T1"
        diagnostics = analyze_constraint_system(circuit)
        assert diagnostics.system_status == "Well-defined"

    def test_empty_circuit_underconstrained(self):
        circuit = Circuit()
        diagnostics = analyze_constraint_system(circuit)
        assert diagnostics.system_status == "Underconstrained"

    def test_underconstrained_missing_pressure(self):
        circuit = Circuit()
        circuit.seed_state = backend.state_from_pressure_temperature(15.0, 540.0)
        circuit.seed_description = "Seed"
        circuit.start_component_id = "T1"
        circuit.add_component(
            Component(
                component_id="T1",
                kind=ComponentKind.TURBINE,
                process_kind=ProcessKind.ISENTROPIC,
                name="Turbine",
                # no outlet pressure, no efficiency
            )
        )
        diagnostics = analyze_constraint_system(circuit)
        assert diagnostics.system_status == "Underconstrained"


# ── Solver error handling ──────────────────────────────────────────────


class TestSolverErrors:
    def test_no_start_component(self):
        circuit = Circuit()
        with pytest.raises(SolverError, match="no start component"):
            solve_circuit(circuit)

    def test_no_seed_state(self):
        circuit = Circuit()
        circuit.add_component(
            Component(
                component_id="N1",
                kind=ComponentKind.CUSTOM,
                process_kind=ProcessKind.GENERAL,
                name="Test",
            )
        )
        circuit.start_component_id = "N1"
        with pytest.raises(SolverError, match="needs a seed state"):
            solve_circuit(circuit)


# ── CircuitSolution summary ────────────────────────────────────────────


class TestCircuitSolutionSummary:
    def test_summary_lines(self):
        solution = CircuitSolution(
            total_heat_in_kj_kg=3740.58,
            total_heat_out_kj_kg=2283.16,
            total_turbine_work_kj_kg=1475.18,
            total_pump_work_kj_kg=17.76,
            net_work_kj_kg=1457.42,
            thermal_efficiency=0.3896,
            back_work_ratio=0.012,
            system_status="Well-defined",
        )
        lines = solution.summary_lines()
        assert any("Heat in" in l for l in lines)
        assert any("Heat out" in l for l in lines)
        assert any("Turbine work" in l for l in lines)
        assert any("Pump work" in l for l in lines)
        assert any("Net work" in l for l in lines)
        assert any("efficiency" in l for l in lines)
        assert any("Well-defined" in l for l in lines)

    def test_summary_underconstrained(self):
        solution = CircuitSolution(
            system_status="Underconstrained",
            underconstrained_components=["Turbine"],
        )
        lines = solution.summary_lines()
        assert any("Underconstrained" in l for l in lines)


# ── Backend helper tests ───────────────────────────────────────────────


class TestSteamPropertyBackend:
    def test_supported_pairs(self):
        """Each supported state pair should produce a valid ThermoState."""
        tests = [
            (backend.state_from_pressure_temperature, 15.0, 540.0),
            (backend.state_from_pressure_enthalpy, 15.0, 3500.0),
            (backend.state_from_pressure_entropy, 15.0, 6.5),
            (backend.state_from_pressure_quality, 0.01, 0.9),
        ]
        for method, a, b in tests:
            state = method(a, b)
            assert state is not None
            assert state.enthalpy_kj_kg > 0

    def test_unsupported_pair_raises(self):
        # specific_volume + enthalpy is not a supported pair
        from heat_circuit_tool.thermo import StateSpec
        with pytest.raises(ValueError, match="Unsupported property pair"):
            backend.make_state(StateSpec(specific_volume_m3_kg=0.001, enthalpy_kj_kg=500.0))

    def test_round_trip_same_state(self):
        s1 = backend.state_from_pressure_temperature(15.0, 540.0)
        s2 = backend.state_from_pressure_temperature(15.0, 540.0)
        assert backend.same_state(s1, s2)

    def test_different_state(self):
        s1 = backend.state_from_pressure_temperature(15.0, 540.0)
        s2 = backend.state_from_pressure_temperature(10.0, 400.0)
        assert not backend.same_state(s1, s2)