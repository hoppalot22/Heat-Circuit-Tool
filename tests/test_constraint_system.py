from __future__ import annotations

from dataclasses import dataclass
import unittest

from heat_circuit_tool.model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec
from heat_circuit_tool.solver import analyze_constraint_system
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
        inlet_spec=inlet_spec or ThermoSpec(),
        outlet_spec=outlet_spec or ThermoSpec(),
    )
    component.user_input_fields = user_input_fields or set()
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
    blocked_circuit.add_component(
        make_component(
            "B1",
            name="Boiler",
            user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"},
        )
    )

    underconstrained_frontier = Circuit(seed_state=make_seed_state())
    underconstrained_frontier.add_component(
        make_component(
            "B1",
            name="Boiler",
            user_input_fields={"outlet_pressure_mpa"},
        )
    )

    well_defined_single = Circuit(seed_state=make_seed_state())
    well_defined_single.add_component(
        make_component(
            "B1",
            name="Boiler",
            user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"},
            outlet_spec=ThermoSpec(pressure_mpa=1.0, temperature_c=200.0),
        )
    )

    underconstrained_chain = Circuit(seed_state=make_seed_state())
    underconstrained_chain.add_component(
        make_component(
            "B1",
            name="Boiler",
            user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"},
            outlet_spec=ThermoSpec(pressure_mpa=1.0, temperature_c=220.0),
        )
    )
    underconstrained_chain.add_component(
        make_component(
            "T1",
            name="Turbine",
            kind=ComponentKind.TURBINE,
            process_kind=ProcessKind.ISENTROPIC,
            user_input_fields={"outlet_pressure_mpa"},
        )
    )
    underconstrained_chain.connect("B1", "T1")

    overconstrained_turbine = Circuit(seed_state=make_seed_state())
    overconstrained_turbine.add_component(
        make_component(
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
    )

    mixer_chain = Circuit(seed_state=make_seed_state())
    mixer_chain.add_component(
        make_component(
            "B1",
            name="Boiler",
            user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"},
            outlet_spec=ThermoSpec(pressure_mpa=1.0, temperature_c=210.0),
        )
    )
    mixer_chain.add_component(
        make_component(
            "M1",
            name="Mixer",
            kind=ComponentKind.MIXER,
            process_kind=ProcessKind.GENERAL,
        )
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
    def test_traversal_order_visits_breadth_first_then_disconnected_nodes(self) -> None:
        circuit = Circuit()
        for component_id, name in (("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")):
            circuit.add_component(make_component(component_id, name=name))
        circuit.connect("A", "B")
        circuit.connect("A", "C")

        order = [component.component_id for component in circuit.traversal_order("A")]

        self.assertEqual(order, ["A", "B", "C", "D"])

    def test_traversal_order_ignores_cycles_without_repeating_components(self) -> None:
        circuit = Circuit()
        for component_id in ("A", "B", "C"):
            circuit.add_component(make_component(component_id, name=component_id))
        circuit.connect("A", "B")
        circuit.connect("B", "C")
        circuit.connect("C", "A")

        order = [component.component_id for component in circuit.traversal_order("A")]

        self.assertEqual(order, ["A", "B", "C"])

    def test_ordered_path_follows_first_downstream_chain_and_stops_on_cycle(self) -> None:
        circuit = Circuit()
        for component_id in ("A", "B", "C"):
            circuit.add_component(make_component(component_id, name=component_id))
        circuit.connect("A", "B")
        circuit.connect("B", "C")
        circuit.connect("C", "A")

        path = [component.component_id for component in circuit.ordered_path("A")]

        self.assertEqual(path, ["A", "B", "C"])

    def test_ordered_path_uses_first_downstream_branch_only(self) -> None:
        circuit = Circuit()
        for component_id in ("A", "B", "C"):
            circuit.add_component(make_component(component_id, name=component_id))
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
        circuit.add_component(make_component("B1", name="Boiler", user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"}))

        diagnostics = analyze_constraint_system(circuit)

        self.assertEqual(diagnostics.system_status, "Underconstrained")
        self.assertEqual(diagnostics.blocked_components, ["Boiler"])
        self.assertEqual(diagnostics.component_diagnostics[0].status, "Blocked")

    def test_upstream_ready_component_with_one_missing_target_is_underconstrained(self) -> None:
        circuit = Circuit(seed_state=make_seed_state())
        circuit.add_component(
            make_component(
                "B1",
                name="Boiler",
                user_input_fields={"outlet_pressure_mpa"},
            )
        )

        diagnostics = analyze_constraint_system(circuit)

        self.assertEqual(diagnostics.system_status, "Underconstrained")
        self.assertEqual(diagnostics.component_diagnostics[0].status, "Underconstrained")
        self.assertEqual(diagnostics.total_additional_info_required, 1)
        self.assertEqual(diagnostics.frontier_min_additional_info, 1)
        self.assertTrue(diagnostics.propagation_hint)

    def test_well_defined_component_is_classified_as_solved_frontier(self) -> None:
        circuit = Circuit(seed_state=make_seed_state())
        circuit.add_component(
            make_component(
                "B1",
                name="Boiler",
                user_input_fields={"outlet_pressure_mpa", "outlet_temperature_c"},
                outlet_spec=ThermoSpec(pressure_mpa=1.0, temperature_c=200.0),
            )
        )

        diagnostics = analyze_constraint_system(circuit)

        self.assertEqual(diagnostics.system_status, "Well-defined")
        self.assertEqual(diagnostics.component_diagnostics[0].status, "Well-defined")
        self.assertEqual(diagnostics.underconstrained_components, [])
        self.assertEqual(diagnostics.overconstrained_components, [])

    def test_overconstrained_component_takes_precedence(self) -> None:
        circuit = Circuit(seed_state=make_seed_state())
        circuit.add_component(
            make_component(
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
        )

        diagnostics = analyze_constraint_system(circuit)

        self.assertEqual(diagnostics.system_status, "Overconstrained")
        self.assertEqual(diagnostics.component_diagnostics[0].status, "Overconstrained")
        self.assertEqual(diagnostics.overconstrained_components, ["Turbine"])


if __name__ == "__main__":
    unittest.main()