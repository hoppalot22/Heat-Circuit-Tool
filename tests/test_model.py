"""Tests for the Circuit and Component data model."""

import pytest
from heat_circuit_tool.model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec


def _make_component(
    component_id: str,
    kind: ComponentKind = ComponentKind.CUSTOM,
    process: ProcessKind = ProcessKind.GENERAL,
    name: str = "",
) -> Component:
    return Component(
        component_id=component_id,
        kind=kind,
        process_kind=process,
        name=name or f"{kind.value}_{component_id}",
    )


# ── Component creation ─────────────────────────────────────────────────


class TestComponentCreation:
    def test_minimal_component(self):
        c = _make_component("N1")
        assert c.component_id == "N1"
        assert c.name == "Custom_N1"
        assert c.kind == ComponentKind.CUSTOM
        assert c.process_kind == ProcessKind.GENERAL
        assert c.notes == ""
        assert c.upstream_ids == []
        assert c.downstream_ids == []

    def test_all_kinds(self):
        for kind in ComponentKind:
            c = _make_component("X", kind=kind)
            assert c.kind == kind

    def test_inlet_spec_defaults(self):
        c = _make_component("N1")
        assert c.inlet_spec.pressure_mpa is None
        assert c.inlet_spec.temperature_c is None

    def test_outlet_spec_defaults(self):
        c = _make_component("N1")
        assert c.outlet_spec.pressure_mpa is None
        assert c.outlet_spec.temperature_c is None

    def test_notes_round_trip(self):
        c = _make_component("N1")
        c.notes = "Test note"
        assert c.notes == "Test note"


# ── Component properties ────────────────────────────────────────────────


class TestComponentProperties:
    def test_upstream_id_single(self):
        c = _make_component("N1")
        c.upstream_ids = ["P1"]
        assert c.upstream_id == "P1"

    def test_upstream_id_none(self):
        c = _make_component("N1")
        assert c.upstream_id is None

    def test_upstream_id_setter(self):
        c = _make_component("N1")
        c.upstream_id = "P1"
        assert c.upstream_ids == ["P1"]
        c.upstream_id = None
        assert c.upstream_ids == []

    def test_downstream_id_single(self):
        c = _make_component("N1")
        c.downstream_ids = ["T1"]
        assert c.downstream_id == "T1"

    def test_downstream_id_none(self):
        c = _make_component("N1")
        assert c.downstream_id is None

    def test_downstream_id_setter(self):
        c = _make_component("N1")
        c.downstream_id = "T1"
        assert c.downstream_ids == ["T1"]
        c.downstream_id = None
        assert c.downstream_ids == []

    def test_center_default(self):
        from heat_circuit_tool.model_layout import ComponentLayout
        layout = ComponentLayout(component_id="N1")
        cx, cy = layout.center()
        assert cx == 90.0  # 0 + 180/2
        assert cy == 46.0  # 0 + 92/2

    def test_inlet_port_default(self):
        from heat_circuit_tool.model_layout import ComponentLayout
        layout = ComponentLayout(component_id="N1")
        px, py = layout.inlet_port()
        assert px == 0.0
        assert py == 46.0  # 0 + 92/2

    def test_outlet_port_default(self):
        from heat_circuit_tool.model_layout import ComponentLayout
        layout = ComponentLayout(component_id="N1")
        px, py = layout.outlet_port()
        assert px == 180.0
        assert py == 46.0


# ── Circuit operations ──────────────────────────────────────────────────


class TestCircuitAddRemove:
    def test_add_component(self):
        circuit = Circuit()
        c = _make_component("N1")
        circuit.add_component(c)
        assert "N1" in circuit.components
        assert circuit.start_component_id == "N1"

    def test_add_multiple_components(self):
        circuit = Circuit()
        for i in range(5):
            circuit.add_component(_make_component(f"N{i+1}"))
        assert len(circuit.components) == 5

    def test_remove_component(self):
        circuit = Circuit()
        circuit.add_component(_make_component("N1"))
        circuit.add_component(_make_component("N2"))
        circuit.remove_component("N1")
        assert "N1" not in circuit.components
        assert circuit.start_component_id == "N2"

    def test_remove_clears_connections(self):
        circuit = Circuit()
        circuit.add_component(_make_component("N1"))
        circuit.add_component(_make_component("N2"))
        circuit.add_component(_make_component("N3"))
        circuit.connect("N1", "N2")
        circuit.connect("N2", "N3")
        circuit.remove_component("N2")
        assert "N1" in circuit.components
        assert "N3" in circuit.components
        assert circuit.components["N1"].downstream_ids == []
        assert circuit.components["N3"].upstream_ids == []


