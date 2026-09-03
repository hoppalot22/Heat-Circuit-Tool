from __future__ import annotations

from dataclasses import dataclass
import unittest

from heat_circuit_tool.model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec
from heat_circuit_tool.persistence import _circuit_from_legacy_dict, circuit_from_dict, circuit_to_dict
from heat_circuit_tool.solver import ThermoSolver, analyze_constraint_system
from heat_circuit_tool.thermo import ThermoState


def make_seed_state() -> ThermoState:
    return ThermoState(
        pressure_mpa=1.0,
        temperature_c=100.0,
        enthalpy_kj_kg=420.0,
        entropy_kj_kgk=1.30,
        specific_volume_m3_kg=0.0010,
    )


def make_component(
    circuit: Circuit,
    component_id: str,
    *,
    name: str,
    kind: ComponentKind = ComponentKind.BOILER,
    process_kind: ProcessKind = ProcessKind.ISOBARIC,
    inlet_spec: ThermoSpec | None = None,
    outlet_spec: ThermoSpec | None = None,
    user_input_fields: set[str] | None = None,
) -> Component:
    component = Component(
        component_id=component_id,
        kind=kind,
        process_kind=process_kind,
        name=name,
    )
    circuit.add_component(component)
    inlet_edge = circuit.inlet_edge(component)
    outlet_edge = circuit.outlet_edge(component)
    if inlet_spec is not None:
        inlet_edge.spec = inlet_spec
    if outlet_spec is not None:
        outlet_edge.spec = outlet_spec
    for field_name in user_input_fields or set():
        if field_name.startswith("inlet_"):
            inlet_edge.user_input_fields.add(field_name[len("inlet_"):])
        elif field_name.startswith("outlet_"):
            outlet_edge.user_input_fields.add(field_name[len("outlet_"):])
        else:
            outlet_edge.user_input_fields.add(field_name)
    return component


@dataclass(frozen=True)
class SampleSetup:
    name: str
    circuit: Circuit
    expected_system_status: str
    expected_component_statuses: dict[str, str]
    expected_overconstrained: list[str] | None = None
    expected_underconstrained: list[str] | None = None
    expected_blocked: list[str] | None = None
    expected_frontier_min_additional_info: int | None = None


def build_sample_setups() -> list[SampleSetup]:
    empty_circuit = Circuit()

    blocked_circuit = Circuit()
    make_component(
        blocked_circuit,
        "B1",
        name="Boiler",
        user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"},
    )

    underconstrained_frontier = Circuit(seed_state=make_seed_state())
    make_component(
        underconstrained_frontier,
        "B1",
        name="Boiler",
        user_input_fields={"outlet_pressure_mpa"},
    )

    well_defined_single = Circuit(seed_state=make_seed_state())
    make_component(
        well_defined_single,
        "B1",
        name="Boiler",
        user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"},
        outlet_spec=ThermoSpec(pressure_mpa=1.0, temperature_c=200.0),
    )

    underconstrained_chain = Circuit(seed_state=make_seed_state())
    make_component(
        underconstrained_chain,
        "B1",
        name="Boiler",
        user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"},
        outlet_spec=ThermoSpec(pressure_mpa=1.0, temperature_c=220.0),
    )
    make_component(
        underconstrained_chain,
        "T1",
        name="Turbine",
        kind=ComponentKind.TURBINE,
        process_kind=ProcessKind.ISENTROPIC,
        user_input_fields={"outlet_pressure_mpa"},
    )
    underconstrained_chain.connect("B1", "T1")

    overconstrained_turbine = Circuit(seed_state=make_seed_state())
    make_component(
        overconstrained_turbine,
        "T1",
        name="Turbine",
        kind=ComponentKind.TURBINE,
        process_kind=ProcessKind.ISENTROPIC,
        user_input_fields={
            "outlet_pressure_mpa",
            "outlet_temperature_c",
            "outlet_enthalpy_kj_kg",
        },
        outlet_spec=ThermoSpec(
            pressure_mpa=0.1,
            temperature_c=120.0,
            enthalpy_kj_kg=2600.0,
        ),
    )

    mixer_chain = Circuit(seed_state=make_seed_state())
    make_component(
        mixer_chain,
        "B1",
        name="Boiler",
        user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"},
        outlet_spec=ThermoSpec(pressure_mpa=1.0, temperature_c=210.0),
    )
    make_component(
        mixer_chain,
        "M1",
        name="Mixer",
        kind=ComponentKind.MIXER,
        process_kind=ProcessKind.GENERAL,
    )
    mixer_chain.connect("B1", "M1")

    return [
        SampleSetup(
            name="empty circuit",
            circuit=empty_circuit,
            expected_system_status="Underconstrained",
            expected_component_statuses={},
            expected_underconstrained=[],
            expected_overconstrained=[],
            expected_blocked=[],
        ),
        SampleSetup(
            name="blocked start component",
            circuit=blocked_circuit,
            expected_system_status="Underconstrained",
            expected_component_statuses={"Boiler": "Blocked"},
            expected_blocked=["Boiler"],
        ),
        SampleSetup(
            name="underconstrained frontier",
            circuit=underconstrained_frontier,
            expected_system_status="Underconstrained",
            expected_component_statuses={"Boiler": "Underconstrained"},
            expected_underconstrained=["Boiler"],
            expected_frontier_min_additional_info=1,
        ),
        SampleSetup(
            name="well defined single component",
            circuit=well_defined_single,
            expected_system_status="Well-defined",
            expected_component_statuses={"Boiler": "Well-defined"},
            expected_underconstrained=[],
            expected_overconstrained=[],
            expected_blocked=[],
        ),
        SampleSetup(
            name="underconstrained chain",
            circuit=underconstrained_chain,
            expected_system_status="Underconstrained",
            expected_component_statuses={"Boiler": "Well-defined", "Turbine": "Underconstrained"},
            expected_underconstrained=["Turbine"],
            expected_frontier_min_additional_info=1,
        ),
        SampleSetup(
            name="overconstrained turbine",
            circuit=overconstrained_turbine,
            expected_system_status="Overconstrained",
            expected_component_statuses={"Turbine": "Overconstrained"},
            expected_overconstrained=["Turbine"],
        ),
        SampleSetup(
            name="mixer propagation",
            circuit=mixer_chain,
            expected_system_status="Well-defined",
            expected_component_statuses={"Boiler": "Well-defined", "Mixer": "Well-defined"},
            expected_underconstrained=[],
            expected_overconstrained=[],
            expected_blocked=[],
        ),
    ]


