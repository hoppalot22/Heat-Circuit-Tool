# Phase 1 - Separate Engineering Model From UI State

## Goal

`Component` should represent engineering data only.

UI-specific information should live elsewhere.

---

## Task 1.1 - Create ComponentLayout

### Instructions for Copilot

Create a new dataclass:

```
@dataclass(slots=True)class ComponentLayout:    component_id: str    x: float    y: float    width: float    height: float
```

Move the following fields out of `Component`:

```
xywidthheight
```

Store them in a new layout collection owned by the circuit or project.

---

### Acceptance Criteria

- Component no longer contains coordinates.
- Canvas renders using ComponentLayout.
- Save/load still works.
- Existing projects load correctly.

---

## Task 1.2 - Create ComponentUIState

### Instructions for Copilot

Create:

```
@dataclass(slots=True)class ComponentUIState:    component_id: str    is_dirty: bool = False    report: str = ""
```

Move UI-only fields from Component.

Examples:

```
is_dirtyreport
```

Any future selection state should also belong here.

---

### Acceptance Criteria

- Engineering model contains no UI state.
- Canvas still updates correctly.
- Reports still display correctly.

---

# Phase 2 - Introduce a Project Model

## Goal

Stop using the main window as the application's data owner.

---

## Task 2.1 - Create Project

### Instructions for Copilot

Create:

```
@dataclass(slots=True)class Project:    circuit: Circuit    layouts: dict[str, ComponentLayout]    ui_state: dict[str, ComponentUIState]
```

The project becomes the root object.

---

### Acceptance Criteria

Replace:

```
self.circuit
```

with:

```
self.project.circuit
```

where appropriate.

---

# Phase 3 - Isolate Solver

This is the highest-value improvement.

---

## Task 3.1 - Create Solution Models

### Instructions for Copilot

Create:

```
@dataclass(slots=True)class ComponentSolution:    component_id: str    inlet_state: ThermoState | None    outlet_state: ThermoState | None    messages: list[str]
```

and

```
@dataclass(slots=True)class CircuitSolution:    components: dict[str, ComponentSolution]    success: bool    diagnostics: list[str]
```

---

### Acceptance Criteria

Solver outputs solution objects.

Do not mutate components directly.

---

## Task 3.2 - Refactor Solver API

Replace patterns like:

```
solve(circuit)
```

that mutate the model.

New API:

```
solution = solver.solve(circuit)
```

---

### Acceptance Criteria

The circuit remains unchanged after solve.

All results live inside CircuitSolution.

---

## Task 3.3 - UI Consumes Solution

### Instructions for Copilot

Update UI panels to display:

```
solution.components[id]
```

instead of:

```
component.outlet_state
```

---

### Acceptance Criteria

The application behaves identically from the user's perspective.

---

# Phase 4 - Create Controllers

## Goal

Shrink HeatCircuitApp.

---

## Task 4.1 - Create ProjectController

### Responsibilities

```
New ProjectOpen ProjectSave ProjectSave AsDirty Tracking
```

---

### Instructions for Copilot

Move all project/file logic from:

```
HeatCircuitApp
```

into:

```
ProjectController
```

---

### Acceptance Criteria

Main window no longer performs file IO.

---

## Task 4.2 - Create SolveController

### Responsibilities

```
Run SolveStore Current SolutionPublish Solve Results
```

---

### Instructions for Copilot

Move solve orchestration from main window into:

```
SolveController
```

---

### Acceptance Criteria

Main window does not directly call the solver.

---

# Phase 5 - Extract Connection Routing

## Goal

Canvas should draw.

Routing should route.

---

## Task 5.1 - Create ConnectionRouter

### Instructions for Copilot

Move:

```
_assign_all_connection_ports()_route_connection_points()_route_connection()
```

out of the canvas.

Create:

```
class ConnectionRouter:
```

that produces connection paths.

---

### API

```
router.route(circuit, layouts)
```

returns:

```
list[ConnectionPath]
```

---

### Acceptance Criteria

Canvas no longer contains routing algorithms.

Canvas only renders results.

---

# Phase 6 - Clean Up Specifications

This will help before adding more equipment.

---

## Task 6.1 - Split ThermoSpec

Current ThermoSpec is becoming overloaded.

Create:

```
StateSpec
```

for:

```
pressuretemperatureenthalpyentropyquality
```

and

```
EquipmentSpec
```

for:

```
efficiencypressure_dropheat_dutyloss_coefficientsdiameterlengthroughness
```

---

### Acceptance Criteria

Thermodynamic state definition is separate from equipment settings.

---

# Phase 7 - Add Unit Service

## Goal

Stop scattering unit preferences through the model.

---

## Task 7.1 - Create UnitManager

### Instructions for Copilot

Create:

```
class UnitManager:
```

Responsible for:

```
convert_pressure()convert_temperature()convert_energy()format_pressure()format_temperature()format_state()
```

---

### Acceptance Criteria

No formatting logic inside ThermoState.

No formatting logic inside Component.

---

# Phase 8 - Add Test Coverage

This is the phase I would personally prioritize before any major feature work.

---

## Task 8.1 - Circuit Tests

Create tests for:

```
Adding ComponentsRemoving ComponentsConnecting ComponentsDisconnecting ComponentsBranch Detection
```

---

## Task 8.2 - Solver Tests

Create tests for:

```
Pressure PropagationTemperature PropagationPump CalculationsTurbine CalculationsHeat Exchanger Calculations
```

---

## Task 8.3 - Serialization Tests

Create tests for:

```
SaveLoadRound Trip Persistence
```

Example:

```
project_asave()load()project_bassert project_a == project_b
```

---

# Phase 9 - Future Architecture Target

After these refactors the project should roughly look like:

```
project/│├── model/│   ├── circuit.py│   ├── component.py│   ├── thermo.py│   ├── project.py│├── solver/│   ├── solver.py│   ├── solution.py│├── controllers/│   ├── project_controller.py│   ├── solve_controller.py│├── services/│   ├── steam_backend.py│   ├── unit_manager.py│   ├── connection_router.py│├── ui/│   ├── canvas.py│   ├── inspector.py│   ├── main_window.py│└── tests/
```

This structure would make the application much easier to evolve toward more advanced goals such as:

- constraint-based solving,
- multiple working fluids,
- undo/redo,
- simulation snapshots,
- report generation,
- ECS-style rendering,
- eventually a web frontend if you ever decide to move beyond Tkinter.