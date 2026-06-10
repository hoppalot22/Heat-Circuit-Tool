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
        ("inlet_definition_mode", "Inlet Definition"),
        ("inlet_pressure_mpa", "Inlet Pressure"),
        ("inlet_temperature_c", "Inlet Temperature"),
        ("inlet_enthalpy_kj_kg", "Inlet Enthalpy"),
        ("inlet_entropy_kj_kgk", "Inlet Entropy"),
        ("inlet_quality", "Inlet Quality"),
        ("inlet_specific_volume_m3_kg", "Inlet Specific Volume"),
        ("inlet_efficiency", "Inlet Efficiency"),
        ("outlet_definition_mode", "Outlet Definition"),
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

    _base_fields = {"name", "kind", "process_kind", "notes"}
    _definition_fields = {"inlet_definition_mode", "outlet_definition_mode"}
    _inlet_state_fields = {
        "inlet_pressure_mpa",
        "inlet_temperature_c",
        "inlet_enthalpy_kj_kg",
        "inlet_entropy_kj_kgk",
        "inlet_quality",
        "inlet_specific_volume_m3_kg",
    }
    _outlet_state_fields = {
        "outlet_pressure_mpa",
        "outlet_temperature_c",
        "outlet_enthalpy_kj_kg",
        "outlet_entropy_kj_kgk",
        "outlet_quality",
        "outlet_specific_volume_m3_kg",
    }
    _definition_mode_map: dict[str, tuple[str, ...]] = {
        "Auto": (
            "pressure_mpa",
            "temperature_c",
            "enthalpy_kj_kg",
            "entropy_kj_kgk",
            "quality",
            "specific_volume_m3_kg",
        ),
        "P + T": ("pressure_mpa", "temperature_c"),
        "P + h": ("pressure_mpa", "enthalpy_kj_kg"),
        "P + s": ("pressure_mpa", "entropy_kj_kgk"),
        "P + x": ("pressure_mpa", "quality"),
        "T + h": ("temperature_c", "enthalpy_kj_kg"),
        "T + s": ("temperature_c", "entropy_kj_kgk"),
        "T + x": ("temperature_c", "quality"),
        "P + T + x": ("pressure_mpa", "temperature_c", "quality"),
    }
    _state_fields = {
        "inlet_pressure_mpa",
        "inlet_temperature_c",
        "inlet_enthalpy_kj_kg",
        "inlet_entropy_kj_kgk",
        "inlet_quality",
        "inlet_specific_volume_m3_kg",
        "outlet_pressure_mpa",
        "outlet_temperature_c",
        "outlet_enthalpy_kj_kg",
        "outlet_entropy_kj_kgk",
        "outlet_quality",
        "outlet_specific_volume_m3_kg",
    }
    _pipe_fields = {
        "mass_flow_kg_s",
        "pipe_length_m",
        "pipe_outer_diameter_m",
        "pipe_wall_thickness_m",
        "pipe_roughness_m",
        "elevation_change_m",
        "local_loss_coefficient",
        "pressure_drop_mpa",
        "outlet_pressure_mpa",
    }

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
        self._labels: dict[str, ttk.Label] = {}
        self._widgets: dict[str, tk.Widget] = {}
        self._colorable_fields: set[str] = set()
        self._unit_vars: dict[str, tk.StringVar] = {}
        self._unit_widgets: dict[str, ttk.Combobox] = {}
        self._unit_last: dict[str, str] = {}
        self._active_fields: set[str] = set(self._base_fields)
        self._kind_values = [kind.value for kind in ComponentKind]
        self._process_values = [process.value for process in ProcessKind]
        self._definition_modes = list(self._definition_mode_map.keys())
        self._loading = False
        self._solution_text = "Run the solver to see the cycle summary."
        self._build()

    def _build(self) -> None:
        for row, (field_name, label) in enumerate(self.field_specs):
            label_widget = ttk.Label(self, text=label)
            label_widget.grid(row=row, column=0, sticky="w", padx=4, pady=2)
            self._labels[field_name] = label_widget
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
            elif field_name in {"inlet_definition_mode", "outlet_definition_mode"}:
                widget = ttk.Combobox(self, textvariable=var, values=self._definition_modes, state="readonly", width=22)
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

    def _definition_fields_for_mode(self, prefix: str, mode: str) -> set[str]:
        suffixes = self._definition_mode_map.get(mode, self._definition_mode_map["Auto"])
        return {f"{prefix}_{suffix}" for suffix in suffixes}

    def _active_fields_for(self, kind: ComponentKind, process: ProcessKind, inlet_mode: str, outlet_mode: str) -> set[str]:
        fields = set(self._base_fields) | set(self._definition_fields)
        inlet_mode_fields = self._definition_fields_for_mode("inlet", inlet_mode)
        outlet_mode_fields = self._definition_fields_for_mode("outlet", outlet_mode)
        if kind in {ComponentKind.PUMP, ComponentKind.TURBINE}:
            fields |= (self._inlet_state_fields & inlet_mode_fields)
            fields |= (self._outlet_state_fields & outlet_mode_fields)
            fields |= {"outlet_efficiency", "inlet_efficiency", "pressure_drop_mpa"}
            return fields
        if kind in {ComponentKind.BOILER, ComponentKind.REHEATER, ComponentKind.CONDENSER, ComponentKind.HEAT_EXCHANGER}:
            fields |= (self._inlet_state_fields & inlet_mode_fields)
            fields |= (self._outlet_state_fields & outlet_mode_fields)
            fields |= {"heat_duty_kw", "pressure_drop_mpa"}
            return fields
        if kind == ComponentKind.VALVE:
            fields |= (self._inlet_state_fields & inlet_mode_fields)
            fields |= (self._outlet_state_fields & outlet_mode_fields)
            fields |= {"pressure_drop_mpa"}
            return fields
        if kind == ComponentKind.PIPE:
            fields |= (self._inlet_state_fields & inlet_mode_fields)
            fields |= (self._outlet_state_fields & outlet_mode_fields)
            fields |= self._pipe_fields
            return fields
        if kind in {ComponentKind.MIXER, ComponentKind.SPLITTER}:
            fields |= (self._inlet_state_fields & inlet_mode_fields)
            fields |= (self._outlet_state_fields & outlet_mode_fields)
            fields |= {"pressure_drop_mpa"}
            return fields
        if process == ProcessKind.GENERAL or kind == ComponentKind.CUSTOM:
            fields |= (self._inlet_state_fields & inlet_mode_fields)
            fields |= (self._outlet_state_fields & outlet_mode_fields)
            fields |= {"pressure_drop_mpa", "outlet_efficiency", "heat_duty_kw"}
            return fields
        fields |= (self._inlet_state_fields & inlet_mode_fields)
        fields |= (self._outlet_state_fields & outlet_mode_fields)
        fields |= {"pressure_drop_mpa", "outlet_efficiency"}
        return fields

    def _update_field_visibility(self, kind: ComponentKind, process: ProcessKind, inlet_mode: str, outlet_mode: str) -> None:
        self._active_fields = self._active_fields_for(kind, process, inlet_mode, outlet_mode)
        for field_name, _ in self.field_specs:
            visible = field_name in self._active_fields
            label = self._labels[field_name]
            widget = self._widgets[field_name]
            unit_widget = self._unit_widgets[field_name]
            if visible:
                label.grid()
                widget.grid()
                unit_widget.grid()
            else:
                label.grid_remove()
                widget.grid_remove()
                unit_widget.grid_remove()

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
            self._vars["inlet_definition_mode"].set("Auto")
            self._vars["outlet_definition_mode"].set("Auto")
            self._update_field_visibility(ComponentKind.CUSTOM, ProcessKind.GENERAL, "Auto", "Auto")
            self._loading = False
            return

        component = self.circuit.components[component_id]
        self._ensure_unit_prefs(component)
        self._update_field_visibility(
            component.kind,
            component.process_kind,
            component.inlet_definition_mode,
            component.outlet_definition_mode,
        )

        values = {
            "name": component.name,
            "kind": component.kind.value,
            "process_kind": component.process_kind.value,
            "inlet_definition_mode": component.inlet_definition_mode,
            "outlet_definition_mode": component.outlet_definition_mode,
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
        component.inlet_definition_mode = self._vars["inlet_definition_mode"].get().strip() or "Auto"
        component.outlet_definition_mode = self._vars["outlet_definition_mode"].get().strip() or "Auto"
        self._update_field_visibility(
            component.kind,
            component.process_kind,
            component.inlet_definition_mode,
            component.outlet_definition_mode,
        )

        component.solved_fields.clear()

        active = self._active_fields_for(
            component.kind,
            component.process_kind,
            component.inlet_definition_mode,
            component.outlet_definition_mode,
        )

        def parse_active(field_name: str) -> float | None:
            if field_name in active:
                return self._parse_and_track(component, field_name)
            component.user_input_fields.discard(field_name)
            return None

        component.inlet_spec = ThermoSpec(
            pressure_mpa=parse_active("inlet_pressure_mpa"),
            temperature_c=parse_active("inlet_temperature_c"),
            enthalpy_kj_kg=parse_active("inlet_enthalpy_kj_kg"),
            entropy_kj_kgk=parse_active("inlet_entropy_kj_kgk"),
            quality=parse_active("inlet_quality"),
            specific_volume_m3_kg=parse_active("inlet_specific_volume_m3_kg"),
            efficiency=parse_active("inlet_efficiency"),
        )
        component.outlet_spec = ThermoSpec(
            pressure_mpa=parse_active("outlet_pressure_mpa"),
            temperature_c=parse_active("outlet_temperature_c"),
            enthalpy_kj_kg=parse_active("outlet_enthalpy_kj_kg"),
            entropy_kj_kgk=parse_active("outlet_entropy_kj_kgk"),
            quality=parse_active("outlet_quality"),
            specific_volume_m3_kg=parse_active("outlet_specific_volume_m3_kg"),
            efficiency=parse_active("outlet_efficiency"),
            heat_duty_kw=parse_active("heat_duty_kw"),
            pressure_drop_mpa=parse_active("pressure_drop_mpa"),
            mass_flow_kg_s=parse_active("mass_flow_kg_s"),
            pipe_length_m=parse_active("pipe_length_m"),
            pipe_outer_diameter_m=parse_active("pipe_outer_diameter_m"),
            pipe_wall_thickness_m=parse_active("pipe_wall_thickness_m"),
            pipe_roughness_m=parse_active("pipe_roughness_m"),
            elevation_change_m=parse_active("elevation_change_m"),
            local_loss_coefficient=parse_active("local_loss_coefficient"),
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
        if self._vars[field_name].get().strip():
            component.user_input_fields.add(field_name)
        else:
            component.user_input_fields.discard(field_name)
        self._clear_highlights_dirty(component)

    def _on_any_field_modified(self, field_name: str) -> None:
        if self._loading or self.current_component_id is None:
            return
        component = self.circuit.components[self.current_component_id]
        if field_name in {"kind", "process_kind", "inlet_definition_mode", "outlet_definition_mode"}:
            try:
                kind = ComponentKind(self._vars["kind"].get().strip() or component.kind.value)
            except Exception:
                kind = component.kind
            try:
                process = ProcessKind(self._vars["process_kind"].get().strip() or component.process_kind.value)
            except Exception:
                process = component.process_kind
            inlet_mode = self._vars["inlet_definition_mode"].get().strip() or component.inlet_definition_mode
            outlet_mode = self._vars["outlet_definition_mode"].get().strip() or component.outlet_definition_mode
            self._update_field_visibility(kind, process, inlet_mode, outlet_mode)
        if is_numeric_field(field_name):
            if self._vars[field_name].get().strip():
                component.user_input_fields.add(field_name)
            else:
                component.user_input_fields.discard(field_name)
        self._clear_highlights_dirty(component)

    def _clear_highlights_dirty(self, component) -> None:
        component.solved_fields.clear()
        component.conflicting_fields.clear()
        component.is_dirty = True
        self._apply_highlights(component)
        if self.on_dirty:
            self.on_dirty()

    def _apply_highlights(self, component) -> None:
        overdefined = self._is_overdefined_for_non_general(component)
        for field_name in self._colorable_fields:
            widget = self._widgets[field_name]
            if field_name not in self._active_fields:
                continue
            color = self._neutral_bg
            if field_name in component.user_input_fields:
                color = self._input_bg
            if not component.is_dirty and field_name in component.solved_fields:
                color = self._solver_bg
            if field_name in component.conflicting_fields:
                color = self._conflict_bg
            widget.configure(bg=color)

        for field_name, label in self._labels.items():
            if field_name not in self._active_fields:
                continue
            highlight_field = field_name in self._inlet_state_fields or field_name in self._outlet_state_fields
            if overdefined and highlight_field:
                label.configure(foreground="#ff5a5a")
            else:
                label.configure(foreground="#e9eef7")

    def _is_overdefined_for_non_general(self, component) -> bool:
        if component.process_kind == ProcessKind.GENERAL:
            return False
        inlet_mode_var = self._vars.get("inlet_definition_mode")
        outlet_mode_var = self._vars.get("outlet_definition_mode")
        inlet_mode = (inlet_mode_var.get() if inlet_mode_var is not None else "") or component.inlet_definition_mode
        outlet_mode = (outlet_mode_var.get() if outlet_mode_var is not None else "") or component.outlet_definition_mode
        inlet_required = self._definition_fields_for_mode("inlet", inlet_mode)
        outlet_required = self._definition_fields_for_mode("outlet", outlet_mode)

        def complete(required: set[str]) -> bool:
            for field_name in required:
                if field_name not in self._active_fields:
                    continue
                if not self._vars[field_name].get().strip():
                    return False
            return True

        return complete(inlet_required) and complete(outlet_required)

    def solve_requested(self) -> None:
        if self.on_solve:
            self.on_solve()
