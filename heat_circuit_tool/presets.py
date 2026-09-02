from __future__ import annotations

from dataclasses import dataclass, fields

from .model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec

_THERMO_SPEC_FIELD_NAMES = [f.name for f in fields(ThermoSpec)]


@dataclass(frozen=True, slots=True)
class ComponentPreset:
    name: str
    kind: ComponentKind
    process_kind: ProcessKind
    inlet_spec: ThermoSpec
    outlet_spec: ThermoSpec
    notes: str


PRESETS: dict[str, ComponentPreset] = {
    "Feed Pump": ComponentPreset(
        name="Feed Pump",
        kind=ComponentKind.PUMP,
        process_kind=ProcessKind.ISENTROPIC,
        inlet_spec=ThermoSpec(efficiency=0.85),
        outlet_spec=ThermoSpec(pressure_mpa=15.0, efficiency=0.85),
        notes="Pressurizes liquid water to boiler pressure.",
    ),
    "Main Boiler": ComponentPreset(
        name="Main Boiler",
        kind=ComponentKind.BOILER,
        process_kind=ProcessKind.ISOBARIC,
        inlet_spec=ThermoSpec(),
        outlet_spec=ThermoSpec(pressure_mpa=15.0, temperature_c=540.0),
        notes="Raises steam to superheated turbine inlet conditions.",
    ),
    "HP Turbine": ComponentPreset(
        name="HP Turbine",
        kind=ComponentKind.TURBINE,
        process_kind=ProcessKind.ISENTROPIC,
        inlet_spec=ThermoSpec(efficiency=0.88),
        outlet_spec=ThermoSpec(pressure_mpa=3.0, efficiency=0.88),
        notes="High-pressure expansion stage.",
    ),
    "Reheater": ComponentPreset(
        name="Reheater",
        kind=ComponentKind.REHEATER,
        process_kind=ProcessKind.ISOBARIC,
        inlet_spec=ThermoSpec(),
        outlet_spec=ThermoSpec(pressure_mpa=3.0, temperature_c=540.0),
        notes="Restores temperature between turbine stages.",
    ),
    "LP Turbine": ComponentPreset(
        name="LP Turbine",
        kind=ComponentKind.TURBINE,
        process_kind=ProcessKind.ISENTROPIC,
        inlet_spec=ThermoSpec(efficiency=0.88),
        outlet_spec=ThermoSpec(pressure_mpa=0.01, efficiency=0.88),
        notes="Low-pressure expansion stage.",
    ),
    "Surface Condenser": ComponentPreset(
        name="Surface Condenser",
        kind=ComponentKind.CONDENSER,
        process_kind=ProcessKind.ISOBARIC,
        inlet_spec=ThermoSpec(),
        outlet_spec=ThermoSpec(pressure_mpa=0.01, quality=0.0),
        notes="Condenses exhaust steam to saturated liquid.",
    ),
    "Process Pipe": ComponentPreset(
        name="Process Pipe",
        kind=ComponentKind.PIPE,
        process_kind=ProcessKind.ADIABATIC,
        inlet_spec=ThermoSpec(),
        outlet_spec=ThermoSpec(
            mass_flow_kg_s=12.0,
            pipe_length_m=50.0,
            pipe_outer_diameter_m=0.2191,
            pipe_wall_thickness_m=0.0082,
            pipe_roughness_m=4.5e-5,
            elevation_change_m=0.0,
            local_loss_coefficient=1.5,
        ),
        notes="Hydraulic pressure loss from friction, elevation, and local losses.",
    ),
    "Throttle Valve": ComponentPreset(
        name="Throttle Valve",
        kind=ComponentKind.VALVE,
        process_kind=ProcessKind.ISENTHALPIC,
        inlet_spec=ThermoSpec(),
        outlet_spec=ThermoSpec(pressure_mpa=1.5),
        notes="Pressure reduction with approximately constant enthalpy.",
    ),
    "Steam Splitter": ComponentPreset(
        name="Steam Splitter",
        kind=ComponentKind.SPLITTER,
        process_kind=ProcessKind.ADIABATIC,
        inlet_spec=ThermoSpec(),
        outlet_spec=ThermoSpec(),
        notes="Copies state to multiple outgoing branches.",
    ),
    "Steam Mixer": ComponentPreset(
        name="Steam Mixer",
        kind=ComponentKind.MIXER,
        process_kind=ProcessKind.ADIABATIC,
        inlet_spec=ThermoSpec(),
        outlet_spec=ThermoSpec(),
        notes="Combines incoming branches into one mixed state.",
    ),
}


def preset_names() -> list[str]:
    return sorted(PRESETS.keys())


def apply_preset(circuit: Circuit, component: Component, preset_name: str) -> None:
    """Apply a preset to a component that has already been added to `circuit`.

    Presets describe single, unconnected components, so this always writes into
    the component's own boundary edges (created by `Circuit.add_component`).
    """
    preset = PRESETS[preset_name]
    component.kind = preset.kind
    component.process_kind = preset.process_kind
    component.name = preset.name
    inlet_edge = circuit.inlet_edge(component)
    outlet_edge = circuit.outlet_edge(component)
    for attr in _THERMO_SPEC_FIELD_NAMES:
        setattr(inlet_edge.spec, attr, getattr(preset.inlet_spec, attr))
        setattr(outlet_edge.spec, attr, getattr(preset.outlet_spec, attr))
    component.notes = preset.notes
