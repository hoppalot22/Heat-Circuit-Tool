from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from ..model import Circuit, ComponentKind, ProcessKind, ThermoSpec
from ..solver import CircuitSolution
from ..unit_system import best_prefixed_display, default_unit, from_internal, is_numeric_field, to_internal, unit_names


class ComponentInspector(ttk.Frame):
    field_specs = [
        ("name", "Name"),
        ("kind", "Component Type"),
        ("process_kind", "Process"),
        ("inlet_pressure_mpa", "Inlet Pressure"),
        ("inlet_temperature_c", "Inlet Temperature"),
        ("inlet_enthalpy_kj_kg", "Inlet Enthalpy"),
        ("inlet_entropy_kj_kgk", "Inlet Entropy"),
        ("inlet_quality", "Inlet Quality"),
        ("inlet_specific_volume_m3_kg", "Inlet Specific Volume"),
        ("inlet_efficiency", "Inlet Efficiency"),
        ("outlet_pressure_mpa", "Outlet Pressure"),
        ("outlet_temperature_c", "Outlet Temperature"),
        ("outlet_enthalpy_kj_kg", "Outlet Enthalpy"),
        ("outlet_entropy_kj_kgk", "Outlet Entropy"),
        ("outlet_quality", "Outlet Quality"),
        ("outlet_specific_volume_m3_kg", "Outlet Specific Volume"),
        ("outlet_efficiency", "Outlet Efficiency"),
        ("heat_duty_kw", "Heat Duty"),
        ("pressure_drop_mpa", "Pressure Drop"),
        ("mass_flow_kg_s", "Mass Flow"),
        ("pipe_length_m", "Pipe Length"),
        ("pipe_outer_diameter_m", "Pipe OD"),
        ("pipe_wall_thickness_m", "Pipe Wall Thickness"),
        ("pipe_roughness_m", "Pipe Roughness"),
        ("elevation_change_m", "Elevation Change"),
        ("local_loss_coefficient", "Local Loss Coefficient"),
        ("notes", "Notes"),
    ]

    _neutral_bg = "#fcfcfc"
    _solver_bg = "#d7e7f5"
    _input_bg = "#eadfb9"
    _conflict_bg = "#f0b4b4"

    def __init__(
        self,
        master: tk.Misc,
        circuit: Circuit,
        on_apply: Callable[[], None] | None = None,
        on_solve: Callable[[], None] | None = None,
        on_dirty: Callable[[], None] | None = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.circuit = circuit
        self.on_apply = on_apply
        self.on_solve = on_solve
        self.on_dirty = on_dirty
        self.current_component_id: Optional[str] = None
        self._vars: dict[str, tk.StringVar] = {}
        self._widgets: dict[str, tk.Widget] = {}
        self._colorable_fields: set[str] = set()
        self._unit_vars: dict[str, tk.StringVar] = {}
        self._unit_widgets: dict[str, ttk.Combobox] = {}
        self._unit_last: dict[str, str] = {}
        self._kind_values = [kind.value for kind in ComponentKind]
        self._process_values = [process.value for process in ProcessKind]
        self._loading = False
        self._solution_text = "Run the solver to see the cycle summary."
        self._build()

    def _build(self) -> None:
        for row, (field_name, label) in enumerate(self.field_specs):
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            var = tk.StringVar()
            self._vars[field_name] = var

            if field_name == "kind":
                widget: tk.Widget = ttk.Combobox(self, textvariable=var, values=self._kind_values, state="readonly", width=22)
                widget.bind("<<ComboboxSelected>>", lambda _e, f=field_name: self._on_any_field_modified(f))
                unit_widget = self._make_unit_placeholder(row)
            elif field_name == "process_kind":
                widget = ttk.Combobox(self, textvariable=var, values=self._process_values, state="readonly", width=22)
                widget.bind("<<ComboboxSelected>>", lambda _e, f=field_name: self._on_any_field_modified(f))
                unit_widget = self._make_unit_placeholder(row)
            elif field_name == "notes":
                widget = tk.Entry(self, textvariable=var, width=30, bg=self._neutral_bg)
                widget.bind("<KeyRelease>", lambda _e, f=field_name: self._on_any_field_modified(f))
                self._colorable_fields.add(field_name)
                unit_widget = self._make_unit_placeholder(row)
            else:
                widget = tk.Entry(self, textvariable=var, width=20, bg=self._neutral_bg)
                widget.bind("<KeyRelease>", lambda _e, f=field_name: self._on_any_field_modified(f))
                self._colorable_fields.add(field_name)
                unit_widget = self._make_unit_selector(row, field_name)

            widget.grid(row=row, column=1, sticky="ew", padx=4, pady=2)
            self._widgets[field_name] = widget
            self._unit_widgets[field_name] = unit_widget

        self.columnconfigure(1, weight=1)

        button_row = len(self.field_specs)
        ttk.Button(self, text="Apply to Component", command=self.apply_to_component).grid(row=button_row, column=0, columnspan=3, sticky="ew", padx=4, pady=(10, 2))
        ttk.Button(self, text="Solve Circuit", command=self.solve_requested).grid(row=button_row + 1, column=0, columnspan=3, sticky="ew", padx=4, pady=2)

    def _make_unit_placeholder(self, row: int) -> ttk.Combobox:
        unit_var = tk.StringVar(value="-")
        combo = ttk.Combobox(self, textvariable=unit_var, values=["-"], state="disabled", width=10)
        combo.grid(row=row, column=2, sticky="ew", padx=4, pady=2)
        return combo

    def _make_unit_selector(self, row: int, field_name: str) -> ttk.Combobox:
        units = unit_names(field_name)
        initial = default_unit(field_name)
        unit_var = tk.StringVar(value=initial)
        self._unit_vars[field_name] = unit_var
        self._unit_last[field_name] = initial
        combo = ttk.Combobox(self, textvariable=unit_var, values=units or ["-"], state="readonly", width=10)
        combo.grid(row=row, column=2, sticky="ew", padx=4, pady=2)
        combo.bind("<<ComboboxSelected>>", lambda _e, f=field_name: self._on_unit_changed(f))
        return combo

    def load_component(self, component_id: Optional[str]) -> None:
        self.current_component_id = component_id
        self._loading = True
        if component_id is None:
            for key, var in self._vars.items():
                var.set("")
                if key in self._colorable_fields:
                    widget = self._widgets.get(key)
                    if widget is not None:
                        widget.configure(bg=self._neutral_bg)
            self._loading = False
            return

        component = self.circuit.components[component_id]
        self._ensure_unit_prefs(component)

        values = {
            "name": component.name,
            "kind": component.kind.value,
            "process_kind": component.process_kind.value,
            "inlet_pressure_mpa": component.inlet_spec.pressure_mpa,
            "inlet_temperature_c": component.inlet_spec.temperature_c,
            "inlet_enthalpy_kj_kg": component.inlet_spec.enthalpy_kj_kg,
            "inlet_entropy_kj_kgk": component.inlet_spec.entropy_kj_kgk,
            "inlet_quality": component.inlet_spec.quality,
            "inlet_specific_volume_m3_kg": component.inlet_spec.specific_volume_m3_kg,
            "inlet_efficiency": component.inlet_spec.efficiency,
            "outlet_pressure_mpa": component.outlet_spec.pressure_mpa,
            "outlet_temperature_c": component.outlet_spec.temperature_c,
            "outlet_enthalpy_kj_kg": component.outlet_spec.enthalpy_kj_kg,
            "outlet_entropy_kj_kgk": component.outlet_spec.entropy_kj_kgk,
            "outlet_quality": component.outlet_spec.quality,
            "outlet_specific_volume_m3_kg": component.outlet_spec.specific_volume_m3_kg,
            "outlet_efficiency": component.outlet_spec.efficiency,
            "heat_duty_kw": component.outlet_spec.heat_duty_kw,
            "pressure_drop_mpa": component.outlet_spec.pressure_drop_mpa,
            "mass_flow_kg_s": component.outlet_spec.mass_flow_kg_s,
            "pipe_length_m": component.outlet_spec.pipe_length_m,
            "pipe_outer_diameter_m": component.outlet_spec.pipe_outer_diameter_m,
            "pipe_wall_thickness_m": component.outlet_spec.pipe_wall_thickness_m,
            "pipe_roughness_m": component.outlet_spec.pipe_roughness_m,
            "elevation_change_m": component.outlet_spec.elevation_change_m,
            "local_loss_coefficient": component.outlet_spec.local_loss_coefficient,
            "notes": component.notes,
        }

        for field_name, value in values.items():
            if field_name in self._unit_vars:
                unit = component.unit_preferences.get(field_name, default_unit(field_name))
                self._unit_vars[field_name].set(unit)
                self._unit_last[field_name] = unit
                numeric_value = self._coerce_float(value)
                if numeric_value is None:
                    self._vars[field_name].set("")
                else:
                    converted = from_internal(field_name, numeric_value, unit)
                    self._vars[field_name].set(self._format(converted))
            else:
                self._vars[field_name].set("" if value is None else str(value))

        self._apply_highlights(component)
        self._loading = False

    def apply_to_component(self) -> None:
        if self.current_component_id is None:
            return
        component = self.circuit.components[self.current_component_id]
        self._ensure_unit_prefs(component)
        component.name = self._vars["name"].get().strip() or component.name
        component.kind = ComponentKind(self._vars["kind"].get().strip() or component.kind.value)
        component.process_kind = ProcessKind(self._vars["process_kind"].get().strip() or component.process_kind.value)

        component.solved_fields.clear()

        component.inlet_spec = ThermoSpec(
            pressure_mpa=self._parse_and_track(component, "inlet_pressure_mpa"),
            temperature_c=self._parse_and_track(component, "inlet_temperature_c"),
            enthalpy_kj_kg=self._parse_and_track(component, "inlet_enthalpy_kj_kg"),
            entropy_kj_kgk=self._parse_and_track(component, "inlet_entropy_kj_kgk"),
            quality=self._parse_and_track(component, "inlet_quality"),
            specific_volume_m3_kg=self._parse_and_track(component, "inlet_specific_volume_m3_kg"),
            efficiency=self._parse_and_track(component, "inlet_efficiency"),
        )
        component.outlet_spec = ThermoSpec(
            pressure_mpa=self._parse_and_track(component, "outlet_pressure_mpa"),
            temperature_c=self._parse_and_track(component, "outlet_temperature_c"),
            enthalpy_kj_kg=self._parse_and_track(component, "outlet_enthalpy_kj_kg"),
            entropy_kj_kgk=self._parse_and_track(component, "outlet_entropy_kj_kgk"),
            quality=self._parse_and_track(component, "outlet_quality"),
            specific_volume_m3_kg=self._parse_and_track(component, "outlet_specific_volume_m3_kg"),
            efficiency=self._parse_and_track(component, "outlet_efficiency"),
            heat_duty_kw=self._parse_and_track(component, "heat_duty_kw"),
            pressure_drop_mpa=self._parse_and_track(component, "pressure_drop_mpa"),
            mass_flow_kg_s=self._parse_and_track(component, "mass_flow_kg_s"),
            pipe_length_m=self._parse_and_track(component, "pipe_length_m"),
            pipe_outer_diameter_m=self._parse_and_track(component, "pipe_outer_diameter_m"),
            pipe_wall_thickness_m=self._parse_and_track(component, "pipe_wall_thickness_m"),
            pipe_roughness_m=self._parse_and_track(component, "pipe_roughness_m"),
            elevation_change_m=self._parse_and_track(component, "elevation_change_m"),
            local_loss_coefficient=self._parse_and_track(component, "local_loss_coefficient"),
        )
        component.notes = self._vars["notes"].get().strip()
        component.is_dirty = True
        self._apply_highlights(component)
        if self.on_apply:
            self.on_apply()

    def apply_solution_to_component(
        self,
        component_id: str,
        inlet_state,
        outlet_state,
        conflicting_fields: list[str] | None = None,
    ) -> None:
        component = self.circuit.components.get(component_id)
        if component is None:
            return
        component.conflicting_fields = set(conflicting_fields or [])
        component.solved_fields.clear()

        def set_if_not_user(spec_obj, field_name: str, value: float | None, scoped_name: str) -> None:
            if scoped_name in component.user_input_fields:
                return
            setattr(spec_obj, field_name, value)
            component.solved_fields.add(scoped_name)

        if inlet_state is not None:
            set_if_not_user(component.inlet_spec, "pressure_mpa", inlet_state.pressure_mpa, "inlet_pressure_mpa")
            set_if_not_user(component.inlet_spec, "temperature_c", inlet_state.temperature_c, "inlet_temperature_c")
            set_if_not_user(component.inlet_spec, "enthalpy_kj_kg", inlet_state.enthalpy_kj_kg, "inlet_enthalpy_kj_kg")
            set_if_not_user(component.inlet_spec, "entropy_kj_kgk", inlet_state.entropy_kj_kgk, "inlet_entropy_kj_kgk")
            set_if_not_user(component.inlet_spec, "specific_volume_m3_kg", inlet_state.specific_volume_m3_kg, "inlet_specific_volume_m3_kg")
            set_if_not_user(component.inlet_spec, "quality", inlet_state.quality, "inlet_quality")
        if outlet_state is not None:
            set_if_not_user(component.outlet_spec, "pressure_mpa", outlet_state.pressure_mpa, "outlet_pressure_mpa")
            set_if_not_user(component.outlet_spec, "temperature_c", outlet_state.temperature_c, "outlet_temperature_c")
            set_if_not_user(component.outlet_spec, "enthalpy_kj_kg", outlet_state.enthalpy_kj_kg, "outlet_enthalpy_kj_kg")
            set_if_not_user(component.outlet_spec, "entropy_kj_kgk", outlet_state.entropy_kj_kgk, "outlet_entropy_kj_kgk")
            set_if_not_user(component.outlet_spec, "specific_volume_m3_kg", outlet_state.specific_volume_m3_kg, "outlet_specific_volume_m3_kg")
            set_if_not_user(component.outlet_spec, "quality", outlet_state.quality, "outlet_quality")
        if inlet_state is not None and outlet_state is not None:
            set_if_not_user(
                component.outlet_spec,
                "pressure_drop_mpa",
                max(0.0, inlet_state.pressure_mpa - outlet_state.pressure_mpa),
                "pressure_drop_mpa",
            )
        component.is_dirty = False
        if self.current_component_id == component_id:
            self.load_component(component_id)

    def show_solution(self, solution: CircuitSolution) -> None:
        text = ["Circuit Summary", "----------------"]
        text.extend(solution.summary_lines())
        text.append("")
        text.append("Component Reports")
        text.append("------------------")
        for result in solution.component_results:
            text.append(f"{result.component_name}: {result.status}")
            component = self.circuit.components.get(result.component_id)
            text.append("  Inlet: " + self._state_line(component, result.inlet_state, "inlet"))
            text.append("  Outlet: " + self._state_line(component, result.outlet_state, "outlet"))
            text.append(f"  Work: {result.work_kj_kg:.2f} kJ/kg | Heat: {result.heat_kj_kg:.2f} kJ/kg")
            if result.message:
                text.append(f"  {result.message}")
            text.append("")
        self._solution_text = "\n".join(text)

    def solution_text(self) -> str:
        return self._solution_text

    def _state_line(self, component, state, prefix: str) -> str:
        if state is None:
            return "Undeterminable"
        if component is None:
            return state.brief()
        fields = [
            (f"{prefix}_pressure_mpa", state.pressure_mpa),
            (f"{prefix}_temperature_c", state.temperature_c),
            (f"{prefix}_enthalpy_kj_kg", state.enthalpy_kj_kg),
            (f"{prefix}_entropy_kj_kgk", state.entropy_kj_kgk),
            (f"{prefix}_specific_volume_m3_kg", state.specific_volume_m3_kg),
        ]
        parts: list[str] = []
        for field_name, value in fields:
            preferred = component.unit_preferences.get(field_name, default_unit(field_name))
            best_value, best_unit = best_prefixed_display(field_name, value, preferred)
            label = field_name.replace(prefix + "_", "").replace("_", " ")
            parts.append(f"{label}={best_value:.4g} {best_unit}")
        if state.quality is not None:
            preferred = component.unit_preferences.get(f"{prefix}_quality", "fraction")
            best_value, best_unit = best_prefixed_display(f"{prefix}_quality", state.quality, preferred)
            parts.append(f"quality={best_value:.4g} {best_unit}")
        return ", ".join(parts)

    def _parse_and_track(self, component, field_name: str) -> float | None:
        raw = self._vars[field_name].get().strip()
        if not raw:
            component.user_input_fields.discard(field_name)
            return None
        try:
            number = float(raw)
        except ValueError:
            component.user_input_fields.discard(field_name)
            return None
        unit_name = component.unit_preferences.get(field_name, default_unit(field_name))
        return to_internal(field_name, number, unit_name)

    def _format(self, value: float | str | None) -> str:
        if value is None:
            return ""
        numeric = self._coerce_float(value)
        if numeric is None:
            return str(value)
        return f"{numeric:.6g}"

    def _coerce_float(self, value: float | str | None) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            try:
                return float(raw)
            except ValueError:
                return None
        return None

    def _ensure_unit_prefs(self, component) -> None:
        for field_name, _ in self.field_specs:
            if is_numeric_field(field_name):
                component.unit_preferences.setdefault(field_name, default_unit(field_name))

    def _on_unit_changed(self, field_name: str) -> None:
        if self._loading or self.current_component_id is None:
            return
        component = self.circuit.components[self.current_component_id]
        new_unit = self._unit_vars[field_name].get()
        old_unit = self._unit_last.get(field_name, new_unit)
        current_text = self._vars[field_name].get().strip()
        if current_text:
            try:
                current_value = float(current_text)
                internal = to_internal(field_name, current_value, old_unit)
                converted = from_internal(field_name, internal, new_unit)
                self._vars[field_name].set(self._format(converted))
            except ValueError:
                pass
        component.unit_preferences[field_name] = new_unit
        self._unit_last[field_name] = new_unit
        component.user_input_fields.add(field_name)
        self._clear_highlights_dirty(component)

    def _on_any_field_modified(self, field_name: str) -> None:
        if self._loading or self.current_component_id is None:
            return
        component = self.circuit.components[self.current_component_id]
        if is_numeric_field(field_name):
            component.user_input_fields.add(field_name)
        self._clear_highlights_dirty(component)

    def _clear_highlights_dirty(self, component) -> None:
        component.solved_fields.clear()
        component.conflicting_fields.clear()
        component.is_dirty = True
        self._apply_highlights(component)
        if self.on_dirty:
            self.on_dirty()

    def _apply_highlights(self, component) -> None:
        for field_name in self._colorable_fields:
            widget = self._widgets[field_name]
            color = self._neutral_bg
            if field_name in component.user_input_fields:
                color = self._input_bg
            if not component.is_dirty and field_name in component.solved_fields:
                color = self._solver_bg
            if field_name in component.conflicting_fields:
                color = self._conflict_bg
            widget.configure(bg=color)

    def solve_requested(self) -> None:
        if self.on_solve:
            self.on_solve()
