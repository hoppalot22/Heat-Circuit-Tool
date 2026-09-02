# Refactor Plan: Edge-Owned Thermodynamic State

## Status
Not started. This document is a scoping/instruction doc to be executed in a
dedicated session, separate from day-to-day feature work.

## Problem statement
Today, thermodynamic state is duplicated per component: each `Component` owns
its own `inlet_spec`/`outlet_spec` (user-entered targets) and
`inlet_state`/`outlet_state` (solved results), plus per-field bookkeeping sets
(`user_input_fields`, `solved_fields`, `conflicting_fields`). When two
components are connected, the outlet of the upstream component and the inlet
of the downstream component represent the *same physical state*, but are
stored as two independent copies.

This has already caused multiple bugs fixed via UI-layer patches in
`heat_circuit_tool/ui/inspector.py`:
- Solver-computed (non-user) outlet values were flagged as "overconstrained"
  in the inspector even though the user never entered them.
- The inspector had to manually copy values from an upstream outlet into a
  downstream inlet (and vice versa) so the user didn't have to retype known
  values (`_apply_propagated_inlet_fields` / `_propagate_from_neighbor`).
- "User-defined-ness" also had to be manually propagated across the same
  connection so downstream overconstraint checks didn't demand redundant
  re-entry (`_linked_user_fields`).

These are symptoms of state living in the wrong place. The fix is to make the
connection (edge) between two components the single owner of the shared
thermodynamic state, and have both endpoints reference it instead of holding
independent copies.

