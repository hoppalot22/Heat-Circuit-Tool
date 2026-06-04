from __future__ import annotations

import sys

try:
    from heat_circuit_tool.ui.main_window import run_app
except ModuleNotFoundError as exc:
    missing = getattr(exc, "name", "")
    if missing == "iapws":
        raise SystemExit(
            "Missing dependency 'iapws' for this Python interpreter.\n"
            "Install dependencies in the same interpreter used to launch this script:\n"
            f"  {sys.executable} -m pip install -r requirements.txt"
        ) from exc
    raise


if __name__ == "__main__":
    run_app()
