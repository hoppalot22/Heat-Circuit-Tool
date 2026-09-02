from __future__ import annotations

from .model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec
from .solver import SteamPropertyBackend, solve_circuit


def _set_specs(circuit: Circuit, component: Component, *, inlet_spec: ThermoSpec | None = None, outlet_spec: ThermoSpec | None = None) -> None:
    if inlet_spec is not None:
        circuit.inlet_edge(component).spec = inlet_spec
    if outlet_spec is not None:
        circuit.outlet_edge(component).spec = outlet_spec


def build_reheat_rankine_demo() -> Circuit:
    circuit = Circuit()

    pump = Component(
        component_id="P1",
        kind=ComponentKind.PUMP,
        process_kind=ProcessKind.ISENTROPIC,
        name="Feed Pump",
        x=50,
        y=250,
        notes="Pressurizes condensate to boiler pressure.",
    )
    boiler = Component(
        component_id="B1",
        kind=ComponentKind.BOILER,
        process_kind=ProcessKind.ISOBARIC,
        name="Boiler",
        x=320,
        y=80,
        notes="Superheats the feedwater to main steam conditions.",
    )
    hpt = Component(
        component_id="T1",
        kind=ComponentKind.TURBINE,
        process_kind=ProcessKind.ISENTROPIC,
        name="HP Turbine",
        x=600,
        y=80,
        notes="Expands steam to reheat pressure.",
    )
    reheater = Component(
        component_id="R1",
        kind=ComponentKind.REHEATER,
        process_kind=ProcessKind.ISOBARIC,
        name="Reheater",
        x=880,
        y=80,
        notes="Restores steam temperature before the LP turbine.",
    )
    lpt = Component(
        component_id="T2",
        kind=ComponentKind.TURBINE,
        process_kind=ProcessKind.ISENTROPIC,
        name="LP Turbine",
        x=1160,
        y=80,
        notes="Expands steam to condenser pressure.",
    )
    condenser = Component(
        component_id="C1",
        kind=ComponentKind.CONDENSER,
        process_kind=ProcessKind.ISOBARIC,
        name="Condenser",
        x=1440,
        y=250,
        notes="Condenses exhaust steam to saturated liquid.",
    )

    for component in (pump, boiler, hpt, reheater, lpt, condenser):
        circuit.add_component(component)

    _set_specs(circuit, pump, inlet_spec=ThermoSpec(efficiency=0.85), outlet_spec=ThermoSpec(pressure_mpa=15.0, efficiency=0.85))
    _set_specs(circuit, boiler, outlet_spec=ThermoSpec(pressure_mpa=15.0, temperature_c=540.0))
    _set_specs(circuit, hpt, outlet_spec=ThermoSpec(pressure_mpa=3.0, efficiency=0.88))
    _set_specs(circuit, reheater, outlet_spec=ThermoSpec(pressure_mpa=3.0, temperature_c=540.0))
    _set_specs(circuit, lpt, outlet_spec=ThermoSpec(pressure_mpa=0.01, efficiency=0.88))
    _set_specs(circuit, condenser, outlet_spec=ThermoSpec(pressure_mpa=0.01, quality=0.0))

    circuit.connect("P1", "B1")
    circuit.connect("B1", "T1")
    circuit.connect("T1", "R1")
    circuit.connect("R1", "T2")
    circuit.connect("T2", "C1")
    circuit.connect("C1", "P1")

    circuit.start_component_id = "B1"
    circuit.seed_state = SteamPropertyBackend().state_from_pressure_temperature(15.0, 45.0)
    provisional_solution = solve_circuit(circuit)
    pump_result = next(result for result in provisional_solution.component_results if result.component_id == "P1")
    if pump_result.outlet_state is not None:
        circuit.seed_state = pump_result.outlet_state
    circuit.seed_description = "Feed pump outlet / boiler inlet state"
    return circuit