## Goal
Model each connection between two components (and each "boundary" — the
circuit seed and any dangling terminal ends) as a single shared state object.
A component's "inlet" and "outlet" become *views* onto the edges attached to
it, not independent storage. This eliminates an entire class of
synchronization bugs by construction and simplifies constraint counting
(an edge's degree-of-definition is counted once, not once per side).

## Proposed data model (`model.py`)

```python
@dataclass(slots=True)
class Edge:
    edge_id: str
    spec: ThermoSpec = field(default_factory=ThermoSpec)       # user-entered targets
    state: Optional[ThermoState] = None                          # solved state
    user_input_fields: set[str] = field(default_factory=set)     # unprefixed names, e.g. "pressure_mpa"
    solved_fields: set[str] = field(default_factory=set)
    conflicting_fields: set[str] = field(default_factory=set)
    unit_preferences: dict[str, str] = field(default_factory=dict)
```

Notes on field naming: today fields are stored with an `inlet_`/`outlet_`
prefix (e.g. `inlet_pressure_mpa`). On an `Edge` these become unprefixed
(`pressure_mpa`) since there is no inlet/outlet side anymore — only "the
component upstream of this edge" and "the component downstream of this edge".
The inspector will need to add the prefix back only when mapping to
UI widgets for the currently selected component (see below).

`Component` changes:
- Remove `inlet_spec`, `outlet_spec`, `inlet_state`, `outlet_state`,
  `user_input_fields`, `solved_fields`, `conflicting_fields`.
- Add `inlet_edge_id: str | None` and `outlet_edge_id: str | None` (single
  inlet/outlet edge per component, matching today's `upstream_id`/
  `downstream_id` single-connection model — mixers/splitters are out of scope
  for this refactor, see "Out of scope" below).
- Keep `inlet_definition_mode` / `outlet_definition_mode` and
  `unit_preferences` for now (unit prefs could move to the edge later, but
  that's a separate concern — a component could reasonably want to view the
  same edge in different units for inlet vs outlet display, though this is
  unlikely to matter in practice).

`Circuit` changes:
- Add `edges: dict[str, Edge]`.
- `connect(source_id, target_id)`: instead of only recording
  `upstream_ids`/`downstream_ids`, create (or reuse) an `Edge` and set
  `source.outlet_edge_id = target.inlet_edge_id = edge.edge_id`.
- `disconnect(source_id, target_id)`: clear the shared edge reference on both
  sides. Decide whether to delete the `Edge` object outright (simplest) or
  leave it orphaned. Deleting is cleaner and avoids stale data resurrecting
  itself if reconnected.
- Add a helper `Circuit.edge_for(component_id, side)` (`side` is
  `"inlet"`/`"outlet"`) returning the `Edge` or `None`.
- `remove_component`: also drop/clear edges attached to the removed
  component's ports.
- The circuit `seed_state` remains a special case (there is no upstream
  component for the start component) — keep it as-is, or optionally model it
  as a boundary `Edge` with no upstream component for consistency. Recommend
  keeping `seed_state` as its own field for this pass to limit scope; revisit
  later if it causes friction.

## Affected files and required changes

### `heat_circuit_tool/model.py`
- Add `Edge` dataclass.
- Update `Component` fields as above.
- Update `Circuit.connect`/`disconnect`/`remove_component` to manage edges.
- Add `Circuit.edge_for(...)` helper and any other convenience accessors
  needed by solver/UI (e.g. `Circuit.inlet_edge(component)`,
  `Circuit.outlet_edge(component)`).

### `heat_circuit_tool/solver.py` (largest change — ~90 references today)
- Replace all reads of `component.inlet_spec` / `component.outlet_spec` with
  reads of the edge's `spec` via `circuit.edge_for(component.component_id, "inlet"/"outlet")`.
- Replace all reads/writes of `component.inlet_state` / `component.outlet_state`
  with the edge's `state`.
- `_resolve_inlet_state`/`_resolve_outlet_state`: since inlet and outlet are
  now literally the same edge object as the neighbor's outlet/inlet, these
  methods can likely be simplified — resolving "the inlet state" becomes
  "read `edge.state` if already solved, else derive from `edge.spec` if it has
  ≥2 defined fields, else `None`". The mixing logic for multiple incoming
  connections (mixers) still needs multiple edges per component — see
  "Out of scope".
- `_diagnostic_overconstraint_flags` / `_diagnostic_missing_fields`: field
  counts should be computed per-edge (once) rather than per-component-side.
  This is where the "is this component's process overconstrained" check
  becomes structurally correct: check the inlet edge's defined-field count
  and the outlet edge's defined-field count directly; no separate "linked"
  bookkeeping is needed since there's only one field set per edge.
- Update any function signature that currently takes `ThermoSpec` objects
  pulled from `component.inlet_spec`/`outlet_spec` to instead take the edge
  (or its `.spec`).

### `heat_circuit_tool/persistence.py`
- Add `edge_to_dict`/`edge_from_dict` (mirrors existing `_spec_to_dict`/
  `_state_to_dict`, plus the field-tracking sets).
- `circuit_to_dict`: serialize `circuit.edges`, and change component
  serialization to store `inlet_edge_id`/`outlet_edge_id` instead of
  `inlet_spec`/`outlet_spec`/`inlet_state`/`outlet_state`/`user_input_fields`/
  `solved_fields`/`conflicting_fields`.
- **Backward compatibility**: bump the saved-file `version` field (currently
  `1`). On load, if `version < 2` (or `edges` key is absent), run a
  migration: for each component with legacy `inlet_spec`/`outlet_spec`/etc.,
  synthesize edges — for each `connect`-ed pair, merge the upstream
  component's legacy `outlet_*` data and the downstream component's legacy
  `inlet_*` data into one new `Edge` (prefer non-null values; if both sides
  disagree, prefer the one marked as user input, otherwise flag a conflict
  for the user to review). Components with no connection on a given side
  (start/terminal components) still get an edge with just their own legacy
  data. Write a unit test using a real pre-migration save file (there's an
  example in the repo root: `unsaved_project.solve_log.jsonl` is a solve log,
  not a save file, so create a small fixture `.json` save file representing
  the pre-refactor format for the migration test).

### `heat_circuit_tool/presets.py`
- Presets currently build a template `Component` with its own `inlet_spec`/
  `outlet_spec` and copy field-by-field into a new component
  (`apply_preset`). Update to populate the new component's inlet/outlet edge
  specs instead. Since presets are single, unconnected components, this
  should create a fresh boundary edge for each side.

### `heat_circuit_tool/solve_logging.py`
- Update `component.inlet_spec.pretty()`/`outlet_spec.pretty()` and
  `_state_to_dict(component.inlet_state)`/`outlet_state` calls to pull from
  the edges instead.

### `heat_circuit_tool/ui/inspector.py` (second largest change)
- Remove `_propagated_fields`, `_linked_user_fields`,
  `_apply_propagated_inlet_fields`, `_propagate_from_neighbor` entirely — no
  longer needed, since reading the shared edge naturally shows the same
  value/user-status on both sides.
- `load_component`: read inlet fields from `circuit.edge_for(id, "inlet").spec`
  and outlet fields from `circuit.edge_for(id, "outlet").spec` (falling back
  to a fresh empty `ThermoSpec` if there is no edge yet, e.g. an
  unconnected port).
- `apply_to_component`: write back into the edge's `spec` (creating a
  boundary edge on that port if one doesn't exist yet, e.g. before any
  connection is made) instead of `component.inlet_spec`/`outlet_spec`.
- `apply_solution_to_component`: write solved values into
  `edge.state`/`edge.solved_fields` instead of `component.inlet_state`/etc.
  Since the edge is shared, this single write is now visible to both the
  upstream and downstream component views without any extra propagation
  code — this is the whole point of the refactor.
- `_is_overdefined_for_non_general`: simplify — check the inlet edge's
  and outlet edge's own `user_input_fields` counts directly; delete the
  "linked" workaround.
- `_clear_highlights_dirty` / `_on_any_field_modified` / `_on_unit_changed`:
  update to mutate the edge's `user_input_fields` (unprefixed field names)
  rather than `component.user_input_fields` (prefixed).
- Careful: when the user edits an inlet field for component B, that edit is
  now visible on component A's outlet view too (same edge!). Decide desired
  UX — most likely correct behavior given this refactor's premise — but
  confirm this matches user expectations before finishing, since it's a
  visible behavior change (previously each side was editable independently,
  now editing either endpoint edits the same value system-wide).

