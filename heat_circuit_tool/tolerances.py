"""Centralised numerical tolerances used throughout the solver."""

# State matching tolerances
PRESSURE_TOL: float = 1e-5
TEMPERATURE_TOL: float = 1e-3
ENTHALPY_TOL: float = 1e-2
ENTROPY_TOL: float = 1e-4
SPECIFIC_VOLUME_TOL: float = 1e-7
QUALITY_TOL: float = 1e-4
PRESSURE_DROP_TOL: float = 1e-5

# Closure tolerances
CLOSURE_ENTHALPY_TOL: float = 1e-3
CLOSURE_PRESSURE_TOL: float = 1e-4

# State change detection
STATE_CHANGE_TOL: float = 1e-5

# Bisection solver
BISECTION_CONVERGENCE: float = 1e-6
BISECTION_MAX_ITERATIONS: int = 80

# Isochoric solver
ISOCHORIC_CONVERGENCE: float = 1e-8
ISOCHORIC_MAX_ITERATIONS: int = 60