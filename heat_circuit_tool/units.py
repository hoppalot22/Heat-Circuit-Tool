from __future__ import annotations

from math import isclose

MPA_TO_PA = 1_000_000.0
KELVIN_OFFSET = 273.15


def c_to_k(value_c: float) -> float:
    return value_c + KELVIN_OFFSET


def k_to_c(value_k: float) -> float:
    return value_k - KELVIN_OFFSET


def mpa_to_pa(value_mpa: float) -> float:
    return value_mpa * MPA_TO_PA


def pa_to_mpa(value_pa: float) -> float:
    return value_pa / MPA_TO_PA


def almost_equal(left: float, right: float, tolerance: float = 1e-6) -> bool:
    return isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


def format_optional(value: float | None, precision: int = 3) -> str:
    if value is None:
        return "-"
    return f"{value:.{precision}f}"