### `heat_circuit_tool/ui/canvas.py`
- `component.outlet_state` usage (status coloring, line ~670) → read from
  the outlet edge's `state`.

### `heat_circuit_tool/ui/cycle_diagram.py`
- `result.inlet_state`/`result.outlet_state` come from `ComponentResult`
  (solver output), not directly from `Component` — likely unaffected if
  `ComponentResult` keeps carrying resolved `ThermoState` snapshots. Verify
  after solver changes land.

### `heat_circuit_tool/ui/main_window.py`
- `_apply_seed_to_start_component` (or similarly named, ~line 68): writes
  `component.inlet_spec.*` for the seed — update to write into the start
  component's inlet edge (or keep a separate seed-boundary edge, decide
  based on whichever approach is chosen for `seed_state` above).
- Any `setattr(component.inlet_spec, field_name, None)`-style clearing logic
  (~line 504) → clear on the edge instead.
- Calls to `apply_solution_to_component(result.inlet_state, result.outlet_state, ...)`
  stay mostly the same shape, just routed through edges inside inspector.

### `heat_circuit_tool/demo.py`
- `pump_result.outlet_state` — this reads from `ComponentResult`, should be
  unaffected, but re-verify after solver changes.

### Tests (`tests/test_constraint_system.py`)
- Existing tests build `Component`/`Circuit` objects directly with
  `inlet_spec`/`outlet_spec` and check `solve_circuit` results. These will
  need to be updated to build circuits via `circuit.connect(...)` and set
  spec values through edges (or through a small test helper that mirrors
  what the inspector does) rather than setting `component.inlet_spec`
  directly.
- Add new tests specifically for edge sharing:
  - Setting a value on an upstream component's outlet edge field is visible
    immediately on the downstream component's inlet edge (same object).
  - Save/load round-trip preserves edges and their field-tracking sets.
  - Loading a legacy (pre-refactor) save file migrates correctly into edges.
  - Overconstraint detection still fires correctly for a non-General
    component with a fully-defined inlet edge and fully-defined outlet edge.

## Out of scope for this pass
- Mixers/splitters with multiple inlet or outlet connections. Today
  `upstream_ids`/`downstream_ids` are lists but only `[0]` is used for
  traversal (`ordered_path`), and mixing logic (`_mix_states`) already
  handles combining multiple upstream states into one value. For this
  refactor, keep `inlet_edge_id`/`outlet_edge_id` as single references for
  most component kinds, but `Circuit` should still support a component having
  multiple *incoming* edges by tracking them separately from the "primary"
  inlet edge used for spec entry (mirroring today's `upstream_ids` list vs.
  `upstream_id` singular property). Do not attempt to unify mixer semantics
  in this pass — just don't regress current mixer behavior.
- Moving `seed_state`/`seed_description` onto an edge (kept as a `Circuit`
  field for now, see above).
- Changing `unit_preferences` to live per-edge instead of per-component.

## Suggested implementation order
1. Add `Edge` to `model.py` alongside the existing fields (don't remove old
   fields yet). Add `Circuit.edges` and edge-management in
   `connect`/`disconnect`/`remove_component`, but don't wire anything else up
   — this step is additive and should not change any behavior.
2. Update `solver.py` to read/write through edges, with the old
   `component.inlet_spec`/etc. fields still present but unused by the
   solver. Run the existing test suite; fix breakage.
3. Update `persistence.py` to serialize edges alongside the legacy fields
   (both, temporarily) and add the version-2 migration path for old files.
   Add migration tests.
4. Update `inspector.py`, `main_window.py`, `canvas.py`, `cycle_diagram.py`,
   `presets.py`, `solve_logging.py`, `demo.py` to use edges.
5. Remove the now-dead `Component.inlet_spec`/`outlet_spec`/`inlet_state`/
   `outlet_state`/`user_input_fields`/`solved_fields`/`conflicting_fields`
   fields and the legacy persistence keys (bump save format to drop legacy
   fields entirely once migration is proven, or keep writing them
   permanently for one more major version as a safety net — pick based on
   how confident the migration tests make you).
6. Manually smoke-test the running app end to end: build a small cycle
   (pump → boiler → turbine → condenser → pump), confirm solving, saving,
   reloading, and inspector highlighting all behave as expected, and that
   the specific bugs fixed via the old propagation workaround
   (`_apply_propagated_inlet_fields`, `_linked_user_fields`) remain fixed
   under the new model with no leftover workaround code.

## Acceptance criteria
- All existing tests in `tests/test_constraint_system.py` pass (updated to
  the new construction API where needed).
- New tests covering edge sharing, save/load round-trip, and legacy-file
  migration pass.
- `inspector.py` no longer contains `_propagated_fields`,
  `_linked_user_fields`, `_apply_propagated_inlet_fields`, or
  `_propagate_from_neighbor` — this logic is deleted, not just unused.
- Manually verified: editing a value on one side of a connection is
  reflected on the other side instantly, with correct user/solved/neutral
  coloring, and no scenario requires the user to re-enter a value already
  known from a neighboring component.
