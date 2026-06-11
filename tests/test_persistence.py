"""Tests for circuit/project serialization and deserialization."""

import json
import tempfile
from pathlib import Path

from heat_circuit_tool.model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec
from heat_circuit_tool.model_layout import ComponentLayout, ComponentUIState
from heat_circuit_tool.persistence import circuit_to_dict, circuit_from_dict, save_project_file, load_project_file
from heat_circuit_tool.thermo import SteamPropertyBackend


backend = SteamPropertyBackend()


class TestCircuitRoundTrip:
    """Ensure circuit converts cleanly to dict and back."""

    def _make_simple_circuit(self) -> Circuit:
        circuit = Circuit()
        circuit.seed_state = backend.state_from_pressure_temperature(15.0, 45.0)
        circuit.seed_description = "Test seed"

        c1 = Component(
            component_id="P1",
            kind=ComponentKind.PUMP,
            process_kind=ProcessKind.ISENTROPIC,
            name="Feed Pump",
            notes="Test pump",
            inlet_spec=ThermoSpec(efficiency=0.85),
            outlet_spec=ThermoSpec(pressure_mpa=15.0, efficiency=0.85),
        )
        c2 = Component(
            component_id="B1",
            kind=ComponentKind.BOILER,
            process_kind=ProcessKind.ISOBARIC,
            name="Boiler",
            outlet_spec=ThermoSpec(pressure_mpa=15.0, temperature_c=540.0),
        )
        circuit.add_component(c1)
        circuit.add_component(c2)
        circuit.connect("P1", "B1")
        circuit.start_component_id = "P1"
        return circuit

    def test_circuit_to_dict_round_trip(self):
        circuit = self._make_simple_circuit()
        data = circuit_to_dict(circuit)
        restored = circuit_from_dict(data)

        assert len(restored.components) == 2
        assert restored.start_component_id == "P1"
        assert "P1" in restored.components
        assert restored.components["P1"].name == "Feed Pump"
        assert restored.components["P1"].kind == ComponentKind.PUMP
        assert restored.seed_description == "Test seed"
        assert restored.seed_state is not None
        assert abs(restored.seed_state.pressure_mpa - 15.0) < 1e-4

    def test_connections_preserved(self):
        circuit = self._make_simple_circuit()
        data = circuit_to_dict(circuit)
        restored = circuit_from_dict(data)
        assert "B1" in restored.components["P1"].downstream_ids
        assert "P1" in restored.components["B1"].upstream_ids

    def test_thermo_spec_preserved(self):
        circuit = self._make_simple_circuit()
        data = circuit_to_dict(circuit)
        restored = circuit_from_dict(data)
        boiler = restored.components["B1"]
        assert boiler.outlet_spec.pressure_mpa == 15.0
        assert boiler.outlet_spec.temperature_c == 540.0

    def test_layout_preserved(self):
        circuit = self._make_simple_circuit()
        data = circuit_to_dict(circuit)
        restored = circuit_from_dict(data)
        assert len(restored.layouts) == 2
        for cid, layout in restored.layouts.items():
            assert isinstance(layout, ComponentLayout)
            assert layout.component_id == cid
            assert layout.width == 180.0
            assert layout.height == 92.0

    def test_ui_state_preserved(self):
        circuit = self._make_simple_circuit()
        data = circuit_to_dict(circuit)
        restored = circuit_from_dict(data)
        assert len(restored.ui_states) == 2
        for cid, ui in restored.ui_states.items():
            assert isinstance(ui, ComponentUIState)
            assert ui.component_id == cid
            assert ui.inlet_definition_mode == "Auto"
            assert ui.outlet_definition_mode == "Auto"

    def test_empty_circuit_round_trip(self):
        circuit = Circuit()
        data = circuit_to_dict(circuit)
        restored = circuit_from_dict(data)
        assert len(restored.components) == 0

    def test_circuit_without_seed(self):
        circuit = Circuit()
        c = Component(component_id="N1", kind=ComponentKind.CUSTOM, process_kind=ProcessKind.GENERAL, name="Test")
        circuit.add_component(c)
        data = circuit_to_dict(circuit)
        restored = circuit_from_dict(data)
        assert restored.seed_state is None
        assert len(restored.components) == 1


class TestProjectFileSaveLoad:
    """Test save_project_file and load_project_file."""

    def test_save_and_load(self):
        circuit = Circuit()
        circuit.seed_state = backend.state_from_pressure_temperature(10.0, 300.0)
        c = Component(
            component_id="T1",
            kind=ComponentKind.TURBINE,
            process_kind=ProcessKind.ISENTROPIC,
            name="Turbine",
            outlet_spec=ThermoSpec(pressure_mpa=1.0, efficiency=0.9),
        )
        circuit.add_component(c)
        circuit.start_component_id = "T1"

        snapshots = [{"name": "Test", "circuit": circuit_to_dict(circuit)}]
        latest = circuit_to_dict(circuit)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".hct.json", delete=False, encoding="utf-8") as f:
            path = f.name
            save_project_file(path, circuit, snapshots, latest)

        try:
            payload = load_project_file(path)
            assert "active_circuit" in payload
            assert len(payload["snapshots"]) == 1
            assert payload["snapshots"][0]["name"] == "Test"
            assert payload["latest_solved"] is not None

            restored = circuit_from_dict(payload["active_circuit"])
            assert restored.components["T1"].name == "Turbine"
            assert restored.seed_state is not None
        finally:
            Path(path).unlink(missing_ok=True)


class TestComponentFieldsRoundTrip:
    """Verify all Component fields survive a round trip."""

    def test_all_fields(self):
        circuit = Circuit()
        c = Component(
            component_id="C1",
            kind=ComponentKind.BOILER,
            process_kind=ProcessKind.ISOBARIC,
            name="Test Component",
            notes="Test notes",
            upstream_ids=["U1"],
            downstream_ids=["D1"],
        )
        c.inlet_spec = ThermoSpec(pressure_mpa=10.0, temperature_c=300.0, enthalpy_kj_kg=3000.0)
        c.outlet_spec = ThermoSpec(pressure_mpa=10.0, temperature_c=500.0, quality=1.0, heat_duty_kw=5000.0)
        layout = ComponentLayout(component_id="C1", x=50.0, y=100.0, width=200.0, height=100.0)
        ui = ComponentUIState(component_id="C1", inlet_definition_mode="Manual", outlet_definition_mode="Manual")
        circuit.add_component(c, layout=layout, ui_state=ui)
        circuit.start_component_id = "C1"

        data = circuit_to_dict(circuit)
        restored = circuit_from_dict(data)
        rc = restored.components["C1"]

        assert rc.component_id == "C1"
        assert rc.kind == ComponentKind.BOILER
        assert rc.process_kind == ProcessKind.ISOBARIC
        assert rc.name == "Test Component"
        assert rc.notes == "Test notes"
        assert rc.upstream_ids == ["U1"]
        assert rc.downstream_ids == ["D1"]

        assert rc.inlet_spec.pressure_mpa == 10.0
        assert rc.inlet_spec.temperature_c == 300.0
        assert rc.outlet_spec.quality == 1.0
        assert rc.outlet_spec.heat_duty_kw == 5000.0

        rl = restored.layouts["C1"]
        assert rl.x == 50.0
        assert rl.y == 100.0
        assert rl.width == 200.0
        assert rl.height == 100.0

        rui = restored.ui_states["C1"]
        assert rui.inlet_definition_mode == "Manual"
        assert rui.outlet_definition_mode == "Manual"