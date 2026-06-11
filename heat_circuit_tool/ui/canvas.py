from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

from ..model import Circuit, Component, PortRole
from ..model_layout import ComponentLayout, ComponentUIState
from ._geometry import segment_intersects_rect
from .path_finder import OrthogonalPathFinder, orthogonal_intersection_point


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
        self._text_obstacles_world: list[tuple[float, float, float, float]] = []
        self._routed_segments_world: list[tuple[tuple[float, float], tuple[float, float], str]] = []
        self._used_port_points: dict[str, dict[str, list[tuple[float, float]]]] = {}
        self._port_point_lookup: dict[tuple[str, str, str], tuple[float, float]] = {}
        self._drag_redraw_after_id: str | None = None

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

    # ── Layout / UI state helpers ─────────────────────────────────────

    def _layout(self, component: Component) -> ComponentLayout:
        """Return the ComponentLayout for *component* from the circuit."""
        return self.circuit.layout(component.component_id)

    def _ui(self, component: Component) -> ComponentUIState:
        """Return the ComponentUIState for *component* from the circuit."""
        return self.circuit.ui_state(component.component_id)

    # ── Public API ────────────────────────────────────────────────────

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

    # ── Bounds and obstacle building ──────────────────────────────────

    def _build_component_bounds(self) -> None:
        self._component_bounds_world = {}
        self._text_obstacles_world = []
        for component in self.circuit.components.values():
            lay = self._layout(component)
            self._component_bounds_world[component.component_id] = (
                lay.x,
                lay.y,
                lay.x + lay.width,
                lay.y + lay.height,
            )
            ui = self._ui(component)
            if ui.report:
                cx = lay.x + lay.width / 2.0
                text_top = lay.y + lay.height + 16.0
                text_bottom = text_top + 18.0
                self._text_obstacles_world.append((cx - 190.0, text_top, cx + 190.0, text_bottom))

    # ── Coordinate transform ──────────────────────────────────────────

    def _world_to_view(self, x: float, y: float) -> tuple[float, float]:
        return x * self.zoom + self.pan_x, y * self.zoom + self.pan_y

    def _view_to_world(self, x: float, y: float) -> tuple[float, float]:
        return (x - self.pan_x) / self.zoom, (y - self.pan_y) / self.zoom

    # ── Grid ──────────────────────────────────────────────────────────

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

    # ── Connection routing ────────────────────────────────────────────

    def _draw_connections(self) -> None:
        self._routed_segments_world = []
        self._used_port_points = {}
        self._port_point_lookup = {}
        self._assign_all_connection_ports()

        for component in self.circuit.components.values():
            for downstream_id in component.downstream_ids:
                downstream = self.circuit.components.get(downstream_id)
                if downstream is None:
                    continue
                connection_key = f"{component.component_id}->{downstream.component_id}"
                source = self._port_point_lookup.get((component.component_id, "outlet", downstream.component_id))
                target = self._port_point_lookup.get((downstream.component_id, "inlet", component.component_id))
                if source is None or target is None:
                    continue
                x1, y1 = source
                x2, y2 = target
                points = self._route_connection_points(
                    component.component_id,
                    downstream.component_id,
                    x1, y1, x2, y2,
                    self._routed_segments_world,
                )
                if len(points) < 2:
                    continue
                view_points: list[float] = []
                for px, py in points:
                    vx, vy = self._world_to_view(px, py)
                    view_points.extend([vx, vy])
                line_width = max(1, int(3 * self.zoom))
                self.create_line(
                    *view_points,
                    smooth=False,
                    fill="#67d4ff",
                    width=line_width,
                    arrow=tk.LAST,
                    arrowshape=(10, 12, 4),
                    tags=("connection", f"connection:{connection_key}"),
                )

                bridge_points = self._bridge_points_for_route(points, self._routed_segments_world)
                for bx, by, orientation in bridge_points:
                    self._draw_bridge_arc(bx, by, orientation, "#67d4ff", line_width)

                for i in range(len(points) - 1):
                    self._routed_segments_world.append((points[i], points[i + 1], connection_key))

    def _port_direction_for_point(self, component_id: str, point: tuple[float, float], role: str) -> tuple[float, float]:
        x1, y1, x2, y2 = self._component_bounds_world[component_id]
        px, py = point
        eps = 1e-6
        if abs(px - x1) <= eps:
            return (-1.0, 0.0)
        if abs(px - x2) <= eps:
            return (1.0, 0.0)
        if abs(py - y1) <= eps:
            return (0.0, -1.0)
        if abs(py - y2) <= eps:
            return (0.0, 1.0)
        return (1.0, 0.0) if role == "outlet" else (-1.0, 0.0)

    def _assign_all_connection_ports(self) -> None:
        for component in self.circuit.components.values():
            outgoing = [peer_id for peer_id in component.downstream_ids if peer_id in self.circuit.components]
            incoming = [peer_id for peer_id in component.upstream_ids if peer_id in self.circuit.components]
            self._assign_component_role_ports(component.component_id, "outlet", outgoing)
            self._assign_component_role_ports(component.component_id, "inlet", incoming)

        for component in self.circuit.components.values():
            self._separate_component_port_overlaps(component.component_id)

        self._used_port_points = {}
        for (component_id, role, _), point in self._port_point_lookup.items():
            self._register_port_point(component_id, role, point)

    def _separate_component_port_overlaps(self, component_id: str) -> None:
        component_entries = [
            (key, point)
            for key, point in self._port_point_lookup.items()
            if key[0] == component_id
        ]
        if len(component_entries) <= 1:
            return

        grouped: dict[tuple[int, int], list[tuple[str, str, str]]] = {}
        for key, point in component_entries:
            point_key = (int(round(point[0] * 1000.0)), int(round(point[1] * 1000.0)))
            grouped.setdefault(point_key, []).append(key)

        for keys in grouped.values():
            if len(keys) <= 1:
                continue
            original_point = self._port_point_lookup[keys[0]]
            side = self._point_side_for_port(component_id, original_point)
            if side is None:
                continue
            ordered = sorted(
                keys,
                key=lambda item: (
                    self._peer_projection_for_port_key(item, side),
                    0 if item[1] == "inlet" else 1,
                    item[2],
                ),
            )
            spacing = 16.0
            center = (len(ordered) - 1) / 2.0
            for idx, key in enumerate(ordered):
                offset = (idx - center) * spacing
                self._port_point_lookup[key] = self._offset_point_along_side(component_id, side, original_point, offset)

    def _peer_projection_for_port_key(self, port_key: tuple[str, str, str], side: str) -> float:
        peer_id = port_key[2]
        peer = self.circuit.components.get(peer_id)
        if peer is None:
            return 0.0
        px, py = self._layout(peer).center()
        return py if side in {"left", "right"} else px

    def _point_side_for_port(self, component_id: str, point: tuple[float, float]) -> str | None:
        x1, y1, x2, y2 = self._component_bounds_world[component_id]
        px, py = point
        eps = 1e-6
        if abs(px - x1) <= eps:
            return "left"
        if abs(px - x2) <= eps:
            return "right"
        if abs(py - y1) <= eps:
            return "top"
        if abs(py - y2) <= eps:
            return "bottom"
        return None

    def _offset_point_along_side(
        self,
        component_id: str,
        side: str,
        point: tuple[float, float],
        offset: float,
    ) -> tuple[float, float]:
        x1, y1, x2, y2 = self._component_bounds_world[component_id]
        corner_margin = 14.0
        px, py = point
        if side in {"left", "right"}:
            min_y = y1 + corner_margin
            max_y = y2 - corner_margin
            y = max(min_y, min(max_y, py + offset))
            x = x1 if side == "left" else x2
            return (x, y)
        min_x = x1 + corner_margin
        max_x = x2 - corner_margin
        x = max(min_x, min(max_x, px + offset))
        y = y1 if side == "top" else y2
        return (x, y)

    def _assign_component_role_ports(self, component_id: str, role: str, peer_ids: list[str]) -> None:
        if not peer_ids:
            return
        component = self.circuit.components[component_id]
        sides = ["left", "right", "top", "bottom"]
        side_buckets: dict[str, list[str]] = {side: [] for side in sides}

        for peer_id in sorted(peer_ids):
            preferred = self._preferred_sides(component_id, peer_id)
            chosen = preferred[0]
            for side in preferred:
                if len(side_buckets[side]) < self._side_capacity(component, side):
                    chosen = side
                    break
            side_buckets[chosen].append(peer_id)

        for side in sides:
            peers = side_buckets[side]
            if not peers:
                continue
            ordered = self._ordered_peers_for_side(component_id, side, peers)
            points = self._evenly_spaced_points_on_side(component, side, len(ordered))
            for peer_id, point in zip(ordered, points):
                self._port_point_lookup[(component_id, role, peer_id)] = point
                self._register_port_point(component_id, role, point)

    def _preferred_sides(self, component_id: str, peer_id: str) -> list[str]:
        component = self.circuit.components[component_id]
        peer = self.circuit.components[peer_id]
        cx, cy = self._layout(component).center()
        px, py = self._layout(peer).center()
        dx = px - cx
        dy = py - cy

        horizontal_first = abs(dx) >= abs(dy)
        primary_h = "right" if dx >= 0 else "left"
        secondary_h = "left" if primary_h == "right" else "right"
        primary_v = "bottom" if dy >= 0 else "top"
        secondary_v = "top" if primary_v == "bottom" else "bottom"
        if horizontal_first:
            return [primary_h, primary_v, secondary_v, secondary_h]
        return [primary_v, primary_h, secondary_h, secondary_v]

    def _side_capacity(self, component: Component, side: str) -> int:
        corner_margin = 14.0
        min_gap = 18.0
        lay = self._layout(component)
        side_len = lay.height if side in {"left", "right"} else lay.width
        usable = max(0.0, side_len - 2.0 * corner_margin)
        return max(1, int(usable // min_gap) + 1)

    def _ordered_peers_for_side(self, component_id: str, side: str, peers: list[str]) -> list[str]:
        component = self.circuit.components[component_id]
        points = self._evenly_spaced_points_on_side(component, side, len(peers))

        def projection(peer_id: str) -> float:
            center = self._layout(self.circuit.components[peer_id]).center()
            return center[1] if side in {"left", "right"} else center[0]

        forward = sorted(peers, key=projection)
        reverse = list(reversed(forward))

        def score(order: list[str]) -> float:
            total = 0.0
            for peer_id, point in zip(order, points):
                px, py = self._layout(self.circuit.components[peer_id]).center()
                total += abs(px - point[0]) + abs(py - point[1])
            return total

        return forward if score(forward) <= score(reverse) else reverse

    def _evenly_spaced_points_on_side(self, component: Component, side: str, count: int) -> list[tuple[float, float]]:
        corner_margin = 14.0
        lay = self._layout(component)
        if count <= 1:
            if side == "left":
                return [(lay.x, lay.y + lay.height / 2.0)]
            if side == "right":
                return [(lay.x + lay.width, lay.y + lay.height / 2.0)]
            if side == "top":
                return [(lay.x + lay.width / 2.0, lay.y)]
            return [(lay.x + lay.width / 2.0, lay.y + lay.height)]

        if side in {"left", "right"}:
            start = lay.y + corner_margin
            end = lay.y + lay.height - corner_margin
            step = (end - start) / (count - 1)
            x = lay.x if side == "left" else lay.x + lay.width
            return [(x, start + idx * step) for idx in range(count)]

        start = lay.x + corner_margin
        end = lay.x + lay.width - corner_margin
        step = (end - start) / (count - 1)
        y = lay.y if side == "top" else lay.y + lay.height
        return [(start + idx * step, y) for idx in range(count)]

    def _register_port_point(self, component_id: str, role: str, point: tuple[float, float]) -> None:
        role_points = self._used_port_points.setdefault(component_id, {"inlet": [], "outlet": []})
        points = role_points[role]
        for px, py in points:
            if abs(px - point[0]) < 1e-6 and abs(py - point[1]) < 1e-6:
                return
        points.append(point)

    def _port_spacing_penalty(self, component_id: str, role: str, point: tuple[float, float]) -> float:
        role_points = self._used_port_points.get(component_id, {}).get(role, [])
        min_gap = 18.0
        penalty = 0.0
        for other in role_points:
            dist = self._axis_distance(point, other)
            if dist < min_gap:
                penalty += 4000.0 + (min_gap - dist) * 200.0
        return penalty

    def _connection_port_candidates(
        self,
        component_id: str,
        peer_id: str,
        role: str,
    ) -> list[tuple[float, float]]:
        component = self.circuit.components[component_id]
        corner_margin = 14.0
        min_gap = 18.0
        lay = self._layout(component)

        if role == "outlet":
            peers = sorted(component.downstream_ids)
            x = lay.x + lay.width
        else:
            peers = sorted(component.upstream_ids)
            x = lay.x

        if peer_id not in peers:
            peers = peers + [peer_id]
            peers.sort()

        count = max(1, len(peers))
        idx = peers.index(peer_id)
        y_top = lay.y + corner_margin
        y_bottom = lay.y + lay.height - corner_margin
        center_y = lay.y + lay.height / 2.0

        if count == 1:
            preferred = center_y
        else:
            available = max(1.0, y_bottom - y_top)
            spacing = max(min_gap, available / (count - 1))
            group_span = spacing * (count - 1)
            first = center_y - group_span / 2.0
            min_first = y_top
            max_first = y_bottom - group_span
            if max_first < min_first:
                max_first = min_first
            first = max(min_first, min(max_first, first))
            preferred = first + idx * spacing

        offsets = [0.0, -min_gap, min_gap, -2.0 * min_gap, 2.0 * min_gap]
        ys: list[float] = []
        for offset in offsets:
            y = max(y_top, min(y_bottom, preferred + offset))
            if all(abs(y - existing) > 1e-6 for existing in ys):
                ys.append(y)

        return [(x, y) for y in ys]

    def _route_connection_points(
        self,
        source_id: str,
        target_id: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        existing_segments: list[tuple[tuple[float, float], tuple[float, float], str]],
    ) -> list[tuple[float, float]]:
        source_direction = self._port_direction_for_point(source_id, (x1, y1), "outlet")
        target_direction = self._port_direction_for_point(target_id, (x2, y2), "inlet")
        path_finder = OrthogonalPathFinder(self._component_bounds_world, self._text_obstacles_world)
        return path_finder.route_connection(
            source_id,
            target_id,
            x1, y1, x2, y2,
            source_direction,
            target_direction,
            existing_segments,
        )

    def _orthogonal_intersection_point(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        q1: tuple[float, float],
        q2: tuple[float, float],
    ) -> tuple[float, float] | None:
        return orthogonal_intersection_point(p1, p2, q1, q2)

    def _bridge_points_for_route(
        self,
        route_points: list[tuple[float, float]],
        existing_segments: list[tuple[tuple[float, float], tuple[float, float], str]],
    ) -> list[tuple[float, float, str]]:
        bridges: list[tuple[float, float, str]] = []
        for i in range(len(route_points) - 1):
            p1 = route_points[i]
            p2 = route_points[i + 1]
            orientation = "horizontal" if abs(p1[1] - p2[1]) < 1e-9 else "vertical"
            for q1, q2, _ in existing_segments:
                cross = orthogonal_intersection_point(p1, p2, q1, q2)
                if cross is not None:
                    bridges.append((cross[0], cross[1], orientation))
        return bridges

    def _draw_bridge_arc(self, xw: float, yw: float, orientation: str, color: str, line_width: int) -> None:
        xv, yv = self._world_to_view(xw, yw)
        radius = max(5, int(7 * self.zoom))
        self.create_oval(
            xv - radius, yv - radius, xv + radius, yv + radius,
            fill="#11161f", outline="#11161f", width=0,
            tags=("connection_bridge",),
        )
        if orientation == "horizontal":
            start, extent = 0, 180
        else:
            start, extent = 270, 180
        self.create_arc(
            xv - radius, yv - radius, xv + radius, yv + radius,
            style=tk.ARC, outline=color, width=line_width,
            start=start, extent=extent,
            tags=("connection_bridge",),
        )

    def _simplify_polyline(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(points) <= 2:
            return points
        simplified = [points[0]]
        for point in points[1:]:
            simplified.append(point)
            while len(simplified) >= 3:
                p1 = simplified[-3]
                p2 = simplified[-2]
                p3 = simplified[-1]
                if (abs(p1[0] - p2[0]) < 1e-9 and abs(p2[0] - p3[0]) < 1e-9) or (
                    abs(p1[1] - p2[1]) < 1e-9 and abs(p2[1] - p3[1]) < 1e-9
                ):
                    simplified.pop(-2)
                else:
                    break
        return simplified

    def _route_penalty(self, source_id: str, target_id: str, points: list[tuple[float, float]]) -> float:
        penalty = 0.0
        length = 0.0
        total_segments = len(points) - 1
        for index in range(total_segments):
            x1, y1 = points[index]
            x2, y2 = points[index + 1]
            length += abs(x2 - x1) + abs(y2 - y1)
            for component_id, rect in self._component_bounds_world.items():
                if self._segment_hits_component_with_endpoint_allowance(
                    (x1, y1), (x2, y2),
                    component_id, rect, 10.0,
                    source_id, target_id,
                    index, total_segments,
                ):
                    penalty += 1000.0
            for rect in self._text_obstacles_world:
                if segment_intersects_rect((x1, y1), (x2, y2), rect, pad=2.0):
                    penalty += 1800.0
        return penalty + length * 0.001

    # ── Component drawing ─────────────────────────────────────────────

    def _draw_components(self) -> None:
        for component in self.circuit.components.values():
            self._draw_component(component)

    def _draw_component(self, component: Component) -> None:
        lay = self._layout(component)
        x1w = lay.x
        y1w = lay.y
        x2w = lay.x + lay.width
        y2w = lay.y + lay.height

        x1, y1 = self._world_to_view(x1w, y1w)
        x2, y2 = self._world_to_view(x2w, y2w)
        fill = "#28354a"
        outline = "#67d4ff" if component.component_id == self.selected_component_id else "#7d8797"
        border_width = max(1, int(2 * self.zoom))

        self.create_rectangle(
            x1, y1, x2, y2,
            fill=fill, outline=outline, width=border_width,
            tags=("component", f"component:{component.component_id}"),
        )

        self.create_text(
            x1 + 12, y1 + 14, anchor="w",
            text=component.name, fill="#f6f7fb",
            font=("Segoe UI", 12, "bold"),
            tags=("component_text", f"component:{component.component_id}"),
        )
        self.create_text(
            x1 + 12, y1 + 34, anchor="w",
            text=component.kind.value, fill="#b7c4d8",
            font=("Segoe UI", 10),
            tags=("component_text", f"component:{component.component_id}"),
        )
        self.create_text(
            x1 + 12, y1 + 52, anchor="w",
            text=component.process_kind.value, fill="#9fd8ff",
            font=("Segoe UI", 9, "italic"),
            tags=("component_text", f"component:{component.component_id}"),
        )
        if component.outlet_state is not None:
            self.create_text(
                x1 + 12, y1 + 72, anchor="w",
                text=f"P={component.outlet_state.pressure_mpa:.3f} MPa  h={component.outlet_state.enthalpy_kj_kg:.1f}",
                fill="#d8f1ff",
                font=("Segoe UI", 8),
                tags=("component_text", f"component:{component.component_id}"),
            )
        ui = self._ui(component)
        if ui.report:
            self.create_text(
                (x1 + x2) / 2.0, y2 + 22, anchor="n",
                text=ui.report[:58], fill="#d9dfef",
                font=("Segoe UI", 8),
                tags=("component_text", f"component:{component.component_id}"),
            )

        inlet_points = self._used_port_points.get(component.component_id, {}).get("inlet", [])
        outlet_points = self._used_port_points.get(component.component_id, {}).get("outlet", [])
        if not inlet_points:
            inlet_points = [lay.inlet_port()]
        if not outlet_points:
            outlet_points = [lay.outlet_port()]
        r = max(5, int(7 * self.zoom))
        for inlet_xw, inlet_yw in inlet_points:
            inlet_x, inlet_y = self._world_to_view(inlet_xw, inlet_yw)
            self.create_oval(
                inlet_x - r, inlet_y - r, inlet_x + r, inlet_y + r,
                fill="#ffcc66", outline="",
                tags=("port", f"port:{component.component_id}:{PortRole.INLET.value}"),
            )
        for outlet_xw, outlet_yw in outlet_points:
            outlet_x, outlet_y = self._world_to_view(outlet_xw, outlet_yw)
            self.create_oval(
                outlet_x - r, outlet_y - r, outlet_x + r, outlet_y + r,
                fill="#67d4ff", outline="",
                tags=("port", f"port:{component.component_id}:{PortRole.OUTLET.value}"),
            )
        if self.pending_connection_source_id == component.component_id:
            outlet_xw, outlet_yw = outlet_points[0]
            outlet_x, outlet_y = self._world_to_view(outlet_xw, outlet_yw)
            highlight_r = r + max(3, int(4 * self.zoom))
            self.create_oval(
                outlet_x - highlight_r, outlet_y - highlight_r,
                outlet_x + highlight_r, outlet_y + highlight_r,
                outline="#18f3a5", width=max(2, int(2 * self.zoom)),
            )
            self.create_text(
                outlet_x + 12, outlet_y - 14, anchor="w",
                text="source", fill="#18f3a5",
                font=("Segoe UI", 8, "bold"),
            )

    # ── Hit testing ───────────────────────────────────────────────────

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

    # ── Mouse events ──────────────────────────────────────────────────

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
        lay = self._layout(component)
        self._drag_offset_world = (world_x - lay.x, world_y - lay.y)

    def _on_left_drag(self, event: tk.Event) -> None:
        if self._drag_component_id is None:
            return
        component = self.circuit.components.get(self._drag_component_id)
        if component is None:
            return
        offset_x, offset_y = self._drag_offset_world
        world_x, world_y = self._view_to_world(event.x, event.y)
        lay = self._layout(component)
        lay.x = world_x - offset_x
        lay.y = world_y - offset_y
        self._schedule_drag_redraw()

    def _on_left_release(self, event: tk.Event) -> None:
        if self._drag_redraw_after_id is not None:
            self.after_cancel(self._drag_redraw_after_id)
            self._drag_redraw_after_id = None
        self.redraw()
        self._drag_component_id = None

    def _schedule_drag_redraw(self) -> None:
        if self._drag_redraw_after_id is not None:
            return
        self._drag_redraw_after_id = self.after(16, self._flush_drag_redraw)

    def _flush_drag_redraw(self) -> None:
        self._drag_redraw_after_id = None
        self.redraw()

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
