from __future__ import annotations

import copy
import platform
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Optional, cast

from ..demo import build_reheat_rankine_demo
from ..model import Circuit, Component, ComponentKind, ProcessKind, ThermoSpec
from ..persistence import circuit_from_dict, circuit_to_dict, load_project_file, save_project_file
from ..presets import PRESETS, apply_preset, preset_names
from ..solve_logging import append_solve_log
from ..solver import ConstraintDiagnostics, CircuitSolution, SolverError, ThermoSolver, analyze_constraint_system, solve_circuit
from .canvas import NodeCanvas
from .cycle_diagram import CycleDiagramPanel
from .inspector import ComponentInspector
from ..unit_system import default_unit


class HeatCircuitApp(ttk.Frame):
    def __init__(self, master: tk.Tk):
        super().__init__(master)
        self._app_root = master
        self._app_root.title("Heat Circuit Tool")
        screen_w = max(int(self._app_root.winfo_screenwidth()), 800)
        screen_h = max(int(self._app_root.winfo_screenheight()), 600)
        launch_w = max(screen_w // 2, 480)
        launch_h = max(screen_h // 2, 320)
        self._app_root.geometry(f"{launch_w}x{launch_h}")
        self._app_root.minsize(480, 320)
        self.circuit = build_reheat_rankine_demo()
        self._selection_id: Optional[str] = None
        self._latest_solved_snapshot: dict | None = None
        self._project_snapshots: list[dict] = []
        self._project_path: str | None = None
        self._project_log_path: str = self._derive_log_path(None)
        self._last_solution: CircuitSolution | None = None
        self._constraint_diagnostics: ConstraintDiagnostics = ConstraintDiagnostics(system_status="Unknown")
        self._last_solver_error: str | None = None
        self._library_collapsed = False
        self._library_popout: tk.Toplevel | None = None
        self._inspector_popout: tk.Toplevel | None = None
        self._results_popout: tk.Toplevel | None = None
        self._popup_inspector: ComponentInspector | None = None
        self._popup_results_text: tk.Text | None = None
        self._panel_state: dict[str, dict] = {}
        self._inspector_popup_host: ttk.Frame | None = None
        self._popup_results_scroll: ttk.Scrollbar | None = None
        self._active_wheel_target: str | None = None
        self._apply_seed_as_user_constraints()
        self._build_style()
        self._build_ui()
        self.pack(fill="both", expand=True)
        self.refresh_all()

    def _apply_seed_as_user_constraints(self) -> None:
        if self.circuit.start_component_id is None or self.circuit.seed_state is None:
            return
        component = self.circuit.components.get(self.circuit.start_component_id)
        if component is None:
            return
        seed = self.circuit.seed_state
        inlet_edge = self.circuit.inlet_edge(component)
        inlet_edge.spec.pressure_mpa = seed.pressure_mpa
        inlet_edge.spec.temperature_c = seed.temperature_c
        inlet_edge.spec.enthalpy_kj_kg = seed.enthalpy_kj_kg
        inlet_edge.spec.entropy_kj_kgk = seed.entropy_kj_kgk
        inlet_edge.spec.specific_volume_m3_kg = seed.specific_volume_m3_kg
        inlet_edge.spec.quality = seed.quality

        seeded_fields = {
            "pressure_mpa",
            "temperature_c",
            "enthalpy_kj_kg",
            "entropy_kj_kgk",
            "specific_volume_m3_kg",
            "quality",
        }
        inlet_edge.user_input_fields.update(seeded_fields)
        for field_name in seeded_fields:
            component.unit_preferences.setdefault(f"inlet_{field_name}", default_unit(f"inlet_{field_name}"))

    def _derive_log_path(self, project_path: str | None) -> str:
        if not project_path:
            return str(Path.cwd() / "unsaved_project.solve_log.jsonl")
        project = Path(project_path)
        if project.name.endswith(".hct.json"):
            base_name = project.name[:-9]
        else:
            base_name = project.stem
        return str(project.with_name(base_name + ".solve_log.jsonl"))

    def _build_style(self) -> None:
        style = ttk.Style(self._app_root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#0f1319")
        style.configure("TLabel", background="#0f1319", foreground="#e9eef7")
        style.configure("TLabelframe", background="#0f1319", foreground="#e9eef7")
        style.configure("TLabelframe.Label", background="#0f1319", foreground="#9fd8ff")
        style.configure("TButton", padding=6)
        # Segoe UI Symbol is Windows-only; fall back to the default symbol font on macOS/Linux
        _symbol_font = ("Segoe UI Symbol", 9) if platform.system() == "Windows" else ("TkDefaultFont", 9)
        style.configure("PanelTool.TButton", padding=(2, 0), font=_symbol_font)
        style.configure("PanelBody.TFrame", background="#18202c")

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_insert_menu()

        header = ttk.Frame(self)
        header.grid(row=0, column=0, columnspan=3, sticky="ew", padx=8, pady=8)
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Heat Circuit Tool", font=("Segoe UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Drag components, connect ports, zoom with wheel, pan with middle mouse, then solve.", font=("Segoe UI", 10)).grid(row=1, column=0, sticky="w")

        toolbar = ttk.Frame(header)
        toolbar.grid(row=0, column=1, rowspan=2, sticky="e")
        ttk.Button(toolbar, text="Load Demo", command=self.load_demo).grid(row=0, column=0, padx=3)
        ttk.Button(toolbar, text="Add Pump", command=lambda: self.add_component(ComponentKind.PUMP, ProcessKind.ISENTROPIC)).grid(row=0, column=1, padx=3)
        ttk.Button(toolbar, text="Add Boiler", command=lambda: self.add_component(ComponentKind.BOILER, ProcessKind.ISOBARIC)).grid(row=0, column=2, padx=3)
        ttk.Button(toolbar, text="Add Turbine", command=lambda: self.add_component(ComponentKind.TURBINE, ProcessKind.ISENTROPIC)).grid(row=0, column=3, padx=3)
        ttk.Button(toolbar, text="Add Reheater", command=lambda: self.add_component(ComponentKind.REHEATER, ProcessKind.ISOBARIC)).grid(row=0, column=4, padx=3)
        ttk.Button(toolbar, text="Add Pipe", command=lambda: self.add_component(ComponentKind.PIPE, ProcessKind.ADIABATIC)).grid(row=0, column=5, padx=3)
        ttk.Button(toolbar, text="Solve", command=self.request_solve).grid(row=0, column=6, padx=3)
        ttk.Button(toolbar, text="Revert Last Solve", command=self.revert_latest_solve).grid(row=0, column=7, padx=3)
        ttk.Button(toolbar, text="Save Project", command=self.save_project).grid(row=0, column=8, padx=3)
        ttk.Button(toolbar, text="Load Project", command=self.load_project).grid(row=0, column=9, padx=3)
        ttk.Button(toolbar, text="Clear All User Fields", command=self.clear_all_user_fields).grid(row=0, column=10, padx=3)

        self.snapshot_var = tk.StringVar(value="")
        self.preset_var = tk.StringVar(value=preset_names()[0])
        self.snapshot_combo = ttk.Combobox(toolbar, textvariable=self.snapshot_var, values=[], state="readonly", width=26)
        self.snapshot_combo.grid(row=1, column=7, columnspan=2, padx=3, sticky="ew")
        self.snapshot_combo.bind("<<ComboboxSelected>>", self._on_snapshot_selected)
        ttk.Button(toolbar, text="Save Snapshot", command=self.save_snapshot).grid(row=1, column=9, padx=3)
        ttk.Button(toolbar, text="Rename Snapshot", command=self.rename_snapshot).grid(row=1, column=10, padx=3)

        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        self.model_tab = ttk.Frame(self.tabs)
        self.diagram_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.model_tab, text="Model")
        self.tabs.add(self.diagram_tab, text="Cycle Diagram")

        self.model_tab.columnconfigure(0, weight=1)
        self.model_tab.rowconfigure(0, weight=1)
        self.diagram_tab.columnconfigure(0, weight=1)
        self.diagram_tab.rowconfigure(0, weight=1)

        self.workspace = ttk.Frame(self.model_tab)
        self.workspace.grid(row=0, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.workspace.columnconfigure(0, weight=1)
        self.workspace.rowconfigure(0, weight=1)

        self.content_pane = tk.PanedWindow(self.workspace, orient=tk.HORIZONTAL, sashrelief=tk.RAISED, sashwidth=6, background="#0f1319")
        self.content_pane.grid(row=0, column=0, sticky="nsew")

        # Docked side panel: Inspector and Results live as tabs of the same
        # notebook, docked to the left of the canvas. Either tab can still be
        # popped out into its own floating window via the "↗" button.
        self.side_dock_frame = ttk.Frame(self.content_pane)
        self.side_dock_frame.rowconfigure(0, weight=1)
        self.side_dock_frame.columnconfigure(0, weight=1)
        self.side_tabs = ttk.Notebook(self.side_dock_frame)
        self.side_tabs.grid(row=0, column=0, sticky="nsew")

        self.canvas_frame = ttk.Frame(self.content_pane)
        self.canvas_frame.rowconfigure(0, weight=1)
        self.canvas_frame.columnconfigure(0, weight=1)
        self.canvas = NodeCanvas(self.canvas_frame, self.circuit, self.on_canvas_select)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Delete>", self.delete_selected_component)
        # On macOS the physical Delete key sends BackSpace; bind both so it works on either platform.
        self.canvas.bind("<BackSpace>", self.delete_selected_component)

        self.inspector_frame = tk.Frame(self.side_tabs, bg="#1a2230")
        self.inspector_frame.columnconfigure(0, weight=1)
        self.inspector_frame.rowconfigure(1, weight=1)
        inspector_header = tk.Frame(self.inspector_frame, bg="#223047")
        inspector_header.grid(row=0, column=0, sticky="ew")
        inspector_header.columnconfigure(0, weight=1)
        inspector_title = tk.Label(inspector_header, text="Inspector", bg="#223047", fg="#e9eef7", font=("Segoe UI", 10, "bold"))
        inspector_title.grid(row=0, column=0, sticky="w", padx=(8, 0), pady=4)
        self.inspector_popout_btn = ttk.Button(inspector_header, text="↗", width=2, style="PanelTool.TButton", command=self.toggle_inspector_popout)
        self.inspector_popout_btn.grid(row=0, column=1, sticky="e", padx=4)
        self.inspector_content = ttk.Frame(self.inspector_frame, style="PanelBody.TFrame")
        self.inspector_content.grid(row=1, column=0, sticky="nsew")

        self.results_frame = tk.Frame(self.side_tabs, bg="#1a2230")
        self.results_frame.columnconfigure(0, weight=1)
        self.results_frame.rowconfigure(1, weight=1)
        results_header = tk.Frame(self.results_frame, bg="#223047")
        results_header.grid(row=0, column=0, sticky="ew")
        results_header.columnconfigure(0, weight=1)
        results_title = tk.Label(results_header, text="Results", bg="#223047", fg="#e9eef7", font=("Segoe UI", 10, "bold"))
        results_title.grid(row=0, column=0, sticky="w", padx=(8, 0), pady=4)
        self.results_popout_btn = ttk.Button(results_header, text="↗", width=2, style="PanelTool.TButton", command=self.toggle_results_popout)
        self.results_popout_btn.grid(row=0, column=1, sticky="e", padx=4)
        self.results_content = ttk.Frame(self.results_frame, style="PanelBody.TFrame")
        self.results_content.grid(row=1, column=0, sticky="nsew")

        self.side_tabs.add(self.inspector_frame, text="Inspector")
        self.side_tabs.add(self.results_frame, text="Results")

        self.inspector_scroll_canvas = tk.Canvas(self.inspector_content, background="#18202c", highlightthickness=0)
        self.inspector_scroll_canvas.pack(side="left", fill="both", expand=True)
        self.inspector_scrollbar = ttk.Scrollbar(self.inspector_content, orient="vertical", command=self.inspector_scroll_canvas.yview)
        self.inspector_scrollbar.pack(side="right", fill="y")
        self.inspector_scroll_canvas.configure(yscrollcommand=self.inspector_scrollbar.set)
        inspector_scroll_host = ttk.Frame(self.inspector_scroll_canvas, style="PanelBody.TFrame")
        inspector_scroll_window = self.inspector_scroll_canvas.create_window((0, 0), window=inspector_scroll_host, anchor="nw")
        inspector_scroll_host.bind("<Configure>", lambda _e: self.inspector_scroll_canvas.configure(scrollregion=self.inspector_scroll_canvas.bbox("all")))
        self.inspector_scroll_canvas.bind("<Configure>", lambda e: self.inspector_scroll_canvas.itemconfigure(inspector_scroll_window, width=e.width))

        self.inspector = ComponentInspector(
            inspector_scroll_host,
            self.circuit,
            on_apply=self._on_inspector_apply,
            on_solve=self.request_solve,
            on_dirty=self._on_inspector_dirty,
        )
        self.inspector.pack(fill="both", expand=True, padx=8, pady=8)

        self.results_text = tk.Text(self.results_content, wrap="word", background="#0b0f14", foreground="#e9eef7", insertbackground="#e9eef7")
        self.results_text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        self.results_scroll = ttk.Scrollbar(self.results_content, orient="vertical", command=self.results_text.yview)
        self.results_scroll.pack(side="right", fill="y", padx=(6, 8), pady=8)
        self.results_text.configure(yscrollcommand=self.results_scroll.set)
        self.results_text.insert("1.0", "Load the demo and press Solve to validate the reheat Rankine cycle.")
        self.results_text.configure(state="disabled")

        self.content_pane.add(self.side_dock_frame, minsize=320)
        self.content_pane.add(self.canvas_frame, minsize=480)

        self._panel_state = {
            "inspector": {"frame": self.inspector_frame, "popout_btn": self.inspector_popout_btn, "undocked": False},
            "results": {"frame": self.results_frame, "popout_btn": self.results_popout_btn, "undocked": False},
        }
        self._bind_panel_scroll_events()

        self.cycle_diagram = CycleDiagramPanel(self.diagram_tab)
        self.cycle_diagram.grid(row=0, column=0, sticky="nsew")

        self.status = tk.StringVar(value="Ready")
        self.constraint_badge = tk.StringVar(value="Constraint: Unknown")
        footer = ttk.Frame(self)
        footer.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        footer.columnconfigure(0, weight=1)
        status_bar = ttk.Label(footer, textvariable=self.status, anchor="w")
        status_bar.grid(row=0, column=0, sticky="ew")
        self.constraint_badge_label = tk.Label(
            footer,
            textvariable=self.constraint_badge,
            bg="#59606b",
            fg="#ffffff",
            padx=8,
            pady=3,
            font=("Segoe UI", 9, "bold"),
        )
        self.constraint_badge_label.grid(row=0, column=1, sticky="e", padx=(8, 0))
        self._refresh_panel_button_labels()
        self._update_live_diagnostics()

    def _build_insert_menu(self) -> None:
        menu_bar = tk.Menu(self._app_root)
        insert_menu = tk.Menu(menu_bar, tearoff=0)
        insert_menu.add_command(label="Pump", command=lambda: self.add_component(ComponentKind.PUMP, ProcessKind.ISENTROPIC))
        insert_menu.add_command(label="Boiler", command=lambda: self.add_component(ComponentKind.BOILER, ProcessKind.ISOBARIC))
        insert_menu.add_command(label="Turbine", command=lambda: self.add_component(ComponentKind.TURBINE, ProcessKind.ISENTROPIC))
        insert_menu.add_command(label="Reheater", command=lambda: self.add_component(ComponentKind.REHEATER, ProcessKind.ISOBARIC))
        insert_menu.add_command(label="Condenser", command=lambda: self.add_component(ComponentKind.CONDENSER, ProcessKind.ISOBARIC))
        insert_menu.add_command(label="Pipe", command=lambda: self.add_component(ComponentKind.PIPE, ProcessKind.ADIABATIC))
        insert_menu.add_command(label="Mixer", command=lambda: self.add_component(ComponentKind.MIXER, ProcessKind.ADIABATIC))
        insert_menu.add_command(label="Splitter", command=lambda: self.add_component(ComponentKind.SPLITTER, ProcessKind.ADIABATIC))
        insert_menu.add_command(label="Valve", command=lambda: self.add_component(ComponentKind.VALVE, ProcessKind.ISENTHALPIC))
        insert_menu.add_command(label="Custom", command=lambda: self.add_component(ComponentKind.CUSTOM, ProcessKind.GENERAL))
        insert_menu.add_separator()

        presets_menu = tk.Menu(insert_menu, tearoff=0)
        for name in preset_names():
            presets_menu.add_command(label=name, command=lambda n=name: self.add_preset_by_name(n))
        insert_menu.add_cascade(label="Preset", menu=presets_menu)

        menu_bar.add_cascade(label="Insert", menu=insert_menu)
        self._app_root.configure(menu=menu_bar)

    def refresh_all(self) -> None:
        self.canvas.redraw()
        self.inspector.load_component(self._selection_id)
        if self._popup_inspector:
            self._popup_inspector.load_component(self._selection_id)
        self._update_live_diagnostics()
        self._refresh_results_text(None)
        self.cycle_diagram.set_solution(self.circuit, self._last_solution)

    def on_canvas_select(self, component_id: Optional[str]) -> None:
        self._selection_id = component_id
        self.inspector.load_component(component_id)
        if self._popup_inspector:
            self._popup_inspector.load_component(component_id)
        self._push_inspector_constraint_status(component_id)
        if component_id is None:
            self.status.set("No component selected")
        else:
            component = self.circuit.components[component_id]
            self.status.set(f"Selected {component.name} ({component.kind.value})")

    def add_component(self, kind: ComponentKind, process: ProcessKind) -> None:
        index = len(self.circuit.components) + 1
        component_id = f"N{index}"
        while component_id in self.circuit.components:
            index += 1
            component_id = f"N{index}"
        default_outlet_spec = ThermoSpec(efficiency=0.85 if kind in {ComponentKind.PUMP, ComponentKind.TURBINE} else None)
        if kind == ComponentKind.PIPE:
            default_outlet_spec = ThermoSpec(
                mass_flow_kg_s=10.0,
                pipe_length_m=25.0,
                pipe_outer_diameter_m=0.1683,
                pipe_wall_thickness_m=0.0071,
                pipe_roughness_m=4.5e-5,
                elevation_change_m=0.0,
                local_loss_coefficient=1.0,
            )
        component = Component(
            component_id,
            kind,
            process,
            f"{kind.value} {index}",
            120 + (index % 4) * 220,
            120 + (index // 4) * 140,
        )
        self.circuit.add_component(component)
        self.circuit.outlet_edge(component).spec = default_outlet_spec
        self.canvas.redraw()
        self.canvas.select_component(component.component_id)
        self.status.set(f"Added {component.name}")

    def add_selected_preset(self) -> None:
        preset_name = self.preset_var.get().strip()
        self.add_preset_by_name(preset_name)

    def add_preset_by_name(self, preset_name: str) -> None:
        if preset_name not in PRESETS:
            return
        index = len(self.circuit.components) + 1
        component_id = f"N{index}"
        while component_id in self.circuit.components:
            index += 1
            component_id = f"N{index}"
        base = PRESETS[preset_name]
        component = Component(
            component_id,
            base.kind,
            base.process_kind,
            f"{base.name} {index}",
            120 + (index % 4) * 220,
            120 + (index // 4) * 140,
        )
        self.circuit.add_component(component)
        apply_preset(self.circuit, component, preset_name)
        component.name = f"{component.name} {index}"
        self.canvas.redraw()
        self.canvas.select_component(component.component_id)
        self.status.set(f"Added preset {preset_name}")

    def delete_selected_component(self, event: tk.Event | None = None) -> None:
        if self._selection_id is None:
            return
        self.circuit.remove_component(self._selection_id)
        self._selection_id = None
        self.canvas.redraw()
        self.inspector.load_component(None)
        if self._popup_inspector:
            self._popup_inspector.load_component(None)
        self.status.set("Component deleted")

    def clear_all_user_fields(self) -> None:
        if not messagebox.askyesno(
            "Clear All User Fields",
            "Clear every user-defined field from every component in the circuit?",
        ):
            return
        for edge in self.circuit.edges.values():
            for suffix in list(edge.user_input_fields):
                setattr(edge.spec, suffix, None)
            edge.user_input_fields.clear()
            edge.solved_fields.clear()
            edge.conflicting_fields.clear()
        for component in self.circuit.components.values():
            component.is_dirty = True
        self.inspector.load_component(self._selection_id)
        if self._popup_inspector:
            self._popup_inspector.load_component(self._selection_id)
        self._last_solution = None
        self._last_solver_error = None
        self._update_live_diagnostics()
        self._refresh_results_text(None)
        self.canvas.redraw()
        self.status.set("Cleared all user-defined fields")

    def request_solve(self) -> None:
        if self._popup_inspector is not None:
            self._popup_inspector.apply_to_component()
        self.inspector.apply_to_component()
        self._last_solver_error = None
        try:
            solution = solve_circuit(self.circuit)
        except SolverError as exc:
            self._last_solver_error = str(exc)
            self._last_solution = None
            self._update_live_diagnostics()
            self._refresh_results_text(None)
            messagebox.showerror("Solve failed", str(exc))
            self.status.set("Solve failed")
            return
        except Exception as exc:  # pragma: no cover - runtime safety
            self._last_solver_error = str(exc)
            self._last_solution = None
            self._update_live_diagnostics()
            self._refresh_results_text(None)
            messagebox.showerror("Solve failed", str(exc))
            self.status.set("Solve failed")
            return

        for result in solution.component_results:
            self.inspector.apply_solution_to_component(
                result.component_id,
                result.inlet_state,
                result.outlet_state,
                conflicting_fields=result.conflicting_fields,
            )
            if self._popup_inspector is not None:
                self._popup_inspector.apply_solution_to_component(
                    result.component_id,
                    result.inlet_state,
                    result.outlet_state,
                    conflicting_fields=result.conflicting_fields,
                )

        self.inspector.show_solution(solution)
        if self._popup_inspector:
            self._popup_inspector.show_solution(solution)
        self._refresh_results_text(solution)
        self._last_solution = solution
        self.cycle_diagram.set_solution(self.circuit, solution)
        self._latest_solved_snapshot = circuit_to_dict(self.circuit)
        self._upsert_snapshot("Latest Solve", self._latest_solved_snapshot)
        try:
            append_solve_log(self._project_log_path, self.circuit, solution)
        except Exception as exc:  # pragma: no cover - non-fatal logging path
            solution.messages.append(f"Solve log write failed: {exc}")
        self._update_live_diagnostics()
        self.canvas.redraw()
        if solution.system_status == "Overconstrained":
            self.status.set("Solve complete: system overconstrained (see red fields and results)")
        elif solution.system_status == "Underconstrained":
            self.status.set("Solve complete: system underconstrained (undeterminable results present)")
        else:
            self.status.set("Circuit solved successfully")

    def _on_inspector_apply(self) -> None:
        self._solve_selected_component_preview()
        self.canvas.redraw()
        if self._popup_inspector and self._selection_id:
            self._popup_inspector.load_component(self._selection_id)
        self._update_live_diagnostics()
        if self._selection_id and self._selection_id in self.circuit.components:
            component = self.circuit.components[self._selection_id]
            if component.is_dirty:
                self.status.set(f"Updated {component.name}")
            else:
                self.status.set(f"Updated {component.name} and solved selected component")

    def _solve_selected_component_preview(self) -> None:
        if self._selection_id is None:
            return
        if self._selection_id not in self.circuit.components:
            return

        solver = ThermoSolver()
        try:
            results_by_id = solver.propagate(self.circuit)
        except Exception:
            return

        # Propagation cascades to every component whose state is now derivable
        # (not just the selected one), so a downstream reheater etc. picks up
        # values that became indirectly known from the edited constraints.
        for result in results_by_id.values():
            self.inspector.apply_solution_to_component(
                result.component_id,
                result.inlet_state,
                result.outlet_state,
                conflicting_fields=result.conflicting_fields,
            )
            if self._popup_inspector is not None:
                self._popup_inspector.apply_solution_to_component(
                    result.component_id,
                    result.inlet_state,
                    result.outlet_state,
                    conflicting_fields=result.conflicting_fields,
                )

    def _on_inspector_dirty(self) -> None:
        self.status.set("Model modified: solve required")
        self.canvas.redraw()
        self._last_solution = None
        self._update_live_diagnostics()
        self._refresh_results_text(None)

    def _refresh_results_text(self, solution: CircuitSolution | None) -> None:
        if solution is None:
            text = self.inspector.solution_text()
        else:
            text = self.inspector.solution_text()
        diagnostics_lines = ["", "Live Diagnostics", "----------------", *self._constraint_diagnostics.summary_lines(), ""]
        for item in self._constraint_diagnostics.component_diagnostics:
            diagnostics_lines.append(
                f"{item.component_name}: {item.status} | needs {item.additional_info_required} | {item.message}"
            )
        if self._last_solver_error:
            diagnostics_lines.extend(["", "Last Solve Error", "----------------", self._last_solver_error])
        text = text + "\n".join(diagnostics_lines)
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", tk.END)
        self.results_text.insert("1.0", text)
        self.results_text.configure(state="disabled")
        if self._popup_results_text is not None:
            self._popup_results_text.configure(state="normal")
            self._popup_results_text.delete("1.0", tk.END)
            self._popup_results_text.insert("1.0", text)
            self._popup_results_text.configure(state="disabled")

    def load_demo(self) -> None:
        self.circuit = build_reheat_rankine_demo()
        self._last_solution = None
        self._apply_seed_as_user_constraints()
        self.canvas.set_circuit(self.circuit)
        self.inspector.circuit = self.circuit
        if self._popup_inspector:
            self._popup_inspector.circuit = self.circuit
        self.cycle_diagram.set_solution(self.circuit, None)
        self._selection_id = self.circuit.start_component_id
        self.canvas.select_component(self._selection_id)
        self._last_solver_error = None
        self._update_live_diagnostics()
        self.status.set("Loaded reheat Rankine cycle demo")

    def revert_latest_solve(self) -> None:
        if self._latest_solved_snapshot is None:
            self.status.set("No solved state cached yet")
            return
        self._restore_circuit_dict(copy.deepcopy(self._latest_solved_snapshot))
        self._last_solver_error = None
        self._update_live_diagnostics()
        self.status.set("Reverted to latest solved state")

    def save_snapshot(self) -> None:
        name = simpledialog.askstring("Save Snapshot", "Snapshot name:", parent=self)
        if not name:
            return
        self._upsert_snapshot(name.strip(), circuit_to_dict(self.circuit))
        self.status.set(f"Saved snapshot: {name.strip()}")

    def rename_snapshot(self) -> None:
        old_name = self.snapshot_var.get().strip()
        if not old_name:
            return
        new_name = simpledialog.askstring("Rename Snapshot", "New name:", initialvalue=old_name, parent=self)
        if not new_name:
            return
        for item in self._project_snapshots:
            if item["name"] == old_name:
                item["name"] = new_name.strip()
                break
        self._refresh_snapshot_combo(new_name.strip())
        self.status.set(f"Renamed snapshot to {new_name.strip()}")

    def _on_snapshot_selected(self, _event=None) -> None:
        target = self.snapshot_var.get().strip()
        if not target:
            return
        for item in self._project_snapshots:
            if item["name"] == target:
                self._restore_circuit_dict(copy.deepcopy(item["circuit"]))
                self.status.set(f"Loaded snapshot: {target}")
                return

    def _upsert_snapshot(self, name: str, circuit_dict: dict) -> None:
        for item in self._project_snapshots:
            if item["name"] == name:
                item["circuit"] = circuit_dict
                self._refresh_snapshot_combo(name)
                return
        self._project_snapshots.append({"name": name, "circuit": circuit_dict})
        self._refresh_snapshot_combo(name)

    def _refresh_snapshot_combo(self, selected: str | None = None) -> None:
        names = [item["name"] for item in self._project_snapshots]
        self.snapshot_combo.configure(values=names)
        if selected and selected in names:
            self.snapshot_var.set(selected)
        elif names and not self.snapshot_var.get():
            self.snapshot_var.set(names[0])

    def save_project(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Save Project",
            defaultextension=".hct.json",
            filetypes=[("Heat Circuit Project", "*.hct.json"), ("JSON", "*.json")],
        )
        if not path:
            return
        save_project_file(path, self.circuit, copy.deepcopy(self._project_snapshots), self._latest_solved_snapshot)
        self._project_path = path
        self._project_log_path = self._derive_log_path(path)
        self.status.set(f"Project saved: {path}")

    def load_project(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Load Project",
            filetypes=[("Heat Circuit Project", "*.hct.json"), ("JSON", "*.json")],
        )
        if not path:
            return
        payload = load_project_file(path)
        self._restore_circuit_dict(payload["active_circuit"])
        self._project_snapshots = payload.get("snapshots", [])
        self._latest_solved_snapshot = payload.get("latest_solved")
        self._last_solution = None
        self._refresh_snapshot_combo()
        self._project_path = path
        self._project_log_path = self._derive_log_path(path)
        self.cycle_diagram.set_solution(self.circuit, None)
        self._last_solver_error = None
        self._update_live_diagnostics()
        self.status.set(f"Project loaded: {path}")

    def _restore_circuit_dict(self, circuit_dict: dict) -> None:
        self.circuit = circuit_from_dict(circuit_dict)
        self._last_solution = None
        self._apply_seed_as_user_constraints()
        self.canvas.set_circuit(self.circuit)
        self.inspector.circuit = self.circuit
        if self._popup_inspector:
            self._popup_inspector.circuit = self.circuit
        self._selection_id = self.circuit.start_component_id
        self.canvas.select_component(self._selection_id)
        self._update_live_diagnostics()
        self._refresh_results_text(None)
        self.cycle_diagram.set_solution(self.circuit, None)

    def _update_live_diagnostics(self) -> None:
        self._constraint_diagnostics = analyze_constraint_system(self.circuit)
        status = self._constraint_diagnostics.system_status
        self.constraint_badge.set(f"Constraint: {status}")
        if status == "Well-defined":
            self.constraint_badge_label.configure(bg="#1f8f4d", fg="#ffffff")
        elif status == "Overconstrained":
            self.constraint_badge_label.configure(bg="#b83a3a", fg="#ffffff")
        else:
            self.constraint_badge_label.configure(bg="#b37a1f", fg="#ffffff")

        # Push per-component status into canvas for coloured outlines
        status_map = {
            diag.component_id: diag.status
            for diag in self._constraint_diagnostics.component_diagnostics
        }
        self.canvas.set_constraint_statuses(status_map)
        self.canvas.redraw()

        # Update inspector banner for the currently selected component
        self._push_inspector_constraint_status(self._selection_id)

    def _push_inspector_constraint_status(self, component_id: Optional[str]) -> None:
        diag = None
        if component_id is not None:
            for d in self._constraint_diagnostics.component_diagnostics:
                if d.component_id == component_id:
                    diag = d
                    break
        self.inspector.update_constraint_status(diag)
        if self._popup_inspector is not None:
            self._popup_inspector.update_constraint_status(diag)

    def _pane_contains(self, pane: tk.PanedWindow, widget: tk.Widget) -> bool:
        widget_name = str(widget)
        return any(str(pane_item) == widget_name for pane_item in pane.panes())

    def _bind_recursive(self, widget: tk.Misc, sequence: str, callback) -> None:
        widget.bind(sequence, callback, add="+")
        for child in widget.winfo_children():
            self._bind_recursive(child, sequence, callback)

    def _bind_panel_scroll_events(self) -> None:
        self.canvas.bind("<Enter>", lambda _e: self._set_wheel_target("canvas"), add="+")
        self.canvas.bind("<Leave>", lambda _e: self._clear_wheel_target("canvas"), add="+")
        self._bind_recursive(self.inspector_frame, "<Enter>", lambda _e: self._set_wheel_target("inspector"))
        self._bind_recursive(self.inspector_frame, "<Leave>", lambda _e: self._clear_wheel_target("inspector"))
        self._bind_recursive(self.results_frame, "<Enter>", lambda _e: self._set_wheel_target("results"))
        self._bind_recursive(self.results_frame, "<Leave>", lambda _e: self._clear_wheel_target("results"))
        self.bind_all("<MouseWheel>", self._on_global_mouse_wheel, add="+")
        self.bind_all("<Shift-MouseWheel>", self._on_global_mouse_wheel, add="+")
        self.bind_all("<Control-MouseWheel>", self._on_global_mouse_wheel, add="+")
        self.bind_all("<Command-MouseWheel>", self._on_global_mouse_wheel, add="+")
        self.bind_all("<Button-4>", self._on_global_scroll_up, add="+")
        self.bind_all("<Button-5>", self._on_global_scroll_down, add="+")

    def _set_wheel_target(self, target: str) -> None:
        self._active_wheel_target = target

    def _clear_wheel_target(self, target: str) -> None:
        if self._active_wheel_target == target:
            self._active_wheel_target = None

    def _pointer_over_widget(self, widget: tk.Widget) -> bool:
        try:
            pointer_x, pointer_y = self.winfo_pointerxy()
        except tk.TclError:
            return False
        left = widget.winfo_rootx()
        top = widget.winfo_rooty()
        right = left + widget.winfo_width()
        bottom = top + widget.winfo_height()
        return left <= pointer_x <= right and top <= pointer_y <= bottom

    def _widget_under_pointer(self) -> tk.Widget | None:
        try:
            pointer_x, pointer_y = self.winfo_pointerxy()
        except tk.TclError:
            return None
        return cast(tk.Widget | None, self.winfo_containing(pointer_x, pointer_y))

    def _is_descendant_of(self, widget: tk.Widget | None, ancestor: tk.Widget) -> bool:
        if widget is None:
            return False
        ancestor_name = str(ancestor)
        widget_name = str(widget)
        return widget_name == ancestor_name or widget_name.startswith(f"{ancestor_name}.")

    def _on_global_mouse_wheel(self, event: tk.Event) -> None:
        hovered = self._widget_under_pointer()
        over_canvas = self._is_descendant_of(hovered, self.canvas)
        over_inspector = self._is_descendant_of(hovered, self.inspector_frame)
        over_results = self._is_descendant_of(hovered, self.results_frame)

        # If pointer is not over inspector/results, default wheel handling to canvas.
        if not over_inspector and not over_results:
            over_canvas = True

        if over_canvas:
            raw = getattr(event, "delta", 0)
            state = getattr(event, "state", 0)
            self.canvas._set_input_debug(f"app wheel raw={raw} state={state}")
            state = getattr(event, "state", 0)
            if state & 0x0001:
                self.canvas._on_canvas_shift_mouse_wheel(event)
            elif state & 0x0004 or state & 0x0008:
                self.canvas._on_canvas_modified_mouse_wheel(event)
            else:
                self.canvas._on_canvas_mouse_wheel(event)
            return

        # Windows delivers delta in multiples of 120; macOS delivers small pixel values.
        # Normalise to ±1 steps regardless of platform.
        raw = event.delta
        if raw == 0:
            return
        if platform.system() == "Windows":
            delta_steps = int(-raw / 120)
        else:
            delta_steps = -1 if raw > 0 else 1
        if over_inspector:
            self.inspector_scroll_canvas.yview_scroll(delta_steps, "units")
        elif over_results:
            self.results_text.yview_scroll(delta_steps, "units")

    def _on_global_scroll_up(self, event: tk.Event) -> None:
        hovered = self._widget_under_pointer()
        over_canvas = self._is_descendant_of(hovered, self.canvas)
        over_inspector = self._is_descendant_of(hovered, self.inspector_frame)
        over_results = self._is_descendant_of(hovered, self.results_frame)
        if not over_inspector and not over_results:
            over_canvas = True
        if over_canvas:
            self.canvas._set_input_debug("app button-4")
            self.canvas._on_canvas_scroll_up(event)
            return
        if over_inspector:
            self.inspector_scroll_canvas.yview_scroll(-1, "units")
        elif over_results:
            self.results_text.yview_scroll(-1, "units")

    def _on_global_scroll_down(self, event: tk.Event) -> None:
        hovered = self._widget_under_pointer()
        over_canvas = self._is_descendant_of(hovered, self.canvas)
        over_inspector = self._is_descendant_of(hovered, self.inspector_frame)
        over_results = self._is_descendant_of(hovered, self.results_frame)
        if not over_inspector and not over_results:
            over_canvas = True
        if over_canvas:
            self.canvas._set_input_debug("app button-5")
            self.canvas._on_canvas_scroll_down(event)
            return
        if over_inspector:
            self.inspector_scroll_canvas.yview_scroll(1, "units")
        elif over_results:
            self.results_text.yview_scroll(1, "units")

    def _refresh_panel_button_labels(self) -> None:
        self.inspector_popout_btn.configure(text="↙" if self._panel_state["inspector"]["undocked"] else "↗")
        self.results_popout_btn.configure(text="↙" if self._panel_state["results"]["undocked"] else "↗")

    def toggle_library_panel(self) -> None:
        self.status.set("Library is now available from the Insert menu")

    def toggle_library_popout(self) -> None:
        self.status.set("Library is now available from the Insert menu")

    def _close_library_popout(self) -> None:
        self._library_popout = None

    def toggle_inspector_popout(self) -> None:
        if self._panel_state["inspector"]["undocked"]:
            self._close_inspector_popout()
            self.status.set("Inspector redocked")
            return

        self._panel_state["inspector"]["undocked"] = True
        self.side_tabs.tab(self.inspector_frame, state="hidden")
        self._inspector_popout = tk.Toplevel(self)
        self._inspector_popout.title("Inspector")
        self._inspector_popout.geometry("520x860")
        self._inspector_popout.protocol("WM_DELETE_WINDOW", self._close_inspector_popout)

        outer = ttk.Frame(self._inspector_popout)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(outer, background="#18202c", highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        self._inspector_popup_host = ttk.Frame(canvas, style="PanelBody.TFrame")
        window_id = canvas.create_window((0, 0), window=self._inspector_popup_host, anchor="nw")
        self._inspector_popup_host.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))

        self._popup_inspector = ComponentInspector(
            self._inspector_popup_host,
            self.circuit,
            on_apply=self._on_inspector_apply,
            on_solve=self.request_solve,
            on_dirty=self._on_inspector_dirty,
        )
        self._popup_inspector.pack(fill="both", expand=True, padx=8, pady=8)
        self._popup_inspector.load_component(self._selection_id)
        self._refresh_panel_button_labels()

    def _close_inspector_popout(self) -> None:
        if self._inspector_popout is not None and self._inspector_popout.winfo_exists():
            self._inspector_popout.destroy()
        self._panel_state["inspector"]["undocked"] = False
        self.side_tabs.tab(self.inspector_frame, state="normal")
        self._inspector_popout = None
        self._popup_inspector = None
        self._inspector_popup_host = None
        self._refresh_panel_button_labels()

    def toggle_results_popout(self) -> None:
        if self._panel_state["results"]["undocked"]:
            self._close_results_popout()
            self.status.set("Results redocked")
            return

        self._panel_state["results"]["undocked"] = True
        self.side_tabs.tab(self.results_frame, state="hidden")
        self._results_popout = tk.Toplevel(self)
        self._results_popout.title("Results")
        self._results_popout.geometry("760x540")
        self._results_popout.protocol("WM_DELETE_WINDOW", self._close_results_popout)

        container = ttk.Frame(self._results_popout)
        container.pack(fill="both", expand=True, padx=8, pady=8)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self._popup_results_text = tk.Text(container, wrap="word", background="#0b0f14", foreground="#e9eef7", insertbackground="#e9eef7")
        self._popup_results_text.grid(row=0, column=0, sticky="nsew")
        self._popup_results_scroll = ttk.Scrollbar(container, orient="vertical", command=self._popup_results_text.yview)
        self._popup_results_scroll.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        self._popup_results_text.configure(yscrollcommand=self._popup_results_scroll.set)
        self._refresh_results_text(None)
        self._refresh_panel_button_labels()

    def _close_results_popout(self) -> None:
        if self._results_popout is not None and self._results_popout.winfo_exists():
            self._results_popout.destroy()
        self._panel_state["results"]["undocked"] = False
        self.side_tabs.tab(self.results_frame, state="normal")
        self._results_popout = None
        self._popup_results_text = None
        self._popup_results_scroll = None
        self._refresh_panel_button_labels()


def run_app() -> None:
    root = tk.Tk()
    app = HeatCircuitApp(root)
    root.mainloop()
