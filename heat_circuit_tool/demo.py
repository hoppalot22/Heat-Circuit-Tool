from __future__ import annotations

from .model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec
from .model_layout import ComponentLayout
from .solver import SteamPropertyBackend, solve_circuit


def build_reheat_rankine_demo() -> Circuit:
    circuit = Circuit()

    pump = Component(
        component_id="P1",
        kind=ComponentKind.PUMP,
        process_kind=ProcessKind.ISENTROPIC,
        name="Feed Pump",
        inlet_spec=ThermoSpec(efficiency=0.85),
        outlet_spec=ThermoSpec(pressure_mpa=15.0, efficiency=0.85),
        notes="Pressurizes condensate to boiler pressure.",
    )
    boiler = Component(
        component_id="B1",
        kind=ComponentKind.BOILER,
        process_kind=ProcessKind.ISOBARIC,
        name="Boiler",
        outlet_spec=ThermoSpec(pressure_mpa=15.0, temperature_c=540.0),
        notes="Superheats the feedwater to main steam conditions.",
    )
    hpt = Component(
        component_id="T1",
        kind=ComponentKind.TURBINE,
        process_kind=ProcessKind.ISENTROPIC,
        name="HP Turbine",
        outlet_spec=ThermoSpec(pressure_mpa=3.0, efficiency=0.88),
        notes="Expands steam to reheat pressure.",
    )
    reheater = Component(
        component_id="R1",
        kind=ComponentKind.REHEATER,
        process_kind=ProcessKind.ISOBARIC,
        name="Reheater",
        outlet_spec=ThermoSpec(pressure_mpa=3.0, temperature_c=540.0),
        notes="Restores steam temperature before the LP turbine.",
    )
    lpt = Component(
        component_id="T2",
        kind=ComponentKind.TURBINE,
        process_kind=ProcessKind.ISENTROPIC,
        name="LP Turbine",
        outlet_spec=ThermoSpec(pressure_mpa=0.01, efficiency=0.88),
        notes="Expands steam to condenser pressure.",
    )
    condenser = Component(
        component_id="C1",
        kind=ComponentKind.CONDENSER,
        process_kind=ProcessKind.ISOBARIC,
        name="Condenser",
        outlet_spec=ThermoSpec(pressure_mpa=0.01, quality=0.0),
        notes="Condenses exhaust steam to saturated liquid.",
    )

    layouts = {
        "P1": ComponentLayout(component_id="P1", x=50, y=250),
        "B1": ComponentLayout(component_id="B1", x=320, y=80),
        "T1": ComponentLayout(component_id="T1", x=600, y=80),
        "R1": ComponentLayout(component_id="R1", x=880, y=80),
        "T2": ComponentLayout(component_id="T2", x=1160, y=80),
        "C1": ComponentLayout(component_id="C1", x=1440, y=250),
    }

    for component in (pump, boiler, hpt, reheater, lpt, condenser):
        circuit.add_component(component, layout=layouts[component.component_id])

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