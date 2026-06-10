from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def _venv_python_executable() -> Path:
    root = Path(__file__).resolve().parent
    return root / ".venv" / "Scripts" / "python.exe"


def _reexec_with_venv_if_available() -> None:
    if os.environ.get("HEAT_CIRCUIT_TOOL_REEXEC") == "1":
        return
    venv_python = _venv_python_executable()
    if not venv_python.exists():
        return
    env = os.environ.copy()
    env["HEAT_CIRCUIT_TOOL_REEXEC"] = "1"
    cmd = [str(venv_python), __file__, *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd, env=env))

try:
    from heat_circuit_tool.ui.main_window import run_app
except ModuleNotFoundError as exc:
    missing = getattr(exc, "name", "")
    if missing == "iapws":
        _reexec_with_venv_if_available()
        raise SystemExit(
            "Missing dependency 'iapws' for this Python interpreter.\n"
            "Install dependencies in the same interpreter used to launch this script:\n"
            f"  {sys.executable} -m pip install -r requirements.txt"
        ) from exc
    raise


if __name__ == "__main__":
    run_app()
