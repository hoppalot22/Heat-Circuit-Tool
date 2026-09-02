# Developer Documentation

This documentation set is designed for fast onboarding and day-2 maintenance work.

## Contents

- API reference: PYTHON_API_REFERENCE.md
- Project overview and usage: ../README.md
- Post-refactor roadmap: POST_REFACTOR_ROADMAP.md

## Current focus

The architecture work behind the edge-owned thermodynamic state refactor is
complete. The active roadmap work is now centered on branch-capable UI flows,
flow-balance diagnostics, and release-readiness documentation.

## Recommended Reading Order

1. Read README.md for workflow, runtime setup, and UI behavior.
2. Read PYTHON_API_REFERENCE.md module-by-module starting with model.py and solver.py.
3. Move to ui/main_window.py and ui/inspector.py for user interaction flow.
4. Use ui/canvas.py and ui/path_finder.py for rendering/routing changes.

## Documentation Conventions

- Purpose sections describe module/class responsibility and intended extension points.
- Constructor sections capture initialization shape and dependency wiring expectations.
- Method/function bullets provide implementation-level entry guidance.
