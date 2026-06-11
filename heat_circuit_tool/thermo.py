from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Any, Optional

from iapws import IAPWS97

from .units import c_to_k, k_to_c


@dataclass(slots=True)
class ThermoState:
    pressure_mpa: float
    temperature_c: float
    enthalpy_kj_kg: float
    entropy_kj_kgk: float
    specific_volume_m3_kg: float
    dynamic_viscosity_pa_s: Optional[float] = None
    quality: Optional[float] = None

    def as_dict(self) -> dict[str, float | None]:
        return {
            "pressure_mpa": self.pressure_mpa,
            "temperature_c": self.temperature_c,
            "enthalpy_kj_kg": self.enthalpy_kj_kg,
            "entropy_kj_kgk": self.entropy_kj_kgk,
            "specific_volume_m3_kg": self.specific_volume_m3_kg,
            "dynamic_viscosity_pa_s": self.dynamic_viscosity_pa_s,
            "quality": self.quality,
        }

    def brief(self) -> str:
        quality_part = ""
        if self.quality is not None:
            quality_part = f", x={self.quality:.4f}"
        return (
            f"P={self.pressure_mpa:.4f} MPa, T={self.temperature_c:.2f} C, "
            f"h={self.enthalpy_kj_kg:.2f} kJ/kg, s={self.entropy_kj_kgk:.4f} kJ/kg-K"
            f"{quality_part}"
        )

    @property
    def temperature_k(self) -> float:
        return c_to_k(self.temperature_c)

    @property
    def density_kg_m3(self) -> float:
        if self.specific_volume_m3_kg <= 0.0:
            return 0.0
        return 1.0 / self.specific_volume_m3_kg


@dataclass(slots=True)
class StateSpec:
    pressure_mpa: float | None = None
    temperature_c: float | None = None
    enthalpy_kj_kg: float | None = None
    entropy_kj_kgk: float | None = None
    quality: float | None = None
    specific_volume_m3_kg: float | None = None

    def defined_fields(self) -> list[str]:
        result: list[str] = []
        for name in (
            "pressure_mpa",
            "temperature_c",
            "enthalpy_kj_kg",
            "entropy_kj_kgk",
            "quality",
            "specific_volume_m3_kg",
        ):
            if getattr(self, name) is not None:
                result.append(name)
        return result

    def is_empty(self) -> bool:
        return not self.defined_fields()

    def pretty(self) -> str:
        fields = []
        if self.pressure_mpa is not None:
            fields.append(f"P={self.pressure_mpa:.4f} MPa")
        if self.temperature_c is not None:
            fields.append(f"T={self.temperature_c:.2f} C")
        if self.enthalpy_kj_kg is not None:
            fields.append(f"h={self.enthalpy_kj_kg:.2f} kJ/kg")
        if self.entropy_kj_kgk is not None:
            fields.append(f"s={self.entropy_kj_kgk:.4f} kJ/kg-K")
        if self.quality is not None:
            fields.append(f"x={self.quality:.4f}")
        if self.specific_volume_m3_kg is not None:
            fields.append(f"v={self.specific_volume_m3_kg:.6f} m3/kg")
        return ", ".join(fields) if fields else "(unspecified)"


def state_to_dict(state: ThermoState | None) -> dict | None:
    if state is None:
        return None
    return {
        "pressure_mpa": state.pressure_mpa,
        "temperature_c": state.temperature_c,
        "enthalpy_kj_kg": state.enthalpy_kj_kg,
        "entropy_kj_kgk": state.entropy_kj_kgk,
        "specific_volume_m3_kg": state.specific_volume_m3_kg,
        "dynamic_viscosity_pa_s": state.dynamic_viscosity_pa_s,
        "quality": state.quality,
    }


def state_from_dict(data: dict | None) -> ThermoState | None:
    if data is None:
        return None
    return ThermoState(
        pressure_mpa=float(data.get("pressure_mpa", 0.0)),
        temperature_c=float(data.get("temperature_c", 0.0)),
        enthalpy_kj_kg=float(data.get("enthalpy_kj_kg", 0.0)),
        entropy_kj_kgk=float(data.get("entropy_kj_kgk", 0.0)),
        specific_volume_m3_kg=float(data.get("specific_volume_m3_kg", 0.0)),
        dynamic_viscosity_pa_s=data.get("dynamic_viscosity_pa_s"),
        quality=data.get("quality"),
    )


