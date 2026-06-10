# Heat Circuit Tool

Heat Circuit Tool is a modular desktop app for creating, connecting, and solving thermal process circuits with steam properties.

## Documentation

- Developer docs index: docs/README.md
- Full Python API reference: docs/PYTHON_API_REFERENCE.md

It is designed so you can:
- Build a flowsheet visually using draggable component blocks.
- Connect components with inlet and outlet node links.
- Define thermodynamic targets per component.
- Solve for steam states and key cycle metrics.
- Detect whether the model is well-defined, underconstrained, or overconstrained.

## 1. Setup and launch

### Requirements
- Python 3.10 or newer
- The iapws package

### Install dependencies
- pip install -r requirements.txt

### Start the app
- python run_heat_circuit_tool.py

## 2. UI layout and what each section does

The main window has three adjustable areas separated by draggable split bars.

### Left panel: Library and presets
- Add standard component types quickly (Pump, Boiler, Turbine, Reheater, Condenser, Mixer, Splitter, Valve, Custom).
- Choose a preset and click Add Selected Preset for realistic default values.

### Center panel: Canvas
- This is where you place components and create links.
- Blocks are draggable with left mouse drag.
- You can zoom and pan the view:
	- Mouse wheel: zoom in or out at cursor position.
	- Middle mouse drag: pan the viewport.

### Right panel top: Inspector
- Shows and edits the selected component.
- You can set:
	- Name
	- Component Type
	- Process
	- Inlet and outlet property targets
	- Efficiency
	- Heat duty and pressure drop
	- Notes
- Click Apply to save field changes to that component.
- Each numeric field has its own unit dropdown with only valid units for that parameter.
- Unit selections are stored per component and used when displaying results.

### Right panel bottom: Results
- Shows solve summary and per-component results.
- Includes heat in/out, turbine work, pump work, net work, efficiency, and diagnostics.
- Results follow the component unit selections from the Inspector.
- Values are automatically promoted to practical SI prefixes where helpful.
	- Example: 0.001 MPa is shown as 1 kPa.

### Bottom status bar
- Shows current selection and solve status.

## 3. How to create components

1. Click any Add button in the left panel, or add a preset.
2. A new block appears on the canvas.
3. Drag it to your desired location.
4. Click a block to select it and edit details in the Inspector.

## 4. How to form new connections (important)

Connections are directional: outlet -> inlet.

1. Click the OUTLET node on the source component.
	 - This is the blue port on the right side of the block.
 	 - It will be highlighted with a green ring and source label while waiting for the second click.
2. Click the INLET node on the destination component.
	 - This is the yellow port on the left side of the block.
3. A line with an arrow appears from source to destination.

Notes:
- You can branch from one source to many destinations by repeating outlet -> inlet clicks.
- You can merge many sources to one destination the same way.
- Right click cancels pending connection mode.
- Clicking empty canvas clears selection and pending connection mode.
- The selected source outlet is highlighted while waiting for the second click.

## 5. Quick connection verification test

Use this short test to confirm linking functionality in your session:

1. Launch app.
2. Click Add Boiler.
3. Click Add Turbine.
4. Click blue outlet port on Boiler.
5. Click yellow inlet port on Turbine.
6. Confirm a connecting line appears.

If no line appears:
- Make sure you are clicking the circular ports, not text labels.
- Ensure first click is source outlet (blue), second is destination inlet (yellow).
- Restart the app so the latest canvas code is loaded.

## 6. Editing component thermodynamic targets

For each component, set enough information for the selected process model.

Typical examples:
- Isentropic turbine or pump:
	- Set outlet pressure.
	- Set efficiency.
- Isobaric heater or condenser:
	- Set pressure.
	- Set one of temperature, enthalpy, entropy, or quality.
- Isenthalpic valve:
	- Set outlet pressure.
- General:
	- Provide enough outlet data for a valid steam state calculation.
- Pipe:
	- Set mass flow, length, outer diameter, wall thickness, and roughness.
	- Optional: elevation change and local loss coefficient.
	- Solver reports Reynolds number, friction factor, inlet velocity, outlet velocity, and pressure drop.

## 7. Solving and diagnostics

### Run solve
- Click Solve in the header toolbar or in the Inspector panel.
- After a successful solve:
	- User-entered solver inputs are shaded dull yellow-orange.
	- Solver-filled fields are shaded dull light blue.
	- Any field edit clears highlight state and marks the model as needing solve.

### Read summary output
- Heat in and heat out
- Turbine and pump work
- Net work
- Thermal efficiency
- Back work ratio
- Loop closure error (if loop return is available)
- System constraint status

### Constraint status meanings
- Well-defined: system has enough compatible constraints.
- Underconstrained: missing required targets for at least one component or unresolved upstream states.
- Overconstrained: conflicting targets were detected.

## 8. Using the built-in reheat Rankine demo

1. Click Load Demo.
2. Click Solve.
3. Review component states and cycle metrics in Results.

The demo is configured as a realistic forward-solved reheat Rankine setup with feed pump outlet seed conditions.

## 9. Canvas interaction reference

- Left click block: select.
- Left drag block: move component.
- Mouse wheel: zoom.
- Middle drag: pan.
- Right click: cancel pending connect mode and keep selection behavior.
- Delete key: remove selected component.
- Connection routing attempts to avoid unrelated components and ports where possible.

## 10. Project and snapshot workflow

- Revert Last Solve restores the most recent solved state cache.
- Save Project stores:
	- Active circuit state
	- Saved snapshots
	- Latest solved cache
- Load Project restores the full project state.
- Every solve is appended to a JSONL log file:
	- Unsaved work: unsaved_project.solve_log.jsonl in the workspace root.
	- Saved/loaded projects: <project_name>.solve_log.jsonl beside the project file.
- Underconstrained and overconstrained solves include expanded debug payloads in the log (component specs, graph links, field constraints, conflicts, and solve status breakdown).
- Snapshot controls in the toolbar allow you to:
	- Save named snapshots
	- Select a snapshot from dropdown to restore it
	- Rename snapshots

## 11. Current modeling assumptions

- Steam properties use IAPWS97.
- Merge nodes currently use mixed inlet state approximation at averaged pressure/enthalpy when multiple upstream states are present.
- Advanced branch mass flow split equations are not yet exposed in the UI.

## 12. Troubleshooting

### App starts but solve fails
- Open Results and read component-level status messages.
- Check selected process and required fields in Inspector.

### Connections still do not form
- Confirm outlet-first then inlet-second click order.
- Confirm the ports are clicked directly.
- Restart app to ensure newest code is active.

### Unexpected thermodynamic output
- Verify units in fields:
	- Pressure in MPa
	- Temperature in C
	- Enthalpy in kJ/kg
	- Entropy in kJ/kg-K

## 13. Project structure

- run_heat_circuit_tool.py: launcher
- heat_circuit_tool/model.py: graph and component data model
- heat_circuit_tool/solver.py: cycle solve logic and diagnostics
- heat_circuit_tool/thermo.py: steam property backend wrapper
- heat_circuit_tool/presets.py: equipment presets
- heat_circuit_tool/ui/canvas.py: node editor canvas and interaction logic
- heat_circuit_tool/ui/inspector.py: component editor panel
- heat_circuit_tool/ui/main_window.py: app window and layout wiring