class ConstraintSystemTests(unittest.TestCase):
    def test_duplicate_component_ids_are_rejected(self) -> None:
        circuit = Circuit()
        first = Component(component_id="A", kind=ComponentKind.BOILER, process_kind=ProcessKind.ISOBARIC, name="A")
        circuit.add_component(first)

        with self.assertRaisesRegex(ValueError, "Duplicate component_id"):
            circuit.add_component(Component(component_id="A", kind=ComponentKind.PUMP, process_kind=ProcessKind.ISENTROPIC, name="A2"))

    def test_self_link_is_rejected(self) -> None:
        circuit = Circuit()
        make_component(circuit, "A", name="A")

        with self.assertRaisesRegex(ValueError, "self-link"):
            circuit.connect("A", "A")

    def test_branch_connections_have_distinct_shared_edges(self) -> None:
        circuit = Circuit()
        source = make_component(circuit, "S", name="Source")
        first = make_component(circuit, "A", name="First")
        second = make_component(circuit, "B", name="Second")

        circuit.connect("S", "A")
        circuit.connect("S", "B")
        circuit.connect("S", "B")

        self.assertEqual(len(source.outlet_edge_ids), 2)
        self.assertEqual(len(second.inlet_edge_ids), 1)
        self.assertIs(circuit.outlet_edges(source)[0], circuit.inlet_edges(first)[0])
        self.assertIs(circuit.outlet_edges(source)[1], circuit.inlet_edges(second)[0])

    def test_removing_branch_component_cleans_shared_edge_references(self) -> None:
        circuit = Circuit()
        source = make_component(circuit, "S", name="Source")
        first = make_component(circuit, "A", name="First")
        second = make_component(circuit, "B", name="Second")
        circuit.connect("S", "A")
        circuit.connect("S", "B")

        removed_edge_ids = set(first.inlet_edge_ids)
        circuit.remove_component("A")

        self.assertTrue(removed_edge_ids.isdisjoint(circuit.edges))
        self.assertEqual(len(source.outlet_edge_ids), 1)
        self.assertEqual(source.outlet_edge_ids, second.inlet_edge_ids)

    def test_branch_edge_references_round_trip_through_persistence(self) -> None:
        circuit = Circuit()
        source = make_component(circuit, "S", name="Source")
        first = make_component(circuit, "A", name="First")
        second = make_component(circuit, "B", name="Second")
        circuit.connect("S", "A")
        circuit.connect("S", "B")

        restored = circuit_from_dict(circuit_to_dict(circuit))

        self.assertEqual(restored.components["S"].outlet_edge_ids, source.outlet_edge_ids)
        self.assertEqual(restored.components["A"].inlet_edge_ids, first.inlet_edge_ids)
        self.assertEqual(restored.components["B"].inlet_edge_ids, second.inlet_edge_ids)

    def test_mixer_uses_mass_flow_weighted_pressure_and_enthalpy(self) -> None:
        solver = ThermoSolver()
        states = [
            ThermoState(1.0, 100.0, 100.0, 1.0, 0.001),
            ThermoState(2.0, 200.0, 300.0, 2.0, 0.002),
        ]

        mixed = solver._mix_states(states, [1.0, 3.0])

        self.assertAlmostEqual(mixed.pressure_mpa, 1.0)
        self.assertAlmostEqual(mixed.enthalpy_kj_kg, 250.0)

    def test_mixer_falls_back_to_equal_weights_without_complete_flows(self) -> None:
        solver = ThermoSolver()
        states = [
            ThermoState(1.0, 100.0, 100.0, 1.0, 0.001),
            ThermoState(2.0, 200.0, 300.0, 2.0, 0.002),
        ]

        mixed = solver._mix_states(states, [1.0, None])

        self.assertAlmostEqual(mixed.pressure_mpa, 1.0)
        self.assertAlmostEqual(mixed.enthalpy_kj_kg, 200.0)

    def test_outlet_defined_turbine_can_reverse_solve(self) -> None:
        circuit = Circuit()
        component = make_component(
            circuit,
            "T1",
            name="Turbine",
            kind=ComponentKind.TURBINE,
            process_kind=ProcessKind.ISENTROPIC,
            inlet_spec=ThermoSpec(pressure_mpa=15.0),
            outlet_spec=ThermoSpec(pressure_mpa=3.0, temperature_c=250.0, efficiency=0.88),
            user_input_fields={"inlet_pressure_mpa", "outlet_pressure_mpa", "outlet_temperature_c", "outlet_efficiency"},
        )

        results = ThermoSolver().propagate(circuit)

        self.assertEqual(results[component.component_id].status, "Solved")
        self.assertIsNotNone(results[component.component_id].inlet_state)

    def test_legacy_migration_preserves_downstream_edge_metadata(self) -> None:
        legacy = {
            "start_component_id": "A",
            "components": [
                {
                    "component_id": "A",
                    "kind": "Boiler",
                    "process_kind": "Isobaric",
                    "name": "A",
                    "upstream_ids": [],
                    "downstream_ids": ["B"],
                    "outlet_spec": {},
                    "user_input_fields": [],
                    "solved_fields": [],
                    "conflicting_fields": [],
                },
                {
                    "component_id": "B",
                    "kind": "Boiler",
                    "process_kind": "Isobaric",
                    "name": "B",
                    "upstream_ids": ["A"],
                    "downstream_ids": [],
                    "inlet_spec": {},
                    "user_input_fields": [],
                    "solved_fields": ["inlet_temperature_c"],
                    "conflicting_fields": ["inlet_pressure_mpa"],
                },
            ],
        }

        circuit = _circuit_from_legacy_dict(legacy)
        edge = circuit.outlet_edge(circuit.components["A"])

        self.assertEqual(edge.solved_fields, {"temperature_c"})
        self.assertEqual(edge.conflicting_fields, {"pressure_mpa"})

    def test_traversal_order_visits_breadth_first_then_disconnected_nodes(self) -> None:
        circuit = Circuit()
        for component_id, name in (("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")):
            make_component(circuit, component_id, name=name)
        circuit.connect("A", "B")
        circuit.connect("A", "C")

        order = [component.component_id for component in circuit.traversal_order("A")]

        self.assertEqual(order, ["A", "B", "C", "D"])

    def test_traversal_order_ignores_cycles_without_repeating_components(self) -> None:
        circuit = Circuit()
        for component_id in ("A", "B", "C"):
            make_component(circuit, component_id, name=component_id)
        circuit.connect("A", "B")
        circuit.connect("B", "C")
        circuit.connect("C", "A")

        order = [component.component_id for component in circuit.traversal_order("A")]

        self.assertEqual(order, ["A", "B", "C"])

    def test_ordered_path_follows_first_downstream_chain_and_stops_on_cycle(self) -> None:
        circuit = Circuit()
        for component_id in ("A", "B", "C"):
            make_component(circuit, component_id, name=component_id)
        circuit.connect("A", "B")
        circuit.connect("B", "C")
        circuit.connect("C", "A")

        path = [component.component_id for component in circuit.ordered_path("A")]

        self.assertEqual(path, ["A", "B", "C"])

    def test_ordered_path_uses_first_downstream_branch_only(self) -> None:
        circuit = Circuit()
        for component_id in ("A", "B", "C"):
            make_component(circuit, component_id, name=component_id)
        circuit.connect("A", "B")
        circuit.connect("A", "C")

        path = [component.component_id for component in circuit.ordered_path("A")]

        self.assertEqual(path, ["A", "B"])

    def test_sample_setups_match_expected_statuses(self) -> None:
        for setup in build_sample_setups():
            with self.subTest(setup=setup.name):
                diagnostics = analyze_constraint_system(setup.circuit)

                self.assertEqual(diagnostics.system_status, setup.expected_system_status)
                self.assertEqual(
                    {item.component_name: item.status for item in diagnostics.component_diagnostics},
                    setup.expected_component_statuses,
                )
                if setup.expected_overconstrained is not None:
                    self.assertEqual(diagnostics.overconstrained_components, setup.expected_overconstrained)
                if setup.expected_underconstrained is not None:
                    self.assertEqual(diagnostics.underconstrained_components, setup.expected_underconstrained)
                if setup.expected_blocked is not None:
                    self.assertEqual(diagnostics.blocked_components, setup.expected_blocked)
                if setup.expected_frontier_min_additional_info is not None:
                    self.assertEqual(diagnostics.frontier_min_additional_info, setup.expected_frontier_min_additional_info)

    def test_empty_circuit_is_underconstrained(self) -> None:
        diagnostics = analyze_constraint_system(Circuit())

        self.assertEqual(diagnostics.system_status, "Underconstrained")
        self.assertIn("Add components and constraints to begin solving.", diagnostics.propagation_hint)

    def test_start_component_without_seed_is_blocked(self) -> None:
        circuit = Circuit()
        make_component(circuit, "B1", name="Boiler", user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"})

        diagnostics = analyze_constraint_system(circuit)

        self.assertEqual(diagnostics.system_status, "Underconstrained")
        self.assertEqual(diagnostics.blocked_components, ["Boiler"])
        self.assertEqual(diagnostics.component_diagnostics[0].status, "Blocked")

    def test_upstream_ready_component_with_one_missing_target_is_underconstrained(self) -> None:
        circuit = Circuit(seed_state=make_seed_state())
        make_component(
            circuit,
            "B1",
            name="Boiler",
            user_input_fields={"outlet_pressure_mpa"},
        )

        diagnostics = analyze_constraint_system(circuit)

        self.assertEqual(diagnostics.system_status, "Underconstrained")
        self.assertEqual(diagnostics.component_diagnostics[0].status, "Underconstrained")
        self.assertEqual(diagnostics.total_additional_info_required, 1)
        self.assertEqual(diagnostics.frontier_min_additional_info, 1)
        self.assertTrue(diagnostics.propagation_hint)

    def test_well_defined_component_is_classified_as_solved_frontier(self) -> None:
        circuit = Circuit(seed_state=make_seed_state())
        make_component(
            circuit,
            "B1",
            name="Boiler",
            user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"},
            outlet_spec=ThermoSpec(pressure_mpa=1.0, temperature_c=200.0),
        )

        diagnostics = analyze_constraint_system(circuit)

        self.assertEqual(diagnostics.system_status, "Well-defined")
        self.assertEqual(diagnostics.component_diagnostics[0].status, "Well-defined")
        self.assertEqual(diagnostics.underconstrained_components, [])
        self.assertEqual(diagnostics.overconstrained_components, [])

    def test_overconstrained_component_takes_precedence(self) -> None:
        circuit = Circuit(seed_state=make_seed_state())
        make_component(
            circuit,
            "T1",
            name="Turbine",
            kind=ComponentKind.TURBINE,
            process_kind=ProcessKind.ISENTROPIC,
            user_input_fields={
                "outlet_pressure_mpa",
                "outlet_temperature_c",
                "outlet_enthalpy_kj_kg",
            },
            outlet_spec=ThermoSpec(
                pressure_mpa=0.1,
                temperature_c=120.0,
                enthalpy_kj_kg=2600.0,
            ),
        )

        diagnostics = analyze_constraint_system(circuit)

        self.assertEqual(diagnostics.system_status, "Overconstrained")
        self.assertEqual(diagnostics.component_diagnostics[0].status, "Overconstrained")
        self.assertEqual(diagnostics.overconstrained_components, ["Turbine"])


if __name__ == "__main__":
    unittest.main()