class SteamPropertyBackend:
    """Thin wrapper around IAPWS97 with unit conversions and friendly errors."""

    supported_pairs = {
        frozenset({"pressure_mpa", "temperature_c"}),
        frozenset({"pressure_mpa", "enthalpy_kj_kg"}),
        frozenset({"pressure_mpa", "entropy_kj_kgk"}),
        frozenset({"pressure_mpa", "quality"}),
        frozenset({"temperature_c", "enthalpy_kj_kg"}),
        frozenset({"temperature_c", "entropy_kj_kgk"}),
        frozenset({"temperature_c", "quality"}),
    }

    def make_state(self, spec: StateSpec) -> ThermoState:
        fields = spec.defined_fields()
        if len(fields) < 2:
            raise ValueError("At least two independent properties are required to define a steam state.")

        pair = frozenset(fields[:2])
        if pair not in self.supported_pairs:
            raise ValueError(
                "Unsupported property pair: " + ", ".join(sorted(pair))
            )

        kwargs: dict[str, Any] = {}
        if spec.pressure_mpa is not None:
            kwargs["P"] = spec.pressure_mpa
        if spec.temperature_c is not None:
            kwargs["T"] = c_to_k(spec.temperature_c)
        if spec.enthalpy_kj_kg is not None:
            kwargs["h"] = spec.enthalpy_kj_kg
        if spec.entropy_kj_kgk is not None:
            kwargs["s"] = spec.entropy_kj_kgk
        if spec.quality is not None:
            kwargs["x"] = spec.quality

        try:
            water = IAPWS97(**kwargs)
        except Exception as exc:  # pragma: no cover - friendly runtime error path
            raise ValueError(f"Steam property solve failed for {spec.pretty()}: {exc}") from exc
        return self._to_state(water)

    def state_from_pressure_temperature(self, pressure_mpa: float, temperature_c: float) -> ThermoState:
        return self.make_state(StateSpec(pressure_mpa=pressure_mpa, temperature_c=temperature_c))

    def state_from_pressure_enthalpy(self, pressure_mpa: float, enthalpy_kj_kg: float) -> ThermoState:
        return self.make_state(StateSpec(pressure_mpa=pressure_mpa, enthalpy_kj_kg=enthalpy_kj_kg))

    def state_from_pressure_entropy(self, pressure_mpa: float, entropy_kj_kgk: float) -> ThermoState:
        return self.make_state(StateSpec(pressure_mpa=pressure_mpa, entropy_kj_kgk=entropy_kj_kgk))

    def state_from_pressure_quality(self, pressure_mpa: float, quality: float) -> ThermoState:
        return self.make_state(StateSpec(pressure_mpa=pressure_mpa, quality=quality))

    def _to_state(self, water: Any) -> ThermoState:
        quality: Optional[float]
        dynamic_viscosity: Optional[float]
        try:
            quality = float(water.x) if water.x is not None else None
        except Exception:
            quality = None
        try:
            dynamic_viscosity = float(water.mu)
        except Exception:
            dynamic_viscosity = None
        return ThermoState(
            pressure_mpa=float(water.P),
            temperature_c=k_to_c(float(water.T)),
            enthalpy_kj_kg=float(water.h),
            entropy_kj_kgk=float(water.s),
            specific_volume_m3_kg=float(water.v),
            dynamic_viscosity_pa_s=dynamic_viscosity,
            quality=quality,
        )

    def same_state(self, left: ThermoState, right: ThermoState, tolerance: float = 1e-4) -> bool:
        return (
            isclose(left.pressure_mpa, right.pressure_mpa, rel_tol=tolerance, abs_tol=tolerance)
            and isclose(left.enthalpy_kj_kg, right.enthalpy_kj_kg, rel_tol=tolerance, abs_tol=tolerance)
            and isclose(left.entropy_kj_kgk, right.entropy_kj_kgk, rel_tol=tolerance, abs_tol=tolerance)
        )
