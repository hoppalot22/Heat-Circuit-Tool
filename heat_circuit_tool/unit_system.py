from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class UnitDef:
    name: str
    to_internal: Callable[[float], float]
    from_internal: Callable[[float], float]


FIELD_UNITS: dict[str, list[UnitDef]] = {
    "inlet_pressure_mpa": [
        UnitDef("MPa", lambda v: v, lambda v: v),
        UnitDef("kPa", lambda v: v / 1000.0, lambda v: v * 1000.0),
        UnitDef("Pa", lambda v: v / 1_000_000.0, lambda v: v * 1_000_000.0),
    ],
    "outlet_pressure_mpa": [
        UnitDef("MPa", lambda v: v, lambda v: v),
        UnitDef("kPa", lambda v: v / 1000.0, lambda v: v * 1000.0),
        UnitDef("Pa", lambda v: v / 1_000_000.0, lambda v: v * 1_000_000.0),
    ],
    "pressure_drop_mpa": [
        UnitDef("MPa", lambda v: v, lambda v: v),
        UnitDef("kPa", lambda v: v / 1000.0, lambda v: v * 1000.0),
        UnitDef("Pa", lambda v: v / 1_000_000.0, lambda v: v * 1_000_000.0),
    ],
    "inlet_temperature_c": [
        UnitDef("C", lambda v: v, lambda v: v),
        UnitDef("K", lambda v: v - 273.15, lambda v: v + 273.15),
    ],
    "outlet_temperature_c": [
        UnitDef("C", lambda v: v, lambda v: v),
        UnitDef("K", lambda v: v - 273.15, lambda v: v + 273.15),
    ],
    "inlet_enthalpy_kj_kg": [
        UnitDef("kJ/kg", lambda v: v, lambda v: v),
        UnitDef("J/kg", lambda v: v / 1000.0, lambda v: v * 1000.0),
        UnitDef("MJ/kg", lambda v: v * 1000.0, lambda v: v / 1000.0),
    ],
    "outlet_enthalpy_kj_kg": [
        UnitDef("kJ/kg", lambda v: v, lambda v: v),
        UnitDef("J/kg", lambda v: v / 1000.0, lambda v: v * 1000.0),
        UnitDef("MJ/kg", lambda v: v * 1000.0, lambda v: v / 1000.0),
    ],
    "inlet_entropy_kj_kgk": [
        UnitDef("kJ/kg-K", lambda v: v, lambda v: v),
        UnitDef("J/kg-K", lambda v: v / 1000.0, lambda v: v * 1000.0),
    ],
    "outlet_entropy_kj_kgk": [
        UnitDef("kJ/kg-K", lambda v: v, lambda v: v),
        UnitDef("J/kg-K", lambda v: v / 1000.0, lambda v: v * 1000.0),
    ],
    "inlet_specific_volume_m3_kg": [
        UnitDef("m3/kg", lambda v: v, lambda v: v),
        UnitDef("L/kg", lambda v: v / 1000.0, lambda v: v * 1000.0),
    ],
    "outlet_specific_volume_m3_kg": [
        UnitDef("m3/kg", lambda v: v, lambda v: v),
        UnitDef("L/kg", lambda v: v / 1000.0, lambda v: v * 1000.0),
    ],
    "inlet_quality": [UnitDef("fraction", lambda v: v, lambda v: v)],
    "outlet_quality": [UnitDef("fraction", lambda v: v, lambda v: v)],
    "inlet_efficiency": [UnitDef("fraction", lambda v: v, lambda v: v), UnitDef("%", lambda v: v / 100.0, lambda v: v * 100.0)],
    "outlet_efficiency": [UnitDef("fraction", lambda v: v, lambda v: v), UnitDef("%", lambda v: v / 100.0, lambda v: v * 100.0)],
    "heat_duty_kw": [
        UnitDef("kW", lambda v: v, lambda v: v),
        UnitDef("W", lambda v: v / 1000.0, lambda v: v * 1000.0),
        UnitDef("MW", lambda v: v * 1000.0, lambda v: v / 1000.0),
    ],
    "mass_flow_kg_s": [
        UnitDef("kg/s", lambda v: v, lambda v: v),
        UnitDef("g/s", lambda v: v / 1000.0, lambda v: v * 1000.0),
        UnitDef("t/h", lambda v: v / 3.6, lambda v: v * 3.6),
    ],
    "pipe_length_m": [UnitDef("m", lambda v: v, lambda v: v), UnitDef("mm", lambda v: v / 1000.0, lambda v: v * 1000.0)],
    "pipe_outer_diameter_m": [UnitDef("m", lambda v: v, lambda v: v), UnitDef("mm", lambda v: v / 1000.0, lambda v: v * 1000.0)],
    "pipe_wall_thickness_m": [UnitDef("m", lambda v: v, lambda v: v), UnitDef("mm", lambda v: v / 1000.0, lambda v: v * 1000.0)],
    "pipe_roughness_m": [UnitDef("m", lambda v: v, lambda v: v), UnitDef("mm", lambda v: v / 1000.0, lambda v: v * 1000.0), UnitDef("um", lambda v: v / 1_000_000.0, lambda v: v * 1_000_000.0)],
    "elevation_change_m": [UnitDef("m", lambda v: v, lambda v: v), UnitDef("mm", lambda v: v / 1000.0, lambda v: v * 1000.0)],
    "local_loss_coefficient": [UnitDef("-", lambda v: v, lambda v: v)],
}


def unit_names(field_name: str) -> list[str]:
    return [unit.name for unit in FIELD_UNITS.get(field_name, [])]


def default_unit(field_name: str) -> str:
    names = unit_names(field_name)
    return names[0] if names else "-"


def to_internal(field_name: str, value: float, unit_name: str) -> float:
    for unit in FIELD_UNITS.get(field_name, []):
        if unit.name == unit_name:
            return unit.to_internal(value)
    return value


def from_internal(field_name: str, value: float, unit_name: str) -> float:
    for unit in FIELD_UNITS.get(field_name, []):
        if unit.name == unit_name:
            return unit.from_internal(value)
    return value


def is_numeric_field(field_name: str) -> bool:
    return field_name in FIELD_UNITS


def best_prefixed_display(field_name: str, internal_value: float, preferred_unit: str) -> tuple[float, str]:
    units = FIELD_UNITS.get(field_name, [])
    if not units:
        return internal_value, preferred_unit

    preferred_family_names = {unit.name for unit in units}
    if preferred_unit not in preferred_family_names:
        preferred_unit = units[0].name

    preferred_value = from_internal(field_name, internal_value, preferred_unit)
    if preferred_value == 0.0:
        return preferred_value, preferred_unit
    if 0.1 <= abs(preferred_value) < 1000.0:
        return preferred_value, preferred_unit

    best_value = preferred_value
    best_unit = preferred_unit
    best_score = abs(len(f"{preferred_value:.3g}"))

    for unit in units:
        candidate = from_internal(field_name, internal_value, unit.name)
        if candidate == 0.0:
            score = 1.0
        else:
            magnitude = abs(candidate)
            if 0.1 <= magnitude < 1000.0:
                score = 0.0
            else:
                score = abs(len(f"{candidate:.3g}"))
        if score < best_score:
            best_score = score
            best_value = candidate
            best_unit = unit.name
    return best_value, best_unit
