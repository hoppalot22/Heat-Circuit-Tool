# Post-Refactor Roadmap

## Status
Active. The edge-owned thermodynamic state refactor is complete and documented in
`EDGE_STATE_REFACTOR_PLAN.md`; this roadmap is the worklist for the next release
milestones.

## Purpose

The model is now structurally correct: connection state is owned by the shared
edge, and solver/UI logic is no longer forced to copy values across the two
sides of the same physical link. The remaining work is to make that capability
transparent, trustworthy, and easy to use in real branch-heavy circuits.

## Current baseline

What is already in place:
- Shared edge ownership for connected thermodynamic state and field tracking.
- Solver propagation through branched connections and the public connection API.
- Save/load compatibility with v1-to-v2 migration for legacy project files.
- Core test coverage for the constraint system and edge-driven propagation.

What is not yet complete:
- Branch-specific UI editing for multiple incoming and outgoing edges.
- Explicit flow-balance diagnostics for mixers and splitters.
- Release-quality examples, documentation sync, and workflow polish.

## Phase 1: End-to-end reliability

### Delivery checklist

- [ ] Add a solver-level branch test using the public `Circuit.connect` API and
  real graph traversal rather than direct helper calls.
- [ ] Validate mixer, splitter, and reconnect/disconnect behavior for primary and
  secondary edges.
- [ ] Verify save/load round-trips and edge normalization for newly created and
  migrated circuits.
- [ ] Reject duplicate component IDs and invalid port links with explicit model
  errors.
- [ ] Confirm branch conflicts are surfaced consistently in component result
  states and inspector diagnostics.

### Acceptance criteria
- A branched circuit can be created and solved without manual state-copy hacks.
- Disconnected and removed branches leave no stale edge data behind.
- Invalid or duplicate graph edits fail clearly and early.

## Phase 2: First-class multi-port UI

### Delivery checklist

- [ ] Show every incoming and outgoing edge for multi-port components in the
  inspector.
- [ ] Display connected component names, edge state, mass flow, and constraint
  status per branch.
- [ ] Allow branch selection without forcing a component switch.
- [ ] Add explicit branch mass-flow inputs with validation and conversion.
- [ ] Differentiate missing branch flow data from thermodynamic conflicts in the
  visual styling.
- [ ] Prevent invalid self-links and duplicate links in connection mode.
- [ ] Provide a clear branch removal action and make port ownership clearer in
  the canvas.

### Acceptance criteria
- A mixer or splitter can be configured and inspected without hidden state
  assumptions.
- A user can tell which branch is being edited and how that branch differs from
  the component-level summary.
- Connection workflow is safe and obvious even for non-trivial branching.

## Phase 3: Flow-balance and thermodynamic diagnostics

### Delivery checklist

- [ ] Report missing or invalid branch mass-flow data explicitly for mixers and
  splitters.
- [ ] Distinguish incomplete flow information from inconsistent flow balances.
- [ ] Validate mixer outlet flow against total inlet flow when outlet flow is
  specified.
- [ ] Validate splitter outlet flow against inlet flow.
- [ ] Keep conservative mixer pressure behavior documented and enforced.
- [ ] Define and test two-phase quality handling for mixer combinations and mixed
  saturation states.
- [ ] Add optional non-adiabatic mixer behavior only if the model needs it.

### Acceptance criteria
- Flow-balance problems are reported as a first-class solver diagnostic rather
  than an accidental side effect of state propagation.
- A user sees the difference between underconstrained, overconstrained, and
  physically inconsistent branch equations.
- Mixer assumptions are consistently documented wherever results are surfaced.

## Phase 4: Focused user workflow

### Delivery checklist

- [ ] Make the normal path obvious: build, connect, constrain, solve, inspect.
- [ ] Reduce always-visible diagnostic noise while retaining detailed reports on
  demand.
- [ ] Add a compact circuit summary for unresolved components, active conflicts,
  and the next most useful input.
- [ ] Improve result navigation so selecting a result focuses the relevant
  component or edge.
- [ ] Visually separate user-entered, solver-filled, and conflicting values.

### Acceptance criteria
- A new user can understand the intended workflow without reading the solver
  internals.
- Circuit health is visible at a glance, but detailed diagnostics remain easily
  accessible.

## Phase 5: Documentation and release readiness

### Delivery checklist

- [ ] Keep `README.md`, the Python API reference, and this roadmap synchronized
  with current solver behavior.
- [ ] Add example circuits for a straight chain, splitter, mixer, pipe, and a
  closed Rankine loop.
- [ ] Define a release checklist covering installation, launch, solve, save,
  reload, and recovery from invalid constraints.
- [ ] Add automated checks for save-format compatibility and representative
  example solves.
- [ ] Publish the simplified mixer assumptions beside any mixer-specific UI or
  result output.

### Acceptance criteria
- A fresh developer or tester can follow the docs and reproduce a clean solve
  without guessing about branch assumptions or migration behavior.
- Release readiness is measurable and repeatable.

## Recommended execution order

1. Stabilize end-to-end branched-circuit behavior and API validation.
2. Build the multi-port inspector and branch-flow editing workflow.
3. Add solver diagnostics for flow-balance problems.
4. Refine mixer pressure and phase behavior where the model still needs tuning.
5. Complete workflow polish and release documentation.

## Notes for the next milestone

The next meaningful milestone is not a second refactor; it is a branch-capable,
user-visible workflow that proves the shared-edge model behaves correctly in the
UI and under realistic mixed-flow constraints. That milestone should ship with
explicit multi-port inspection and branch diagnostics before broader
thermodynamic refinement work begins.
