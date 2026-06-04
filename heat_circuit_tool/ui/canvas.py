from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from ..model import Circuit, Component, PortRole


class NodeCanvas(tk.Canvas):
    def __init__(self, master: tk.Misc, circuit: Circuit, on_select: Callable[[Optional[str]], None], **kwargs):
        super().__init__(master, highlightthickness=0, background="#11161f", **kwargs)
        self.circuit = circuit
        self.on_select = on_select
        self.selected_component_id: Optional[str] = None
        self.pending_connection_source_id: Optional[str] = None
        self._drag_component_id: Optional[str] = None
        self._drag_offset_world = (0.0, 0.0)
        self._component_bounds_world: dict[str, tuple[float, float, float, float]] = {}

        self.zoom = 1.0
        self.pan_x = 40.0
        self.pan_y = 40.0
        self._is_panning = False
        self._pan_anchor = (0.0, 0.0)

        self.bind("<ButtonPress-1>", self._on_left_press)
        self.bind("<B1-Motion>", self._on_left_drag)
        self.bind("<ButtonRelease-1>", self._on_left_release)
        self.bind("<Double-Button-1>", self._on_double_click)
        self.bind("<Button-3>", self._on_right_click)
        self.bind("<ButtonPress-2>", self._on_middle_press)
        self.bind("<B2-Motion>", self._on_middle_drag)
        self.bind("<ButtonRelease-2>", self._on_middle_release)
        self.bind("<MouseWheel>", self._on_mouse_wheel)

    def set_circuit(self, circuit: Circuit) -> None:
        self.circuit = circuit
        self.selected_component_id = None
        self.pending_connection_source_id = None
        self.redraw()

    def select_component(self, component_id: Optional[str]) -> None:
        self.selected_component_id = component_id
        self.redraw()
        self.on_select(component_id)

    def redraw(self) -> None:
        self.delete("all")
        self._build_component_bounds()
        self._draw_grid()
        self._draw_connections()
        self._draw_components()

    def _build_component_bounds(self) -> None:
        self._component_bounds_world = {}
        for component in self.circuit.components.values():
            self._component_bounds_world[component.component_id] = (
                component.x,
                component.y,
                component.x + component.width,
                component.y + component.height,
            )

    def _world_to_view(self, x: float, y: float) -> tuple[float, float]:
        return x * self.zoom + self.pan_x, y * self.zoom + self.pan_y

    def _view_to_world(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.pan_x) / self.zoom, (y - self.pan_y) / self.zoom

    def _draw_grid(self) -> None:
        width = max(self.winfo_width(), 800)
        height = max(self.winfo_height(), 600)
        spacing_world = 40.0

        left_world, top_world = self._view_to_world(0, 0)
        right_world, bottom_world = self._view_to_world(width, height)

        x = int(left_world // spacing_world) * int(spacing_world)
        while x <= right_world + spacing_world:
            x_view, _ = self._world_to_view(float(x), 0.0)
            self.create_line(x_view, 0, x_view, height, fill="#18202b", width=1)
            x += int(spacing_world)

        y = int(top_world // spacing_world) * int(spacing_world)
        while y <= bottom_world + spacing_world:
            _, y_view = self._world_to_view(0.0, float(y))
            self.create_line(0, y_view, width, y_view, fill="#18202b", width=1)
            y += int(spacing_world)

    def _draw_connections(self) -> None:
        for component in self.circuit.components.values():
            for downstream_id in component.downstream_ids:
                downstream = self.circuit.components.get(downstream_id)
                if downstream is None:
                    continue
                x1, y1 = component.outlet_port()
                x2, y2 = downstream.inlet_port()
                points = self._route_connection_points(component.component_id, downstream.component_id, x1, y1, x2, y2)
                view_points: list[float] = []
                for px, py in points:
                    vx, vy = self._world_to_view(px, py)
                    view_points.extend([vx, vy])
                self.create_line(
                    *view_points,
                    smooth=False,
                    fill="#67d4ff",
                    width=max(1, int(3 * self.zoom)),
                    arrow=tk.LAST,
                    arrowshape=(10, 12, 4),
                    tags=("connection", f"connection:{component.component_id}->{downstream.component_id}"),
                )

    def _route_connection_points(
        self,
        source_id: str,
        target_id: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> list[tuple[float, float]]:
        dx = x2 - x1
        mid_x = x1 + dx / 2.0
        top_y = min(y1, y2) - 70.0
        bottom_y = max(y1, y2) + 70.0
        source_step = x1 + 35.0
        target_step = x2 - 35.0

        candidates = [
            [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)],
            [(x1, y1), (source_step, y1), (source_step, top_y), (target_step, top_y), (target_step, y2), (x2, y2)],
            [(x1, y1), (source_step, y1), (source_step, bottom_y), (target_step, bottom_y), (target_step, y2), (x2, y2)],
        ]

        if x2 < x1:
            left_lane = min(x1, x2) - 90.0
            candidates.append([(x1, y1), (source_step, y1), (source_step, top_y), (left_lane, top_y), (left_lane, y2), (x2, y2)])
            candidates.append([(x1, y1), (source_step, y1), (source_step, bottom_y), (left_lane, bottom_y), (left_lane, y2), (x2, y2)])

        best = min(candidates, key=lambda points: self._route_penalty(source_id, target_id, points))
        return best

    def _route_penalty(self, source_id: str, target_id: str, points: list[tuple[float, float]]) -> float:
        penalty = 0.0
        length = 0.0
        for index in range(len(points) - 1):
            x1, y1 = points[index]
            x2, y2 = points[index + 1]
            length += abs(x2 - x1) + abs(y2 - y1)
            for component_id, rect in self._component_bounds_world.items():
                if component_id in {source_id, target_id}:
                    continue
                if self._segment_intersects_rect((x1, y1), (x2, y2), rect, pad=10.0):
                    penalty += 1000.0
        return penalty + length * 0.001

    def _segment_intersects_rect(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        rect: tuple[float, float, float, float],
        pad: float = 0.0,
    ) -> bool:
        x1, y1 = p1
        x2, y2 = p2
        rx1, ry1, rx2, ry2 = rect
        rx1 -= pad
        ry1 -= pad
        rx2 += pad
        ry2 += pad
        if abs(y1 - y2) < 1e-9:
            y = y1
            xmin, xmax = (x1, x2) if x1 <= x2 else (x2, x1)
            return ry1 <= y <= ry2 and xmax >= rx1 and xmin <= rx2
        if abs(x1 - x2) < 1e-9:
            x = x1
            ymin, ymax = (y1, y2) if y1 <= y2 else (y2, y1)
            return rx1 <= x <= rx2 and ymax >= ry1 and ymin <= ry2
        return False

    def _draw_components(self) -> None:
        for component in self.circuit.components.values():
            self._draw_component(component)

    def _draw_component(self, component: Component) -> None:
        x1w = component.x
        y1w = component.y
        x2w = component.x + component.width
        y2w = component.y + component.height

        x1, y1 = self._world_to_view(x1w, y1w)
        x2, y2 = self._world_to_view(x2w, y2w)
        fill = "#28354a"
        outline = "#67d4ff" if component.component_id == self.selected_component_id else "#7d8797"
        border_width = max(1, int(2 * self.zoom))

        self.create_rectangle(
            x1,
            y1,
            x2,
            y2,
            fill=fill,
            outline=outline,
            width=border_width,
            tags=("component", f"component:{component.component_id}"),
        )

        self.create_text(
            x1 + 12,
            y1 + 14,
            anchor="w",
            text=component.name,
            fill="#f6f7fb",
            font=("Segoe UI", 12, "bold"),
            tags=("component_text", f"component:{component.component_id}"),
        )
        self.create_text(
            x1 + 12,
            y1 + 34,
            anchor="w",
            text=component.kind.value,
            fill="#b7c4d8",
            font=("Segoe UI", 10),
            tags=("component_text", f"component:{component.component_id}"),
        )
        self.create_text(
            x1 + 12,
            y1 + 52,
            anchor="w",
            text=component.process_kind.value,
            fill="#9fd8ff",
            font=("Segoe UI", 9, "italic"),
            tags=("component_text", f"component:{component.component_id}"),
        )
        if component.outlet_state is not None:
            self.create_text(
                x1 + 12,
                y1 + 72,
                anchor="w",
                text=f"P={component.outlet_state.pressure_mpa:.3f} MPa  h={component.outlet_state.enthalpy_kj_kg:.1f}",
                fill="#d8f1ff",
                font=("Segoe UI", 8),
                tags=("component_text", f"component:{component.component_id}"),
            )
        if component.report:
            self.create_text(
                (x1 + x2) / 2.0,
                y2 + 10,
                anchor="n",
                text=component.report[:58],
                fill="#d9dfef",
                font=("Segoe UI", 8),
                tags=("component_text", f"component:{component.component_id}"),
            )

        inlet_xw, inlet_yw = component.inlet_port()
        outlet_xw, outlet_yw = component.outlet_port()
        inlet_x, inlet_y = self._world_to_view(inlet_xw, inlet_yw)
        outlet_x, outlet_y = self._world_to_view(outlet_xw, outlet_yw)
        r = max(5, int(7 * self.zoom))
        self.create_oval(
            inlet_x - r,
            inlet_y - r,
            inlet_x + r,
            inlet_y + r,
            fill="#ffcc66",
            outline="",
            tags=("port", f"port:{component.component_id}:{PortRole.INLET.value}"),
        )
        self.create_oval(
            outlet_x - r,
            outlet_y - r,
            outlet_x + r,
            outlet_y + r,
            fill="#67d4ff",
            outline="",
            tags=("port", f"port:{component.component_id}:{PortRole.OUTLET.value}"),
        )
        if self.pending_connection_source_id == component.component_id:
            highlight_r = r + max(3, int(4 * self.zoom))
            self.create_oval(
                outlet_x - highlight_r,
                outlet_y - highlight_r,
                outlet_x + highlight_r,
                outlet_y + highlight_r,
                outline="#18f3a5",
                width=max(2, int(2 * self.zoom)),
            )
            self.create_text(
                outlet_x + 12,
                outlet_y - 14,
                anchor="w",
                text="source",
                fill="#18f3a5",
                font=("Segoe UI", 8, "bold"),
            )

    def _component_at_world(self, event_x: float, event_y: float) -> Optional[str]:
        world_x, world_y = self._view_to_world(event_x, event_y)
        for component_id, bounds in self._component_bounds_world.items():
            x1, y1, x2, y2 = bounds
            if x1 <= world_x <= x2 and y1 <= world_y <= y2:
                return component_id
        return None

    def _port_at(self, item_id: int) -> tuple[Optional[str], Optional[str]]:
        tags = self.gettags(item_id)
        component_id: Optional[str] = None
        port_role: Optional[str] = None
        for tag in tags:
            if tag.startswith("port:"):
                _, component_id, port_role = tag.split(":")
                return component_id, port_role
        return component_id, port_role

    def _on_left_press(self, event: tk.Event) -> None:
        self.focus_set()
        current = self.find_withtag("current")
        if current:
            component_id, port_role = self._port_at(current[0])
            if component_id and port_role:
                if port_role.lower() == PortRole.OUTLET.value.lower():
                    self.pending_connection_source_id = component_id
                    self.select_component(component_id)
                    return
                if port_role.lower() == PortRole.INLET.value.lower() and self.pending_connection_source_id:
                    self.circuit.connect(self.pending_connection_source_id, component_id)
                    self.pending_connection_source_id = None
                    self.redraw()
                    self.select_component(component_id)
                    return

        component_id = self._component_at_world(event.x, event.y)
        if component_id is None:
            self.select_component(None)
            self.pending_connection_source_id = None
            return
        self.select_component(component_id)
        self._drag_component_id = component_id
        component = self.circuit.components[component_id]
        world_x, world_y = self._view_to_world(event.x, event.y)
        self._drag_offset_world = (world_x - component.x, world_y - component.y)

    def _on_left_drag(self, event: tk.Event) -> None:
        if self._drag_component_id is None:
            return
        component = self.circuit.components.get(self._drag_component_id)
        if component is None:
            return
        offset_x, offset_y = self._drag_offset_world
        world_x, world_y = self._view_to_world(event.x, event.y)
        component.x = world_x - offset_x
        component.y = world_y - offset_y
        self.redraw()

    def _on_left_release(self, event: tk.Event) -> None:
        self._drag_component_id = None

    def _on_double_click(self, event: tk.Event) -> None:
        component_id = self._component_at_world(event.x, event.y)
        if component_id:
            self.select_component(component_id)

    def _on_right_click(self, event: tk.Event) -> None:
        self.pending_connection_source_id = None
        component_id = self._component_at_world(event.x, event.y)
        if component_id:
            self.select_component(component_id)

    def _on_middle_press(self, event: tk.Event) -> None:
        self._is_panning = True
        self._pan_anchor = (event.x, event.y)

    def _on_middle_drag(self, event: tk.Event) -> None:
        if not self._is_panning:
            return
        previous_x, previous_y = self._pan_anchor
        self.pan_x += event.x - previous_x
        self.pan_y += event.y - previous_y
        self._pan_anchor = (event.x, event.y)
        self.redraw()

    def _on_middle_release(self, event: tk.Event) -> None:
        self._is_panning = False

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        factor = 1.1 if event.delta > 0 else 0.9
        new_zoom = min(3.0, max(0.4, self.zoom * factor))
        if abs(new_zoom - self.zoom) < 1e-9:
            return
        world_x, world_y = self._view_to_world(event.x, event.y)
        self.zoom = new_zoom
        self.pan_x = event.x - world_x * self.zoom
        self.pan_y = event.y - world_y * self.zoom
        self.redraw()
