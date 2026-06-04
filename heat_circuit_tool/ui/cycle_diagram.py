from __future__ import annotations

from dataclasses import dataclass
from math import log10, sqrt
from typing import Optional

import tkinter as tk
from tkinter import ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D

from ..model import Circuit
from ..solver import CircuitSolution
from ..thermo import SteamPropertyBackend, ThermoState


@dataclass(slots=True)
class AxisSpec:
    key: str
    label: str


AXIS_OPTIONS = [
    AxisSpec("pressure_mpa", "Pressure (MPa)"),
    AxisSpec("temperature_c", "Temperature (C)"),
    AxisSpec("specific_volume_m3_kg", "Specific Volume (m^3/kg)"),
    AxisSpec("enthalpy_kj_kg", "Enthalpy (kJ/kg)"),
    AxisSpec("entropy_kj_kgk", "Entropy (kJ/kg-K)"),
]


class CycleDiagramPanel(ttk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.backend = SteamPropertyBackend()
        self._circuit: Optional[Circuit] = None
        self._solution: Optional[CircuitSolution] = None
        self._label_to_key = {spec.label: spec.key for spec in AXIS_OPTIONS}
        self._key_to_label = {spec.key: spec.label for spec in AXIS_OPTIONS}
        self._placed_label_points: list[tuple[float, float]] = []

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.Frame(self)
        controls.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        controls.columnconfigure(5, weight=1)

        self.x_axis_var = tk.StringVar(value=self._key_to_label["entropy_kj_kgk"])
        self.y_axis_var = tk.StringVar(value=self._key_to_label["temperature_c"])

        axis_labels = [spec.label for spec in AXIS_OPTIONS]
        ttk.Label(controls, text="X Axis").grid(row=0, column=0, sticky="w")
        self.x_combo = ttk.Combobox(controls, textvariable=self.x_axis_var, values=axis_labels, state="readonly", width=24)
        self.x_combo.grid(row=0, column=1, sticky="w", padx=(4, 10))

        ttk.Label(controls, text="Y Axis").grid(row=0, column=2, sticky="w")
        self.y_combo = ttk.Combobox(controls, textvariable=self.y_axis_var, values=axis_labels, state="readonly", width=24)
        self.y_combo.grid(row=0, column=3, sticky="w", padx=(4, 10))

        ttk.Button(controls, text="Redraw", command=self.redraw).grid(row=0, column=4, sticky="w")

        self.message_var = tk.StringVar(value="Run Solve to populate process states.")
        ttk.Label(controls, textvariable=self.message_var).grid(row=0, column=5, sticky="e")

        self.figure = Figure(figsize=(9, 6), dpi=100)
        self.ax = self.figure.add_subplot(111)
        self.ax.grid(True, alpha=0.3)

        self.canvas = FigureCanvasTkAgg(self.figure, self)
        self.canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self.x_combo.bind("<<ComboboxSelected>>", lambda _e: self.redraw())
        self.y_combo.bind("<<ComboboxSelected>>", lambda _e: self.redraw())

    def _logspace(self, start: float, stop: float, count: int) -> list[float]:
        if count <= 1:
            return [start]
        lo = log10(start)
        hi = log10(stop)
        step = (hi - lo) / float(count - 1)
        return [10.0 ** (lo + step * i) for i in range(count)]

    def set_solution(self, circuit: Circuit, solution: Optional[CircuitSolution]) -> None:
        self._circuit = circuit
        self._solution = solution
        self.redraw()

    def redraw(self) -> None:
        self.ax.clear()
        self.ax.grid(True, alpha=0.3)
        self._placed_label_points = []

        x_key = self._label_to_key[self.x_axis_var.get()]
        y_key = self._label_to_key[self.y_axis_var.get()]
        if x_key == y_key:
            self.message_var.set("Choose different properties for X and Y axes.")
            self._draw_labels(x_key, y_key)
            self.canvas.draw_idle()
            return

        self._draw_labels(x_key, y_key)
        self._plot_property_isolines(x_key, y_key)
        self._plot_quality_isolines(x_key, y_key)
        self._plot_solution_states(x_key, y_key)
        self._draw_legend()
        self.canvas.draw_idle()

    def _draw_labels(self, x_key: str, y_key: str) -> None:
        self.ax.set_xlabel(self._axis_label(x_key))
        self.ax.set_ylabel(self._axis_label(y_key))
        self.ax.set_title("Cycle Diagram")

    def _axis_label(self, key: str) -> str:
        for spec in AXIS_OPTIONS:
            if spec.key == key:
                return spec.label
        return key

    def _value(self, state: ThermoState, key: str) -> float:
        return float(getattr(state, key))

    def _is_far_from_labels(self, x: float, y: float, x_span: float, y_span: float) -> bool:
        min_dx = 0.035 * max(x_span, 1.0)
        min_dy = 0.035 * max(y_span, 1.0)
        for lx, ly in self._placed_label_points:
            if abs(x - lx) < min_dx and abs(y - ly) < min_dy:
                return False
        return True

    def _place_label_near(
        self,
        base_x: float,
        base_y: float,
        text: str,
        color: str = "#2a2a2a",
        fontsize: int = 8,
        align: str = "center",
    ) -> None:
        x_min, x_max = self.ax.get_xlim()
        y_min, y_max = self.ax.get_ylim()
        x_span = max(abs(x_max - x_min), 1.0)
        y_span = max(abs(y_max - y_min), 1.0)
        candidates = [
            (0.0, 0.0),
            (0.012 * x_span, 0.012 * y_span),
            (-0.012 * x_span, 0.012 * y_span),
            (0.012 * x_span, -0.012 * y_span),
            (-0.012 * x_span, -0.012 * y_span),
            (0.02 * x_span, 0.0),
            (-0.02 * x_span, 0.0),
        ]
        for dx, dy in candidates:
            cx = base_x + dx
            cy = base_y + dy
            if self._is_far_from_labels(cx, cy, x_span, y_span):
                self.ax.annotate(text, (cx, cy), fontsize=fontsize, alpha=0.92, color=color, ha=align)
                self._placed_label_points.append((cx, cy))
                return
        self.ax.annotate(text, (base_x, base_y), fontsize=fontsize, alpha=0.85, color=color, ha=align)
        self._placed_label_points.append((base_x, base_y))

    def _draw_legend(self) -> None:
        handles = [
            Line2D([0], [0], color="#1f77b4", lw=2.0, label="Process path"),
            Line2D([0], [0], marker="o", markersize=5, linestyle="None", color="#1f77b4", label="State point"),
            Line2D([0], [0], marker="o", markersize=6, linestyle="None", markerfacecolor="#ffd166", markeredgecolor="#111111", color="#111111", label="Inter-component point"),
            Line2D([0], [0], color="#8c8c8c", lw=0.9, ls="--", label="Property isolines"),
            Line2D([0], [0], color="#b56576", lw=0.9, ls="-", label="Steam quality isolines"),
        ]
        self.ax.legend(handles=handles, loc="upper right", fontsize=8, framealpha=0.92)

    def _plot_solution_states(self, x_key: str, y_key: str) -> None:
        if self._solution is None or self._circuit is None:
            self.message_var.set("Run Solve to populate process states.")
            return

        plotted_any = False
        point_index = 1
        for result in self._solution.component_results:
            inlet = result.inlet_state
            outlet = result.outlet_state
            if inlet is not None and outlet is not None:
                x1 = self._value(inlet, x_key)
                y1 = self._value(inlet, y_key)
                x2 = self._value(outlet, x_key)
                y2 = self._value(outlet, y_key)
                self.ax.plot([x1, x2], [y1, y2], color="#1f77b4", linewidth=2.0)
                self.ax.scatter([x1, x2], [y1, y2], s=20, color="#1f77b4")

                dx = x2 - x1
                dy = y2 - y1
                norm = sqrt(dx * dx + dy * dy)
                mid_x = 0.5 * (x1 + x2)
                mid_y = 0.5 * (y1 + y2)
                if norm > 1e-12:
                    nx = -dy / norm
                    ny = dx / norm
                else:
                    nx = 0.0
                    ny = 1.0
                x_min, x_max = self.ax.get_xlim()
                y_min, y_max = self.ax.get_ylim()
                x_scale = max(abs(x_max - x_min), 1.0)
                y_scale = max(abs(y_max - y_min), 1.0)
                label_x = mid_x + nx * x_scale * 0.01
                label_y = mid_y + ny * y_scale * 0.01
                self._place_label_near(label_x, label_y, result.component_name, color="#23395d", fontsize=8)
                plotted_any = True

            if outlet is not None and self._circuit is not None:
                for downstream_id in self._circuit.outgoing(result.component_id):
                    x = self._value(outlet, x_key)
                    y = self._value(outlet, y_key)
                    self.ax.scatter([x], [y], s=36, marker="o", edgecolor="#111111", facecolor="#ffd166", zorder=5)
                    self.ax.annotate(str(point_index), (x, y), fontsize=7, color="#111111")
                    point_index += 1
                    plotted_any = True

        if plotted_any:
            self.message_var.set("Showing solved process paths and inter-component points.")
        else:
            self.message_var.set("No solved states available yet.")

    def _plot_property_isolines(self, x_key: str, y_key: str) -> None:
        excluded = {x_key, y_key}
        for key in ["pressure_mpa", "temperature_c", "specific_volume_m3_kg", "enthalpy_kj_kg", "entropy_kj_kgk"]:
            if key in excluded:
                continue
            if key == "pressure_mpa":
                self._plot_iso_pressure_lines(x_key, y_key)
            elif key == "temperature_c":
                self._plot_iso_temperature_lines(x_key, y_key)
            elif key == "enthalpy_kj_kg":
                self._plot_iso_enthalpy_lines(x_key, y_key)
            elif key == "entropy_kj_kgk":
                self._plot_iso_entropy_lines(x_key, y_key)
            elif key == "specific_volume_m3_kg":
                self._plot_iso_specific_volume_lines(x_key, y_key)

    def _plot_iso_pressure_lines(self, x_key: str, y_key: str) -> None:
        pressures = self._logspace(0.01, 22.0, 12)
        for index, pressure in enumerate(pressures):
            xs: list[float] = []
            ys: list[float] = []
            for temp in range(20, 801, 10):
                try:
                    state = self.backend.state_from_pressure_temperature(pressure, float(temp))
                except Exception:
                    continue
                xs.append(self._value(state, x_key))
                ys.append(self._value(state, y_key))
            if len(xs) > 1:
                self.ax.plot(xs, ys, linestyle="--", linewidth=0.8, alpha=0.35, color="#8c8c8c")
                if index % 2 == 0:
                    sample_idx = int(0.62 * (len(xs) - 1))
                    self._place_label_near(xs[sample_idx], ys[sample_idx], f"{pressure:.3g} MPa", color="#666666", fontsize=7)

    def _plot_iso_temperature_lines(self, x_key: str, y_key: str) -> None:
        temperatures = [40.0, 80.0, 120.0, 160.0, 200.0, 250.0, 300.0, 350.0, 400.0, 500.0, 600.0]
        pressures = self._logspace(0.01, 22.0, 32)
        for temperature in temperatures:
            xs: list[float] = []
            ys: list[float] = []
            for pressure in pressures:
                try:
                    state = self.backend.state_from_pressure_temperature(pressure, temperature)
                except Exception:
                    continue
                xs.append(self._value(state, x_key))
                ys.append(self._value(state, y_key))
            if len(xs) > 1:
                self.ax.plot(xs, ys, linestyle=":", linewidth=0.8, alpha=0.35, color="#7a7a7a")

    def _plot_iso_enthalpy_lines(self, x_key: str, y_key: str) -> None:
        enthalpies = [300.0, 600.0, 900.0, 1200.0, 1500.0, 1800.0, 2100.0, 2400.0, 2700.0, 3000.0, 3300.0]
        pressures = self._logspace(0.01, 22.0, 30)
        for enthalpy in enthalpies:
            xs: list[float] = []
            ys: list[float] = []
            for pressure in pressures:
                try:
                    state = self.backend.state_from_pressure_enthalpy(pressure, enthalpy)
                except Exception:
                    continue
                xs.append(self._value(state, x_key))
                ys.append(self._value(state, y_key))
            if len(xs) > 1:
                self.ax.plot(xs, ys, linestyle="-.", linewidth=0.8, alpha=0.35, color="#6a6a6a")

    def _plot_iso_entropy_lines(self, x_key: str, y_key: str) -> None:
        entropies = [0.8, 1.2, 1.6, 2.0, 2.4, 2.8, 3.2, 3.6, 4.0, 4.4, 4.8, 5.2, 5.6, 6.0, 6.4, 6.8, 7.2]
        pressures = self._logspace(0.01, 22.0, 30)
        for entropy in entropies:
            xs: list[float] = []
            ys: list[float] = []
            for pressure in pressures:
                try:
                    state = self.backend.state_from_pressure_entropy(pressure, entropy)
                except Exception:
                    continue
                xs.append(self._value(state, x_key))
                ys.append(self._value(state, y_key))
            if len(xs) > 1:
                self.ax.plot(xs, ys, linestyle="-", linewidth=0.8, alpha=0.25, color="#5a5a5a")

    def _plot_iso_specific_volume_lines(self, x_key: str, y_key: str) -> None:
        target_volumes = [0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0]
        pressures = self._logspace(0.01, 22.0, 26)
        for volume in target_volumes:
            xs: list[float] = []
            ys: list[float] = []
            for pressure in pressures:
                state = self._solve_state_from_pressure_volume(pressure, volume)
                if state is None:
                    continue
                xs.append(self._value(state, x_key))
                ys.append(self._value(state, y_key))
            if len(xs) > 1:
                self.ax.plot(xs, ys, linestyle="--", linewidth=0.8, alpha=0.25, color="#505050")

    def _solve_state_from_pressure_volume(self, pressure_mpa: float, target_v: float) -> ThermoState | None:
        low = 5.0
        high = 800.0
        try:
            low_state = self.backend.state_from_pressure_temperature(pressure_mpa, low)
            high_state = self.backend.state_from_pressure_temperature(pressure_mpa, high)
        except Exception:
            return None

        low_error = low_state.specific_volume_m3_kg - target_v
        high_error = high_state.specific_volume_m3_kg - target_v
        if low_error == 0.0:
            return low_state
        if high_error == 0.0:
            return high_state
        if low_error * high_error > 0.0:
            return None

        candidate = None
        for _ in range(52):
            mid = 0.5 * (low + high)
            try:
                candidate = self.backend.state_from_pressure_temperature(pressure_mpa, mid)
            except Exception:
                return None
            error = candidate.specific_volume_m3_kg - target_v
            if abs(error) < 1e-7:
                return candidate
            if error * low_error > 0.0:
                low = mid
                low_error = error
            else:
                high = mid
                high_error = error
        return candidate

    def _plot_quality_isolines(self, x_key: str, y_key: str) -> None:
        qualities = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
        pressures = self._logspace(0.001, 22.0, 36)
        for quality in qualities:
            xs: list[float] = []
            ys: list[float] = []
            for pressure in pressures:
                try:
                    state = self.backend.state_from_pressure_quality(pressure, quality)
                except Exception:
                    continue
                xs.append(self._value(state, x_key))
                ys.append(self._value(state, y_key))
            if len(xs) > 1:
                self.ax.plot(xs, ys, linestyle="-", linewidth=0.9, alpha=0.5, color="#b56576")
