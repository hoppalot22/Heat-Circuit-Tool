# Python API Reference

This reference documents every Python source file in the workspace and is organized for rapid onboarding.

## How To Use This Reference

- Start with a module section to understand responsibility boundaries.
- For each class, review Constructor to understand required setup and persisted state.
- Use method and function sections as implementation entry points when debugging or extending behavior.

## Module Index

- [run_heat_circuit_tool.py](#runheatcircuittoolpy)
- [heat_circuit_tool/__init__.py](#heatcircuittoolinitpy)
- [heat_circuit_tool/demo.py](#heatcircuittooldemopy)
- [heat_circuit_tool/model.py](#heatcircuittoolmodelpy)
- [heat_circuit_tool/persistence.py](#heatcircuittoolpersistencepy)
- [heat_circuit_tool/presets.py](#heatcircuittoolpresetspy)
- [heat_circuit_tool/solve_logging.py](#heatcircuittoolsolveloggingpy)
- [heat_circuit_tool/solver.py](#heatcircuittoolsolverpy)
- [heat_circuit_tool/thermo.py](#heatcircuittoolthermopy)
- [heat_circuit_tool/unit_system.py](#heatcircuittoolunitsystempy)
- [heat_circuit_tool/units.py](#heatcircuittoolunitspy)
- [heat_circuit_tool/ui/__init__.py](#heatcircuittooluiinitpy)
- [heat_circuit_tool/ui/canvas.py](#heatcircuittooluicanvaspy)
- [heat_circuit_tool/ui/cycle_diagram.py](#heatcircuittooluicyclediagrampy)
- [heat_circuit_tool/ui/inspector.py](#heatcircuittooluiinspectorpy)
- [heat_circuit_tool/ui/main_window.py](#heatcircuittooluimainwindowpy)
- [heat_circuit_tool/ui/path_finder.py](#heatcircuittooluipathfinderpy)

## run_heat_circuit_tool.py
<a id="runheatcircuittoolpy"></a>

### Purpose
Application entry point that validates runtime dependencies and launches the desktop UI.

### Classes
None.

### Module Functions
- No module-level functions.

## heat_circuit_tool/__init__.py
<a id="heatcircuittoolinitpy"></a>

### Purpose
Package export surface for the core modeling, solving, and demo-building APIs.

### Classes
None.

### Module Functions
- No module-level functions.

## heat_circuit_tool/demo.py
<a id="heatcircuittooldemopy"></a>

### Purpose
Builds a ready-to-run reheat Rankine cycle circuit used for onboarding and regression smoke checks.

### Classes
None.

### Module Functions
- build_reheat_rankine_demo(): Primary workflow method exposed for module or class consumers.

## heat_circuit_tool/model.py
<a id="heatcircuittoolmodelpy"></a>

### Purpose
Core domain model: components, thermodynamic specs, graph connectivity, and traversal helpers.

### Classes

#### ComponentKind
Project domain class used within modeling, solving, or UI workflows.

Constructor
- Signature: Uses default object constructor.

Methods
- No explicit methods defined in this class body.

#### ProcessKind
Project domain class used within modeling, solving, or UI workflows.

Constructor
- Signature: Uses default object constructor.

Methods
- No explicit methods defined in this class body.

#### PortRole
Project domain class used within modeling, solving, or UI workflows.

Constructor
- Signature: Uses default object constructor.

Methods
- No explicit methods defined in this class body.

#### ThermoSpec
Configuration/specification object describing user or solver constraints.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: pressure_mpa, temperature_c, enthalpy_kj_kg, entropy_kj_kgk, quality, specific_volume_m3_kg, efficiency, heat_duty_kw, pressure_drop_mpa, mass_flow_kg_s, pipe_length_m, pipe_outer_diameter_m, pipe_wall_thickness_m, pipe_roughness_m, elevation_change_m, local_loss_coefficient.

Methods
- to_state_spec(self): Transforms data between internal and external representations.
- defined_count(self): Primary workflow method exposed for module or class consumers.
- pretty(self): Primary workflow method exposed for module or class consumers.

#### Component
Project domain class used within modeling, solving, or UI workflows.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: component_id, kind, process_kind, name, x, y, width, height, inlet_spec, outlet_spec, notes, upstream_ids, downstream_ids, inlet_state, outlet_state, unit_preferences, inlet_definition_mode, outlet_definition_mode, user_input_fields, solved_fields, conflicting_fields, is_dirty, report.

Methods
- upstream_id(self): Primary workflow method exposed for module or class consumers.
- upstream_id(self, value): Primary workflow method exposed for module or class consumers.
- downstream_id(self): Primary workflow method exposed for module or class consumers.
- downstream_id(self, value): Primary workflow method exposed for module or class consumers.
- center(self): Primary workflow method exposed for module or class consumers.
- inlet_port(self): Primary workflow method exposed for module or class consumers.
- outlet_port(self): Primary workflow method exposed for module or class consumers.
- reset_results(self): Primary workflow method exposed for module or class consumers.
- label(self): Primary workflow method exposed for module or class consumers.

#### Circuit
Project domain class used within modeling, solving, or UI workflows.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: components, start_component_id, seed_state, seed_description.

Methods
- add_component(self, component): Creates and registers a new domain object or UI element.
- remove_component(self, component_id): Removes an object from the active model or UI context.
- connect(self, source_id, target_id): Primary workflow method exposed for module or class consumers.
- disconnect(self, source_id, target_id): Primary workflow method exposed for module or class consumers.
- outgoing(self, component_id): Primary workflow method exposed for module or class consumers.
- incoming(self, component_id): Primary workflow method exposed for module or class consumers.
- ordered_path(self, start_id=..., max_steps=...): Computes or refines routing geometry for graph connections.
- traversal_order(self, start_id=..., max_steps=...): Primary workflow method exposed for module or class consumers.

### Module Functions
- No module-level functions.

## heat_circuit_tool/persistence.py
<a id="heatcircuittoolpersistencepy"></a>

### Purpose
Serialization and project file I/O for circuits, snapshots, and solved-state metadata.

### Classes
None.

### Module Functions
- _spec_to_dict(spec): Internal helper used to keep public workflows modular and testable.
- _spec_from_dict(data): Internal helper used to keep public workflows modular and testable.
- _state_to_dict(state): Internal helper used to keep public workflows modular and testable.
- _state_from_dict(data): Internal helper used to keep public workflows modular and testable.
- circuit_to_dict(circuit): Primary workflow method exposed for module or class consumers.
- circuit_from_dict(data): Primary workflow method exposed for module or class consumers.
- save_project_file(file_path, circuit, snapshots, latest_solved=...): Persists current project/model state to storage.
- load_project_file(file_path): Loads and applies persisted or in-memory project state.

## heat_circuit_tool/presets.py
<a id="heatcircuittoolpresetspy"></a>

### Purpose
Component preset catalog and helpers that apply process defaults to newly created components.

### Classes

#### ComponentPreset
Preset descriptor used to seed component defaults consistently.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: name, kind, process_kind, inlet_spec, outlet_spec, notes.

Methods
- No explicit methods defined in this class body.

### Module Functions
- preset_names(): Primary workflow method exposed for module or class consumers.
- apply_preset(component, preset_name): Primary workflow method exposed for module or class consumers.

## heat_circuit_tool/solve_logging.py
<a id="heatcircuittoolsolveloggingpy"></a>

### Purpose
Structured JSONL solve diagnostics logger used for post-run analysis and debugging.

### Classes
None.

### Module Functions
- _state_to_dict(state): Internal helper used to keep public workflows modular and testable.
- _component_debug(circuit): Internal helper used to keep public workflows modular and testable.
- append_solve_log(log_file_path, circuit, solution): Solves or evaluates thermodynamic/process state based on available constraints.

## heat_circuit_tool/solver.py
<a id="heatcircuittoolsolverpy"></a>

### Purpose
Thermodynamic circuit solver, reverse/forward component solve logic, and live constraint diagnostics.

### Classes

#### ComponentResult
Result data object containing solved values and status summaries.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: component_id, component_name, kind, process_kind, inlet_state, outlet_state, work_kj_kg, heat_kj_kg, status, conflicting_fields, message.

Methods
- No explicit methods defined in this class body.

#### CircuitSolution
Result data object containing solved values and status summaries.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: component_results, total_heat_in_kj_kg, total_heat_out_kj_kg, total_turbine_work_kj_kg, total_pump_work_kj_kg, net_work_kj_kg, thermal_efficiency, back_work_ratio, closure_error_h_kj_kg, closure_error_p_mpa, system_status, underconstrained_components, overconstrained_components, unsolved_components, messages.

Methods
- summary_lines(self): Primary workflow method exposed for module or class consumers.

#### ComponentConstraintDiagnostic
Structured diagnostics payload used for live and post-solve status reporting.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: component_id, component_name, status, message, inlet_available, additional_info_required, missing_fields.

Methods
- No explicit methods defined in this class body.

#### ConstraintDiagnostics
Structured diagnostics payload used for live and post-solve status reporting.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: system_status, component_diagnostics, underconstrained_components, overconstrained_components, blocked_components, total_additional_info_required, frontier_min_additional_info, propagation_hint.

Methods
- summary_lines(self): Primary workflow method exposed for module or class consumers.

#### SolverError
Domain solver that resolves thermodynamic states and consistency diagnostics.

Constructor
- Signature: Uses default object constructor.

Methods
- No explicit methods defined in this class body.

#### ConstraintReport
Project domain class used within modeling, solving, or UI workflows.

Constructor
- Signature: __init__(self, status, message)
- Notes: Constructor parameters should be treated as the minimum required runtime wiring for this class.

Methods
- __init__(self, status, message): Initializes class state and required collaborators.

#### ThermoSolver
Domain solver that resolves thermodynamic states and consistency diagnostics.

Constructor
- Signature: __init__(self, backend=...)
- Notes: Constructor parameters should be treated as the minimum required runtime wiring for this class.

Methods
- __init__(self, backend=...): Initializes class state and required collaborators.
- solve_circuit(self, circuit): Solves or evaluates thermodynamic/process state based on available constraints.
- _resolve_inlet_state(self, circuit, component): Solves or evaluates thermodynamic/process state based on available constraints.
- _resolve_outlet_state(self, circuit, component): Solves or evaluates thermodynamic/process state based on available constraints.
- _state_from_thermo_spec(self, spec): Internal helper used to keep public workflows modular and testable.
- _state_matches_optional_fields(self, state, spec): Internal helper used to keep public workflows modular and testable.
- _mix_states(self, states): Internal helper used to keep public workflows modular and testable.
- _state_changed(self, previous, current): Internal helper used to keep public workflows modular and testable.
- _accumulate_metrics(self, solution): Internal helper used to keep public workflows modular and testable.
- _evaluate_closure(self, circuit, solution): Internal helper used to keep public workflows modular and testable.
- _evaluate_constraints(self, solution): Internal helper used to keep public workflows modular and testable.
- _evaluate_connectivity(self, circuit, solution): Internal helper used to keep public workflows modular and testable.
- solve_component(self, component, inlet_state, outlet_state_hint): Solves or evaluates thermodynamic/process state based on available constraints.
- _solve_component_reverse(self, component, outlet_state): Solves or evaluates thermodynamic/process state based on available constraints.
- _reverse_isenthalpic_component(self, component, outlet_state): Internal helper used to keep public workflows modular and testable.
- _reverse_isentropic_machine(self, component, outlet_state): Internal helper used to keep public workflows modular and testable.
- _has_state_definition(self, spec): Internal helper used to keep public workflows modular and testable.
- _fixed_constraint_conflicts(self, component, inlet_state, outlet_state): Internal helper used to keep public workflows modular and testable.
- _is_conflict(self, expected, actual, tolerance): Internal helper used to keep public workflows modular and testable.
- _solve_pipe_component(self, component, inlet_state): Solves or evaluates thermodynamic/process state based on available constraints.
- _solve_pass_through_component(self, component, inlet_state): Solves or evaluates thermodynamic/process state based on available constraints.
- _solve_isentropic_component(self, component, inlet_state): Solves or evaluates thermodynamic/process state based on available constraints.
- _solve_isenthalpic_component(self, component, inlet_state, outlet_spec): Solves or evaluates thermodynamic/process state based on available constraints.
- _solve_isobaric_component(self, component, inlet_state, outlet_spec): Solves or evaluates thermodynamic/process state based on available constraints.
- _solve_isochoric_component(self, component, inlet_state, outlet_spec): Solves or evaluates thermodynamic/process state based on available constraints.
- _solve_adiabatic_component(self, component, inlet_state, outlet_spec): Solves or evaluates thermodynamic/process state based on available constraints.
- _solve_general_component(self, outlet_spec): Solves or evaluates thermodynamic/process state based on available constraints.
- _constraint_report(self, component, inlet_state, outlet_state): Internal helper used to keep public workflows modular and testable.

### Module Functions
- solve_circuit(circuit, backend=...): Solves or evaluates thermodynamic/process state based on available constraints.
- analyze_constraint_system(circuit): Primary workflow method exposed for module or class consumers.
- _diagnostic_inlet_available(circuit, component, outlet_available, start_id, has_seed): Internal helper used to keep public workflows modular and testable.
- _diagnostic_missing_fields(component, inlet_available): Internal helper used to keep public workflows modular and testable.
- _diagnostic_overconstraint_flags(component): Internal helper used to keep public workflows modular and testable.

## heat_circuit_tool/thermo.py
<a id="heatcircuittoolthermopy"></a>

### Purpose
Steam property backend wrapper around IAPWS97 plus state/spec abstractions.

### Classes

#### ThermoState
Thermodynamic state container representing a fully solved fluid point.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: pressure_mpa, temperature_c, enthalpy_kj_kg, entropy_kj_kgk, specific_volume_m3_kg, dynamic_viscosity_pa_s, quality.

Methods
- as_dict(self): Primary workflow method exposed for module or class consumers.
- brief(self): Primary workflow method exposed for module or class consumers.
- temperature_k(self): Primary workflow method exposed for module or class consumers.
- density_kg_m3(self): Primary workflow method exposed for module or class consumers.

#### StateSpec
Thermodynamic state container representing a fully solved fluid point.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: pressure_mpa, temperature_c, enthalpy_kj_kg, entropy_kj_kgk, quality, specific_volume_m3_kg.

Methods
- defined_fields(self): Primary workflow method exposed for module or class consumers.
- is_empty(self): Primary workflow method exposed for module or class consumers.
- pretty(self): Primary workflow method exposed for module or class consumers.

#### SteamPropertyBackend
Service wrapper around property libraries and domain-level state generation.

Constructor
- Signature: Uses default object constructor.

Methods
- make_state(self, spec): Primary workflow method exposed for module or class consumers.
- state_from_pressure_temperature(self, pressure_mpa, temperature_c): Primary workflow method exposed for module or class consumers.
- state_from_pressure_enthalpy(self, pressure_mpa, enthalpy_kj_kg): Primary workflow method exposed for module or class consumers.
- state_from_pressure_entropy(self, pressure_mpa, entropy_kj_kgk): Primary workflow method exposed for module or class consumers.
- state_from_pressure_quality(self, pressure_mpa, quality): Primary workflow method exposed for module or class consumers.
- _to_state(self, water): Internal helper used to keep public workflows modular and testable.
- same_state(self, left, right, tolerance=...): Primary workflow method exposed for module or class consumers.

### Module Functions
- No module-level functions.

## heat_circuit_tool/unit_system.py
<a id="heatcircuittoolunitsystempy"></a>

### Purpose
Unit conversion registry and display normalization helpers for inspector fields and reports.

### Classes

#### UnitDef
Project domain class used within modeling, solving, or UI workflows.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: name, to_internal, from_internal.

Methods
- No explicit methods defined in this class body.

### Module Functions
- unit_names(field_name): Primary workflow method exposed for module or class consumers.
- default_unit(field_name): Primary workflow method exposed for module or class consumers.
- to_internal(field_name, value, unit_name): Transforms data between internal and external representations.
- from_internal(field_name, value, unit_name): Transforms data between internal and external representations.
- is_numeric_field(field_name): Primary workflow method exposed for module or class consumers.
- best_prefixed_display(field_name, internal_value, preferred_unit): Primary workflow method exposed for module or class consumers.

## heat_circuit_tool/units.py
<a id="heatcircuittoolunitspy"></a>

### Purpose
Low-level unit constants and helper conversions used across the thermodynamic stack.

### Classes
None.

### Module Functions
- c_to_k(value_c): Primary workflow method exposed for module or class consumers.
- k_to_c(value_k): Primary workflow method exposed for module or class consumers.
- mpa_to_pa(value_mpa): Primary workflow method exposed for module or class consumers.
- pa_to_mpa(value_pa): Primary workflow method exposed for module or class consumers.
- almost_equal(left, right, tolerance=...): Primary workflow method exposed for module or class consumers.
- format_optional(value, precision=...): Primary workflow method exposed for module or class consumers.

## heat_circuit_tool/ui/__init__.py
<a id="heatcircuittooluiinitpy"></a>

### Purpose
UI package marker for Tkinter-based panels and canvas widgets.

### Classes
None.

### Module Functions
- No module-level functions.

## heat_circuit_tool/ui/canvas.py
<a id="heatcircuittooluicanvaspy"></a>

### Purpose
Interactive node canvas for component layout, port management, and routed connection rendering.

### Classes

#### NodeCanvas
Interactive drawing surface for component graph layout and connection editing.

Constructor
- Signature: __init__(self, master, circuit, on_select, **kwargs)
- Notes: Constructor parameters should be treated as the minimum required runtime wiring for this class.

Methods
- __init__(self, master, circuit, on_select, **kwargs): Initializes class state and required collaborators.
- set_circuit(self, circuit): Setter-style method that updates internal state and dependent views.
- select_component(self, component_id): Primary workflow method exposed for module or class consumers.
- redraw(self): Primary workflow method exposed for module or class consumers.
- _build_component_bounds(self): Internal helper used to keep public workflows modular and testable.
- _world_to_view(self, x, y): Internal helper used to keep public workflows modular and testable.
- _view_to_world(self, x, y): Internal helper used to keep public workflows modular and testable.
- _draw_grid(self): Rendering routine responsible for visual output updates.
- _draw_connections(self): Rendering routine responsible for visual output updates.
- _port_direction_for_point(self, component_id, point, role): Internal helper used to keep public workflows modular and testable.
- _assign_all_connection_ports(self): Internal helper used to keep public workflows modular and testable.
- _separate_component_port_overlaps(self, component_id): Internal helper used to keep public workflows modular and testable.
- _peer_projection_for_port_key(self, port_key, side): Internal helper used to keep public workflows modular and testable.
- _point_side_for_port(self, component_id, point): Internal helper used to keep public workflows modular and testable.
- _offset_point_along_side(self, component_id, side, point, offset): Internal helper used to keep public workflows modular and testable.
- _assign_component_role_ports(self, component_id, role, peer_ids): Internal helper used to keep public workflows modular and testable.
- _preferred_sides(self, component_id, peer_id): Internal helper used to keep public workflows modular and testable.
- _side_capacity(self, component, side): Internal helper used to keep public workflows modular and testable.
- _ordered_peers_for_side(self, component_id, side, peers): Internal helper used to keep public workflows modular and testable.
- _evenly_spaced_points_on_side(self, component, side, count): Internal helper used to keep public workflows modular and testable.
- _register_port_point(self, component_id, role, point): Internal helper used to keep public workflows modular and testable.
- _port_spacing_penalty(self, component_id, role, point): Internal helper used to keep public workflows modular and testable.
- _connection_port_candidates(self, component_id, peer_id, role): Internal helper used to keep public workflows modular and testable.
- _route_connection_points(self, source_id, target_id, x1, y1, x2, y2, existing_segments): Computes or refines routing geometry for graph connections.
- _orthogonal_intersection_point(self, p1, p2, q1, q2): Internal helper used to keep public workflows modular and testable.
- _bridge_points_for_route(self, route_points, existing_segments): Computes or refines routing geometry for graph connections.
- _draw_bridge_arc(self, xw, yw, orientation, color, line_width): Rendering routine responsible for visual output updates.
- _simplify_polyline(self, points): Internal helper used to keep public workflows modular and testable.
- _route_penalty(self, source_id, target_id, points): Computes or refines routing geometry for graph connections.
- _segment_intersects_rect(self, p1, p2, rect, pad=...): Internal helper used to keep public workflows modular and testable.
- _draw_components(self): Rendering routine responsible for visual output updates.
- _draw_component(self, component): Rendering routine responsible for visual output updates.
- _component_at_world(self, event_x, event_y): Internal helper used to keep public workflows modular and testable.
- _port_at(self, item_id): Internal helper used to keep public workflows modular and testable.
- _on_left_press(self, event): Event handler used by the UI interaction loop.
- _on_left_drag(self, event): Event handler used by the UI interaction loop.
- _on_left_release(self, event): Event handler used by the UI interaction loop.
- _schedule_drag_redraw(self): Internal helper used to keep public workflows modular and testable.
- _flush_drag_redraw(self): Internal helper used to keep public workflows modular and testable.
- _on_double_click(self, event): Event handler used by the UI interaction loop.
- _on_right_click(self, event): Event handler used by the UI interaction loop.
- _on_middle_press(self, event): Event handler used by the UI interaction loop.
- _on_middle_drag(self, event): Event handler used by the UI interaction loop.
- _on_middle_release(self, event): Event handler used by the UI interaction loop.
- _on_mouse_wheel(self, event): Event handler used by the UI interaction loop.

### Module Functions
- No module-level functions.

## heat_circuit_tool/ui/cycle_diagram.py
<a id="heatcircuittooluicyclediagrampy"></a>

### Purpose
Matplotlib-backed thermodynamic diagram panel with configurable property axes and isolines.

### Classes

#### AxisSpec
Configuration/specification object describing user or solver constraints.

Constructor
- Signature: Auto-generated dataclass constructor.
- Parameters: key, label.

Methods
- No explicit methods defined in this class body.

#### CycleDiagramPanel
Project domain class used within modeling, solving, or UI workflows.

Constructor
- Signature: __init__(self, master)
- Notes: Constructor parameters should be treated as the minimum required runtime wiring for this class.

Methods
- __init__(self, master): Initializes class state and required collaborators.
- _logspace(self, start, stop, count): Internal helper used to keep public workflows modular and testable.
- set_solution(self, circuit, solution): Setter-style method that updates internal state and dependent views.
- redraw(self): Primary workflow method exposed for module or class consumers.
- _draw_labels(self, x_key, y_key): Rendering routine responsible for visual output updates.
- _axis_label(self, key): Internal helper used to keep public workflows modular and testable.
- _value(self, state, key): Internal helper used to keep public workflows modular and testable.
- _is_far_from_labels(self, x, y, x_span, y_span): Internal helper used to keep public workflows modular and testable.
- _approx_text_box(self, x, y, text, fontsize, x_span, y_span): Internal helper used to keep public workflows modular and testable.
- _boxes_overlap(self, a, b): Internal helper used to keep public workflows modular and testable.
- _label_box_is_clear(self, box, x_span, y_span): Internal helper used to keep public workflows modular and testable.
- _place_label_near(self, base_x, base_y, text, color=..., fontsize=..., align=...): Internal helper used to keep public workflows modular and testable.
- _draw_legend(self): Rendering routine responsible for visual output updates.
- _plot_solution_states(self, x_key, y_key): Rendering routine responsible for visual output updates.
- _plot_property_isolines(self, x_key, y_key): Rendering routine responsible for visual output updates.
- _plot_iso_pressure_lines(self, x_key, y_key): Rendering routine responsible for visual output updates.
- _plot_iso_temperature_lines(self, x_key, y_key): Rendering routine responsible for visual output updates.
- _plot_iso_enthalpy_lines(self, x_key, y_key): Rendering routine responsible for visual output updates.
- _plot_iso_entropy_lines(self, x_key, y_key): Rendering routine responsible for visual output updates.
- _plot_iso_specific_volume_lines(self, x_key, y_key): Rendering routine responsible for visual output updates.
- _solve_state_from_pressure_volume(self, pressure_mpa, target_v): Solves or evaluates thermodynamic/process state based on available constraints.
- _plot_quality_isolines(self, x_key, y_key): Rendering routine responsible for visual output updates.

### Module Functions
- No module-level functions.

## heat_circuit_tool/ui/inspector.py
<a id="heatcircuittooluiinspectorpy"></a>

### Purpose
Component inspector/editor with unit-aware fields, solve highlights, and definition-mode controls.

### Classes

#### ComponentInspector
Inspector panel used to edit component constraints and inspect solve results.

Constructor
- Signature: __init__(self, master, circuit, on_apply=..., on_solve=..., on_dirty=..., **kwargs)
- Notes: Constructor parameters should be treated as the minimum required runtime wiring for this class.

Methods
- __init__(self, master, circuit, on_apply=..., on_solve=..., on_dirty=..., **kwargs): Initializes class state and required collaborators.
- _build(self): Internal helper used to keep public workflows modular and testable.
- _definition_fields_for_mode(self, prefix, mode): Internal helper used to keep public workflows modular and testable.
- _active_fields_for(self, kind, process, inlet_mode, outlet_mode): Internal helper used to keep public workflows modular and testable.
- _update_field_visibility(self, kind, process, inlet_mode, outlet_mode): Internal helper used to keep public workflows modular and testable.
- _make_unit_placeholder(self, row): Internal helper used to keep public workflows modular and testable.
- _make_unit_selector(self, row, field_name): Internal helper used to keep public workflows modular and testable.
- load_component(self, component_id): Loads and applies persisted or in-memory project state.
- apply_to_component(self): Primary workflow method exposed for module or class consumers.
- apply_solution_to_component(self, component_id, inlet_state, outlet_state, conflicting_fields=...): Primary workflow method exposed for module or class consumers.
- show_solution(self, solution): Primary workflow method exposed for module or class consumers.
- solution_text(self): Primary workflow method exposed for module or class consumers.
- _state_line(self, component, state, prefix): Internal helper used to keep public workflows modular and testable.
- _parse_and_track(self, component, field_name): Internal helper used to keep public workflows modular and testable.
- _format(self, value): Internal helper used to keep public workflows modular and testable.
- _coerce_float(self, value): Internal helper used to keep public workflows modular and testable.
- _ensure_unit_prefs(self, component): Internal helper used to keep public workflows modular and testable.
- _on_unit_changed(self, field_name): Event handler used by the UI interaction loop.
- _on_any_field_modified(self, field_name): Event handler used by the UI interaction loop.
- _clear_highlights_dirty(self, component): Internal helper used to keep public workflows modular and testable.
- _apply_highlights(self, component): Internal helper used to keep public workflows modular and testable.
- _is_overdefined_for_non_general(self, component): Internal helper used to keep public workflows modular and testable.
- solve_requested(self): Solves or evaluates thermodynamic/process state based on available constraints.

### Module Functions
- No module-level functions.

## heat_circuit_tool/ui/main_window.py
<a id="heatcircuittooluimainwindowpy"></a>

### Purpose
Top-level application shell that orchestrates panels, persistence, solve flow, and diagnostics.

### Classes

#### HeatCircuitApp
Top-level application coordinator that composes UI panels and command workflows.

Constructor
- Signature: __init__(self, master)
- Notes: Constructor parameters should be treated as the minimum required runtime wiring for this class.

Methods
- __init__(self, master): Initializes class state and required collaborators.
- _apply_seed_as_user_constraints(self): Internal helper used to keep public workflows modular and testable.
- _derive_log_path(self, project_path): Computes or refines routing geometry for graph connections.
- _build_style(self): Internal helper used to keep public workflows modular and testable.
- _build_ui(self): Internal helper used to keep public workflows modular and testable.
- _build_insert_menu(self): Internal helper used to keep public workflows modular and testable.
- refresh_all(self): Primary workflow method exposed for module or class consumers.
- on_canvas_select(self, component_id): Primary workflow method exposed for module or class consumers.
- add_component(self, kind, process): Creates and registers a new domain object or UI element.
- add_selected_preset(self): Creates and registers a new domain object or UI element.
- add_preset_by_name(self, preset_name): Creates and registers a new domain object or UI element.
- delete_selected_component(self, event=...): Removes an object from the active model or UI context.
- request_solve(self): Solves or evaluates thermodynamic/process state based on available constraints.
- _prepare_circuit_for_user_constrained_solve(self): Solves or evaluates thermodynamic/process state based on available constraints.
- _on_inspector_apply(self): Event handler used by the UI interaction loop.
- _on_inspector_dirty(self): Event handler used by the UI interaction loop.
- _refresh_results_text(self, solution): Internal helper used to keep public workflows modular and testable.
- load_demo(self): Loads and applies persisted or in-memory project state.
- revert_latest_solve(self): Solves or evaluates thermodynamic/process state based on available constraints.
- save_snapshot(self): Persists current project/model state to storage.
- rename_snapshot(self): Primary workflow method exposed for module or class consumers.
- _on_snapshot_selected(self, _event=...): Event handler used by the UI interaction loop.
- _upsert_snapshot(self, name, circuit_dict): Internal helper used to keep public workflows modular and testable.
- _refresh_snapshot_combo(self, selected=...): Internal helper used to keep public workflows modular and testable.
- save_project(self): Persists current project/model state to storage.
- load_project(self): Loads and applies persisted or in-memory project state.
- _restore_circuit_dict(self, circuit_dict): Internal helper used to keep public workflows modular and testable.
- _update_live_diagnostics(self): Internal helper used to keep public workflows modular and testable.
- _pane_contains(self, pane, widget): Internal helper used to keep public workflows modular and testable.
- _bind_recursive(self, widget, sequence, callback): Internal helper used to keep public workflows modular and testable.
- _bind_panel_scroll_events(self): Internal helper used to keep public workflows modular and testable.
- _set_wheel_target(self, target): Internal helper used to keep public workflows modular and testable.
- _clear_wheel_target(self, target): Internal helper used to keep public workflows modular and testable.
- _on_global_mouse_wheel(self, event): Event handler used by the UI interaction loop.
- _bind_drag(self, key, header, title): Internal helper used to keep public workflows modular and testable.
- _bind_resize(self, key, handle): Internal helper used to keep public workflows modular and testable.
- _start_panel_resize(self, key, event): Internal helper used to keep public workflows modular and testable.
- _resize_panel(self, key, event): Internal helper used to keep public workflows modular and testable.
- _layout_floating_panels(self): Internal helper used to keep public workflows modular and testable.
- _clamp_floating_panels(self): Internal helper used to keep public workflows modular and testable.
- _start_panel_drag(self, key, event): Internal helper used to keep public workflows modular and testable.
- _drag_panel(self, key, event): Internal helper used to keep public workflows modular and testable.
- _on_workspace_resize(self, _event=...): Event handler used by the UI interaction loop.
- _set_panel_collapsed(self, key, collapsed): Internal helper used to keep public workflows modular and testable.
- _refresh_panel_button_labels(self): Internal helper used to keep public workflows modular and testable.
- toggle_library_panel(self): Primary workflow method exposed for module or class consumers.
- toggle_inspector_panel(self): Primary workflow method exposed for module or class consumers.
- toggle_results_panel(self): Primary workflow method exposed for module or class consumers.
- toggle_library_popout(self): Primary workflow method exposed for module or class consumers.
- _close_library_popout(self): Internal helper used to keep public workflows modular and testable.
- toggle_inspector_popout(self): Primary workflow method exposed for module or class consumers.
- _close_inspector_popout(self): Internal helper used to keep public workflows modular and testable.
- toggle_results_popout(self): Primary workflow method exposed for module or class consumers.
- _close_results_popout(self): Internal helper used to keep public workflows modular and testable.

### Module Functions
- run_app(): Primary workflow method exposed for module or class consumers.

## heat_circuit_tool/ui/path_finder.py
<a id="heatcircuittooluipathfinderpy"></a>

### Purpose
Orthogonal routing engine for connection lines with obstacle avoidance and cleanup passes.

### Classes

#### OrthogonalPathFinder
Project domain class used within modeling, solving, or UI workflows.

Constructor
- Signature: __init__(self, component_bounds, text_obstacles)
- Notes: Constructor parameters should be treated as the minimum required runtime wiring for this class.

Methods
- __init__(self, component_bounds, text_obstacles): Initializes class state and required collaborators.
- route_connection(self, source_id, target_id, x1, y1, x2, y2, source_direction, target_direction, existing_segments): Computes or refines routing geometry for graph connections.
- _polyline_hits_text(self, points): Internal helper used to keep public workflows modular and testable.
- _reroute_around_text(self, points, source_id, target_id): Computes or refines routing geometry for graph connections.
- _compose_route_with_stubs(self, source_port, source_stub, core_points, target_stub, target_port): Computes or refines routing geometry for graph connections.
- _simplify_preserving_terminal_stubs(self, points): Internal helper used to keep public workflows modular and testable.
- _fallback_route_candidates(self, x1, y1, x2, y2): Computes or refines routing geometry for graph connections.
- _normalize_route_geometry(self, points): Computes or refines routing geometry for graph connections.
- _axis_distance(self, p1, p2): Internal helper used to keep public workflows modular and testable.
- _segment_direction(self, p1, p2): Internal helper used to keep public workflows modular and testable.
- _protrusion_anchor(self, port, direction, obstacles, min_distance): Internal helper used to keep public workflows modular and testable.
- _optimize_orthogonal_polyline(self, points, source_id, target_id): Internal helper used to keep public workflows modular and testable.
- _orthogonal_connectors(self, start, end): Internal helper used to keep public workflows modular and testable.
- _polyline_length(self, points): Internal helper used to keep public workflows modular and testable.
- _segment_hits_obstacles(self, p1, p2, obstacles): Internal helper used to keep public workflows modular and testable.
- _polyline_hits_obstacles(self, points, source_id, target_id, pad): Internal helper used to keep public workflows modular and testable.
- _route_obstacles(self, source_id, target_id, pad): Computes or refines routing geometry for graph connections.
- _segment_hits_component_with_endpoint_allowance(self, p1, p2, component_id, rect, pad, source_id, target_id, segment_index, total_segments): Internal helper used to keep public workflows modular and testable.
- _in_obstacle(self, point, obstacles): Internal helper used to keep public workflows modular and testable.
- _a_star_route(self, start, end, obstacles, grid, existing_segments): Computes or refines routing geometry for graph connections.
- _crossing_penalty(self, from_node, to_node, grid, existing_segments): Internal helper used to keep public workflows modular and testable.
- _route_penalty(self, source_id, target_id, points): Computes or refines routing geometry for graph connections.
- _segment_intersects_rect(self, p1, p2, rect, pad=...): Internal helper used to keep public workflows modular and testable.
- _reduce_tiny_doglegs(self, points, source_id, target_id, min_len=...): Internal helper used to keep public workflows modular and testable.
- _collapse_short_bridge_jogs(self, points, source_id, target_id, max_jog_len=...): Internal helper used to keep public workflows modular and testable.
- _simplify_polyline(self, points): Internal helper used to keep public workflows modular and testable.

### Module Functions
- orthogonal_intersection_point(p1, p2, q1, q2): Primary workflow method exposed for module or class consumers.
