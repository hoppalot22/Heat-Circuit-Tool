from __future__ import annotations

from dataclasses import dataclass

from .model import Component, ComponentKind, ProcessKind, ThermoSpec


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


def apply_preset(component: Component, preset_name: str) -> None:
    preset = PRESETS[preset_name]
    component.kind = preset.kind
    component.process_kind = preset.process_kind
    component.name = preset.name
    component.inlet_spec = ThermoSpec(
        pressure_mpa=preset.inlet_spec.pressure_mpa,
        temperature_c=preset.inlet_spec.temperature_c,
        enthalpy_kj_kg=preset.inlet_spec.enthalpy_kj_kg,
        entropy_kj_kgk=preset.inlet_spec.entropy_kj_kgk,
        quality=preset.inlet_spec.quality,
        specific_volume_m3_kg=preset.inlet_spec.specific_volume_m3_kg,
        efficiency=preset.inlet_spec.efficiency,
        heat_duty_kw=preset.inlet_spec.heat_duty_kw,
        pressure_drop_mpa=preset.inlet_spec.pressure_drop_mpa,
        mass_flow_kg_s=preset.inlet_spec.mass_flow_kg_s,
        pipe_length_m=preset.inlet_spec.pipe_length_m,
        pipe_outer_diameter_m=preset.inlet_spec.pipe_outer_diameter_m,
        pipe_wall_thickness_m=preset.inlet_spec.pipe_wall_thickness_m,
        pipe_roughness_m=preset.inlet_spec.pipe_roughness_m,
        elevation_change_m=preset.inlet_spec.elevation_change_m,
        local_loss_coefficient=preset.inlet_spec.local_loss_coefficient,
    )
    component.outlet_spec = ThermoSpec(
        pressure_mpa=preset.outlet_spec.pressure_mpa,
        temperature_c=preset.outlet_spec.temperature_c,
        enthalpy_kj_kg=preset.outlet_spec.enthalpy_kj_kg,
        entropy_kj_kgk=preset.outlet_spec.entropy_kj_kgk,
        quality=preset.outlet_spec.quality,
        specific_volume_m3_kg=preset.outlet_spec.specific_volume_m3_kg,
        efficiency=preset.outlet_spec.efficiency,
        heat_duty_kw=preset.outlet_spec.heat_duty_kw,
        pressure_drop_mpa=preset.outlet_spec.pressure_drop_mpa,
        mass_flow_kg_s=preset.outlet_spec.mass_flow_kg_s,
        pipe_length_m=preset.outlet_spec.pipe_length_m,
        pipe_outer_diameter_m=preset.outlet_spec.pipe_outer_diameter_m,
        pipe_wall_thickness_m=preset.outlet_spec.pipe_wall_thickness_m,
        pipe_roughness_m=preset.outlet_spec.pipe_roughness_m,
        elevation_change_m=preset.outlet_spec.elevation_change_m,
        local_loss_coefficient=preset.outlet_spec.local_loss_coefficient,
    )
    component.notes = preset.notes