class TestCircuitConnectDisconnect:
    def test_connect(self):
        circuit = Circuit()
        circuit.add_component(_make_component("N1"))
        circuit.add_component(_make_component("N2"))
        circuit.connect("N1", "N2")
        assert "N2" in circuit.components["N1"].downstream_ids
        assert "N1" in circuit.components["N2"].upstream_ids

    def test_connect_self_rejected(self):
        circuit = Circuit()
        circuit.add_component(_make_component("N1"))
        circuit.connect("N1", "N1")
        assert circuit.components["N1"].downstream_ids == []
        assert circuit.components["N1"].upstream_ids == []

    def test_disconnect(self):
        circuit = Circuit()
        circuit.add_component(_make_component("N1"))
        circuit.add_component(_make_component("N2"))
        circuit.connect("N1", "N2")
        circuit.disconnect("N1", "N2")
        assert circuit.components["N1"].downstream_ids == []
        assert circuit.components["N2"].upstream_ids == []

    def test_connect_duplicate(self):
        circuit = Circuit()
        circuit.add_component(_make_component("N1"))
        circuit.add_component(_make_component("N2"))
        circuit.connect("N1", "N2")
        circuit.connect("N1", "N2")  # should be idempotent
        assert circuit.components["N1"].downstream_ids == ["N2"]

    def test_incoming_outgoing(self):
        circuit = Circuit()
        circuit.add_component(_make_component("N1"))
        circuit.add_component(_make_component("N2"))
        circuit.add_component(_make_component("N3"))
        circuit.connect("N1", "N2")
        circuit.connect("N3", "N2")
        assert circuit.incoming("N2") == ["N1", "N3"]
        assert circuit.outgoing("N1") == ["N2"]
        assert circuit.outgoing("N2") == []


# ── Traversal ───────────────────────────────────────────────────────────


class TestTraversal:
    def test_ordered_path_linear(self):
        circuit = Circuit()
        for i in range(4):
            circuit.add_component(_make_component(f"N{i+1}"))
        circuit.connect("N1", "N2")
        circuit.connect("N2", "N3")
        circuit.connect("N3", "N4")
        path = circuit.ordered_path("N1")
        assert [c.component_id for c in path] == ["N1", "N2", "N3", "N4"]

    def test_ordered_path_branch_follows_first(self):
        circuit = Circuit()
        circuit.add_component(_make_component("N1"))
        circuit.add_component(_make_component("N2"))
        circuit.add_component(_make_component("N3"))
        circuit.connect("N1", "N2")
        circuit.connect("N1", "N3")
        path = circuit.ordered_path("N1")
        assert [c.component_id for c in path] == ["N1", "N2"]

    def test_traversal_order_linear(self):
        circuit = Circuit()
        for i in range(4):
            circuit.add_component(_make_component(f"N{i+1}"))
        circuit.connect("N1", "N2")
        circuit.connect("N2", "N3")
        circuit.connect("N3", "N4")
        path = circuit.traversal_order("N1")
        assert [c.component_id for c in path] == ["N1", "N2", "N3", "N4"]

    def test_traversal_order_branch(self):
        circuit = Circuit()
        circuit.add_component(_make_component("N1"))
        circuit.add_component(_make_component("N2"))
        circuit.add_component(_make_component("N3"))
        circuit.connect("N1", "N2")
        circuit.connect("N1", "N3")
        path = circuit.traversal_order("N1")
        assert [c.component_id for c in path] == ["N1", "N2", "N3"]

    def test_traversal_order_loop(self):
        circuit = Circuit()
        for i in range(4):
            circuit.add_component(_make_component(f"N{i+1}"))
        circuit.connect("N1", "N2")
        circuit.connect("N2", "N3")
        circuit.connect("N3", "N4")
        circuit.connect("N4", "N1")  # loop back
        path = circuit.traversal_order("N1")
        assert len(path) == 4
        # loop doesn't cause infinite traversal

    def test_traversal_order_orphans_appended(self):
        circuit = Circuit()
        circuit.add_component(_make_component("N1"))
        circuit.add_component(_make_component("N2"))
        circuit.add_component(_make_component("N3"))
        circuit.connect("N1", "N2")
        # N3 is orphan
        path = circuit.traversal_order("N1")
        ids = [c.component_id for c in path]
        assert ids[:2] == ["N1", "N2"]
        assert "N3" in ids

    def test_empty_circuit(self):
        circuit = Circuit()
        assert circuit.ordered_path() == []
        assert circuit.traversal_order() == []


# ── ThermoSpec ──────────────────────────────────────────────────────────


class TestThermoSpec:
    def test_defined_count_zero(self):
        spec = ThermoSpec()
        assert spec.defined_count() == 0

    def test_defined_count_single(self):
        spec = ThermoSpec(pressure_mpa=15.0)
        assert spec.defined_count() == 1

    def test_defined_count_multiple(self):
        spec = ThermoSpec(pressure_mpa=15.0, temperature_c=540.0, efficiency=0.88)
        assert spec.defined_count() == 3

    def test_to_state_spec_preserves_state_fields(self):
        spec = ThermoSpec(
            pressure_mpa=15.0,
            temperature_c=540.0,
            enthalpy_kj_kg=3500.0,
            quality=1.0,
        )
        state_spec = spec.to_state_spec()
        assert state_spec.pressure_mpa == 15.0
        assert state_spec.temperature_c == 540.0
        assert state_spec.enthalpy_kj_kg == 3500.0
        assert state_spec.quality == 1.0

    def test_to_state_spec_omits_equipment(self):
        spec = ThermoSpec(
            pressure_mpa=15.0,
            temperature_c=540.0,
            efficiency=0.88,
            heat_duty_kw=5000.0,
        )
        state_spec = spec.to_state_spec()
        assert state_spec.pressure_mpa == 15.0
        assert state_spec.temperature_c == 540.0
        # equipment fields should not leak through
        assert not hasattr(state_spec, "efficiency")

    def test_pretty_non_empty(self):
        spec = ThermoSpec(pressure_mpa=15.0, temperature_c=540.0)
        text = spec.pretty()
        assert "P=" in text
        assert "T=" in text
        assert "C" in text

    def test_pretty_empty(self):
        spec = ThermoSpec()
        assert spec.pretty() == "(none)"