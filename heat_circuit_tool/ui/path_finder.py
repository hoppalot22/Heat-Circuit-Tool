from __future__ import annotations

import heapq


def orthogonal_intersection_point(
    p1: tuple[float, float],
    p2: tuple[float, float],
    q1: tuple[float, float],
    q2: tuple[float, float],
) -> tuple[float, float] | None:
    p_horizontal = abs(p1[1] - p2[1]) < 1e-9
    q_horizontal = abs(q1[1] - q2[1]) < 1e-9
    if p_horizontal == q_horizontal:
        return None

    if p_horizontal:
        hx1, hy = p1
        hx2, _ = p2
        vx, vy1 = q1
        _, vy2 = q2
        xmin, xmax = (hx1, hx2) if hx1 <= hx2 else (hx2, hx1)
        ymin, ymax = (vy1, vy2) if vy1 <= vy2 else (vy2, vy1)
        ix, iy = vx, hy
    else:
        vx, vy1 = p1
        _, vy2 = p2
        hx1, hy = q1
        hx2, _ = q2
        xmin, xmax = (hx1, hx2) if hx1 <= hx2 else (hx2, hx1)
        ymin, ymax = (vy1, vy2) if vy1 <= vy2 else (vy2, vy1)
        ix, iy = vx, hy

    eps = 1e-6
    if not (xmin + eps < ix < xmax - eps and ymin + eps < iy < ymax - eps):
        return None
    return (ix, iy)


class OrthogonalPathFinder:
    def __init__(
        self,
        component_bounds: dict[str, tuple[float, float, float, float]],
        text_obstacles: list[tuple[float, float, float, float]],
    ) -> None:
        self._component_bounds_world = component_bounds
        self._text_obstacles_world = text_obstacles

    def route_connection(
        self,
        source_id: str,
        target_id: str,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        source_direction: tuple[float, float],
        target_direction: tuple[float, float],
        existing_segments: list[tuple[tuple[float, float], tuple[float, float], str]],
    ) -> list[tuple[float, float]]:
        grid = 26.0
        obstacles = self._route_obstacles(source_id, target_id, pad=22.0)
        source_stub = self._protrusion_anchor((x1, y1), source_direction, obstacles, min_distance=24.0)
        target_stub = self._protrusion_anchor((x2, y2), target_direction, obstacles, min_distance=24.0)

        path = self._a_star_route(source_stub, target_stub, obstacles, grid, existing_segments)
        if path is None:
            fallback = self._fallback_route_candidates(source_stub[0], source_stub[1], target_stub[0], target_stub[1])
            valid_fallback = [
                points
                for points in fallback
                if not self._polyline_hits_obstacles(
                    self._compose_route_with_stubs((x1, y1), source_stub, points, target_stub, (x2, y2)),
                    source_id,
                    target_id,
                    pad=12.0,
                )
            ]
            candidates = valid_fallback if valid_fallback else fallback
            best_core = min(candidates, key=lambda points: self._route_penalty(source_id, target_id, points))
            core = self._optimize_orthogonal_polyline(self._normalize_route_geometry(best_core), source_id, target_id)
            route = self._compose_route_with_stubs((x1, y1), source_stub, core, target_stub, (x2, y2))
            return self._reduce_tiny_doglegs(route, source_id, target_id)

        core_path = [source_stub] + path + [target_stub]
        core_path = self._optimize_orthogonal_polyline(
            self._normalize_route_geometry(core_path),
            source_id,
            target_id,
        )
        simplified = self._compose_route_with_stubs((x1, y1), source_stub, core_path, target_stub, (x2, y2))
        if self._polyline_hits_obstacles(simplified, source_id, target_id, pad=12.0):
            fallback = self._fallback_route_candidates(source_stub[0], source_stub[1], target_stub[0], target_stub[1])
            valid_fallback = [
                points
                for points in fallback
                if not self._polyline_hits_obstacles(
                    self._compose_route_with_stubs((x1, y1), source_stub, points, target_stub, (x2, y2)),
                    source_id,
                    target_id,
                    pad=12.0,
                )
            ]
            candidates = valid_fallback if valid_fallback else fallback
            best_core = min(candidates, key=lambda points: self._route_penalty(source_id, target_id, points))
            core = self._optimize_orthogonal_polyline(self._normalize_route_geometry(best_core), source_id, target_id)
            simplified = self._compose_route_with_stubs((x1, y1), source_stub, core, target_stub, (x2, y2))
        simplified = self._reroute_around_text(simplified, source_id, target_id)
        cleaned = self._reduce_tiny_doglegs(simplified, source_id, target_id)
        cleaned = self._collapse_short_bridge_jogs(cleaned, source_id, target_id)
        return self._simplify_polyline(cleaned)

    def _polyline_hits_text(self, points: list[tuple[float, float]]) -> bool:
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            for rect in self._text_obstacles_world:
                if self._segment_intersects_rect(p1, p2, rect, pad=2.0):
                    return True
        return False

    def _reroute_around_text(
        self,
        points: list[tuple[float, float]],
        source_id: str,
        target_id: str,
    ) -> list[tuple[float, float]]:
        route = points[:]
        for _ in range(6):
            changed = False
            for index in range(len(route) - 1):
                p1 = route[index]
                p2 = route[index + 1]
                for rect in self._text_obstacles_world:
                    if not self._segment_intersects_rect(p1, p2, rect, pad=2.0):
                        continue
                    rx1, ry1, rx2, ry2 = rect
                    lane_candidates: list[list[tuple[float, float]]] = []
                    if abs(p1[0] - p2[0]) < 1e-9:
                        x = p1[0]
                        lane_candidates.append([p1, (rx1 - 20.0, p1[1]), (rx1 - 20.0, p2[1]), p2])
                        lane_candidates.append([p1, (rx2 + 20.0, p1[1]), (rx2 + 20.0, p2[1]), p2])
                        lane_candidates.sort(key=lambda pts: abs(pts[1][0] - x))
                    elif abs(p1[1] - p2[1]) < 1e-9:
                        y = p1[1]
                        lane_candidates.append([p1, (p1[0], ry1 - 16.0), (p2[0], ry1 - 16.0), p2])
                        lane_candidates.append([p1, (p1[0], ry2 + 16.0), (p2[0], ry2 + 16.0), p2])
                        lane_candidates.sort(key=lambda pts: abs(pts[1][1] - y))
                    else:
                        continue

                    for detour in lane_candidates:
                        candidate = route[:index] + detour + route[index + 2 :]
                        candidate = self._normalize_route_geometry(candidate)
                        if self._polyline_hits_obstacles(candidate, source_id, target_id, pad=12.0):
                            continue
                        route = candidate
                        changed = True
                        break
                    if changed:
                        break
                if changed:
                    break
            if not changed:
                break
        return route

    def _compose_route_with_stubs(
        self,
        source_port: tuple[float, float],
        source_stub: tuple[float, float],
        core_points: list[tuple[float, float]],
        target_stub: tuple[float, float],
        target_port: tuple[float, float],
    ) -> list[tuple[float, float]]:
        filtered_core = [
            point
            for point in core_points
            if self._axis_distance(point, source_stub) > 1e-6 and self._axis_distance(point, target_stub) > 1e-6
        ]
        route: list[tuple[float, float]] = [source_port, source_stub]

        if filtered_core:
            first_core = filtered_core[0]
            if abs(first_core[0] - source_stub[0]) > 1e-9 and abs(first_core[1] - source_stub[1]) > 1e-9:
                route.append((first_core[0], source_stub[1]))
            route.extend(filtered_core)
        else:
            route.append(target_stub)

        if self._axis_distance(route[-1], target_stub) > 1e-6:
            last_core = route[-1]
            if abs(last_core[0] - target_stub[0]) > 1e-9 and abs(last_core[1] - target_stub[1]) > 1e-9:
                route.append((target_stub[0], last_core[1]))
            route.append(target_stub)

        route.append(target_port)
        return self._simplify_polyline(route)

    def _simplify_preserving_terminal_stubs(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(points) <= 4:
            return points
        head = points[:2]
        middle = points[2:-2]
        tail = points[-2:]
        simplified_middle = self._simplify_polyline(middle) if len(middle) >= 2 else middle
        return head + simplified_middle + tail

    def _fallback_route_candidates(self, x1: float, y1: float, x2: float, y2: float) -> list[list[tuple[float, float]]]:
        dx = x2 - x1
        mid_x = x1 + dx / 2.0
        top_y = min(y1, y2) - 90.0
        bottom_y = max(y1, y2) + 90.0
        source_step = x1 + 40.0
        target_step = x2 - 40.0
        candidates = [
            [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)],
            [(x1, y1), (source_step, y1), (source_step, top_y), (target_step, top_y), (target_step, y2), (x2, y2)],
            [(x1, y1), (source_step, y1), (source_step, bottom_y), (target_step, bottom_y), (target_step, y2), (x2, y2)],
        ]
        left_lane = min(x1, x2) - 140.0
        right_lane = max(x1, x2) + 140.0
        candidates.append([(x1, y1), (source_step, y1), (source_step, top_y), (left_lane, top_y), (left_lane, y2), (x2, y2)])
        candidates.append([(x1, y1), (source_step, y1), (source_step, bottom_y), (left_lane, bottom_y), (left_lane, y2), (x2, y2)])
        candidates.append([(x1, y1), (right_lane, y1), (right_lane, top_y), (target_step, top_y), (target_step, y2), (x2, y2)])
        candidates.append([(x1, y1), (right_lane, y1), (right_lane, bottom_y), (target_step, bottom_y), (target_step, y2), (x2, y2)])
        if x2 < x1:
            candidates.append([(x1, y1), (source_step, y1), (source_step, top_y), (left_lane, top_y), (left_lane, y2), (x2, y2)])
            candidates.append([(x1, y1), (source_step, y1), (source_step, bottom_y), (left_lane, bottom_y), (left_lane, y2), (x2, y2)])
            candidates.append([(x1, y1), (right_lane, y1), (right_lane, top_y), (target_step, top_y), (target_step, y2), (x2, y2)])
            candidates.append([(x1, y1), (right_lane, y1), (right_lane, bottom_y), (target_step, bottom_y), (target_step, y2), (x2, y2)])
        return [self._normalize_route_geometry(points) for points in candidates]

    def _normalize_route_geometry(self, points: list[tuple[float, float]]) -> list[tuple[float, float]]:
        if len(points) <= 2:
            return points

        orthogonal: list[tuple[float, float]] = [points[0]]
        for point in points[1:]:
            prev = orthogonal[-1]
            if abs(prev[0] - point[0]) < 1e-9 or abs(prev[1] - point[1]) < 1e-9:
                orthogonal.append(point)
                continue
            corner = (point[0], prev[1])
            orthogonal.append(corner)
            orthogonal.append(point)

        cleaned = self._simplify_polyline(orthogonal)

        min_len = 12.0
        changed = True
        while changed and len(cleaned) >= 4:
            changed = False
            i = 1
            while i < len(cleaned) - 2:
                a = cleaned[i - 1]
                b = cleaned[i]
                c = cleaned[i + 1]
                d = cleaned[i + 2]
                if self._axis_distance(b, c) < min_len and self._segment_direction(a, b) == self._segment_direction(c, d):
                    candidate = cleaned[:i] + [cleaned[i + 2]] + cleaned[i + 3 :]
                    candidate = self._simplify_polyline(candidate)
                    cleaned = candidate
                    changed = True
                    break
                i += 1

        return self._simplify_polyline(cleaned)

    def _axis_distance(self, p1: tuple[float, float], p2: tuple[float, float]) -> float:
        return abs(p2[0] - p1[0]) + abs(p2[1] - p1[1])

    def _segment_direction(self, p1: tuple[float, float], p2: tuple[float, float]) -> str:
        if abs(p1[1] - p2[1]) < 1e-9:
            return "h"
        if abs(p1[0] - p2[0]) < 1e-9:
            return "v"
        return "d"

    def _protrusion_anchor(
        self,
        port: tuple[float, float],
        direction: tuple[float, float],
        obstacles: list[tuple[float, float, float, float]],
        min_distance: float,
    ) -> tuple[float, float]:
        x, y = port
        dx, dy = direction
        current = (x + min_distance * dx, y + min_distance * dy)
        if not self._in_obstacle(current, obstacles) and not self._segment_hits_obstacles(port, current, obstacles):
            return current

        step = 12.0
        for _ in range(16):
            current = (current[0] + step * dx, current[1] + step * dy)
            if not self._in_obstacle(current, obstacles) and not self._segment_hits_obstacles(port, current, obstacles):
                return current
        return (x + min_distance * dx, y + min_distance * dy)

    def _optimize_orthogonal_polyline(
        self,
        points: list[tuple[float, float]],
        source_id: str,
        target_id: str,
    ) -> list[tuple[float, float]]:
        if len(points) <= 3:
            return points

        optimized = self._simplify_polyline(points)
        changed = True
        while changed and len(optimized) > 3:
            changed = False
            n = len(optimized)
            baseline_score = self._route_penalty(source_id, target_id, optimized)
            for i in range(2, n - 4):
                for j in range(n - 3, i + 1, -1):
                    old_subpath = optimized[i : j + 1]
                    connectors = self._orthogonal_connectors(old_subpath[0], old_subpath[-1])
                    replacement: list[tuple[float, float]] | None = None
                    replacement_score = baseline_score
                    for candidate in connectors:
                        merged = optimized[:i] + candidate + optimized[j + 1 :]
                        merged = self._simplify_polyline(merged)
                        if self._polyline_hits_obstacles(merged, source_id, target_id, pad=12.0):
                            continue
                        score = self._route_penalty(source_id, target_id, merged)
                        if score + 1e-6 < replacement_score:
                            replacement = merged
                            replacement_score = score
                    if replacement is not None:
                        optimized = replacement
                        changed = True
                        break
                if changed:
                    break
        return self._simplify_polyline(optimized)

    def _orthogonal_connectors(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
    ) -> list[list[tuple[float, float]]]:
        sx, sy = start
        ex, ey = end
        if abs(sx - ex) < 1e-9 or abs(sy - ey) < 1e-9:
            return [[start, end]]
        return [
            [start, (ex, sy), end],
            [start, (sx, ey), end],
        ]

    def _polyline_length(self, points: list[tuple[float, float]]) -> float:
        total = 0.0
        for idx in range(len(points) - 1):
            total += self._axis_distance(points[idx], points[idx + 1])
        return total

    def _segment_hits_obstacles(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        obstacles: list[tuple[float, float, float, float]],
    ) -> bool:
        for rect in obstacles:
            if self._segment_intersects_rect(p1, p2, rect, pad=0.0):
                return True
        return False

    def _polyline_hits_obstacles(
        self,
        points: list[tuple[float, float]],
        source_id: str,
        target_id: str,
        pad: float,
    ) -> bool:
        total_segments = len(points) - 1
        for i in range(total_segments):
            p1 = points[i]
            p2 = points[i + 1]
            for component_id, rect in self._component_bounds_world.items():
                if self._segment_hits_component_with_endpoint_allowance(
                    p1,
                    p2,
                    component_id,
                    rect,
                    pad,
                    source_id,
                    target_id,
                    i,
                    total_segments,
                ):
                    return True
            for rect in self._text_obstacles_world:
                if self._segment_intersects_rect(p1, p2, rect, pad=2.0):
                    return True
        return False

    def _route_obstacles(self, source_id: str, target_id: str, pad: float) -> list[tuple[float, float, float, float]]:
        obstacles: list[tuple[float, float, float, float]] = []
        for component_id, (x1, y1, x2, y2) in self._component_bounds_world.items():
            component_pad = pad
            if component_id in {source_id, target_id}:
                component_pad = max(8.0, pad * 0.45)
            obstacles.append((x1 - component_pad, y1 - component_pad, x2 + component_pad, y2 + component_pad))
        for x1, y1, x2, y2 in self._text_obstacles_world:
            obstacles.append((x1 - 6.0, y1 - 2.0, x2 + 6.0, y2 + 2.0))
        return obstacles

    def _segment_hits_component_with_endpoint_allowance(
        self,
        p1: tuple[float, float],
        p2: tuple[float, float],
        component_id: str,
        rect: tuple[float, float, float, float],
        pad: float,
        source_id: str,
        target_id: str,
        segment_index: int,
        total_segments: int,
    ) -> bool:
        if not self._segment_intersects_rect(p1, p2, rect, pad=pad):
            return False
        if component_id == source_id and segment_index == 0:
            return False
        if component_id == target_id and segment_index == total_segments - 1:
            return False
        return True

    def _in_obstacle(self, point: tuple[float, float], obstacles: list[tuple[float, float, float, float]]) -> bool:
        px, py = point
        for x1, y1, x2, y2 in obstacles:
            if x1 <= px <= x2 and y1 <= py <= y2:
                return True
        return False

    def _a_star_route(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        obstacles: list[tuple[float, float, float, float]],
        grid: float,
        existing_segments: list[tuple[tuple[float, float], tuple[float, float], str]],
    ) -> list[tuple[float, float]] | None:
        for margin in (220.0, 420.0, 700.0):
            min_x = min(start[0], end[0]) - margin
            max_x = max(start[0], end[0]) + margin
            min_y = min(start[1], end[1]) - margin
            max_y = max(start[1], end[1]) + margin
            for x1, y1, x2, y2 in obstacles:
                min_x = min(min_x, x1 - 50.0)
                min_y = min(min_y, y1 - 50.0)
                max_x = max(max_x, x2 + 50.0)
                max_y = max(max_y, y2 + 50.0)

            def snap(p: tuple[float, float]) -> tuple[int, int]:
                return (int(round(p[0] / grid)), int(round(p[1] / grid)))

            start_n = snap(start)
            end_n = snap(end)

            def to_world(n: tuple[int, int]) -> tuple[float, float]:
                return (n[0] * grid, n[1] * grid)

            if self._in_obstacle(to_world(start_n), obstacles):
                continue
            if self._in_obstacle(to_world(end_n), obstacles):
                continue

            open_heap: list[tuple[float, int, tuple[tuple[int, int], tuple[int, int] | None]]] = []
            counter = 0
            start_state: tuple[tuple[int, int], tuple[int, int] | None] = (start_n, None)
            heapq.heappush(open_heap, (0.0, counter, start_state))

            came_from: dict[
                tuple[tuple[int, int], tuple[int, int] | None],
                tuple[tuple[int, int], tuple[int, int] | None] | None,
            ] = {start_state: None}
            g_score: dict[tuple[tuple[int, int], tuple[int, int] | None], float] = {start_state: 0.0}
            visited: set[tuple[tuple[int, int], tuple[int, int] | None]] = set()

            neighbors = [(1, 0), (-1, 0), (0, 1), (0, -1)]

            def heuristic(a: tuple[int, int], b: tuple[int, int]) -> float:
                # Keep heuristic weak so bend/crossing penalties dominate over pure length.
                return 0.05 * (abs(a[0] - b[0]) + abs(a[1] - b[1]))

            while open_heap:
                _, _, current_state = heapq.heappop(open_heap)
                if current_state in visited:
                    continue
                visited.add(current_state)
                current, current_dir = current_state

                if current == end_n:
                    nodes: list[tuple[int, int]] = [current]
                    trace_state = current_state
                    while came_from.get(trace_state) is not None:
                        prev_state = came_from[trace_state]
                        if prev_state is None:
                            break
                        nodes.append(prev_state[0])
                        trace_state = prev_state
                    nodes.reverse()
                    world_path = [to_world(n) for n in nodes]
                    return world_path[1:-1] if len(world_path) > 2 else []

                for ndx, ndy in neighbors:
                    nxt = (current[0] + ndx, current[1] + ndy)
                    nxt_world = to_world(nxt)
                    if nxt_world[0] < min_x or nxt_world[0] > max_x or nxt_world[1] < min_y or nxt_world[1] > max_y:
                        continue
                    if self._in_obstacle(nxt_world, obstacles):
                        continue

                    move_cost = 0.15
                    if current_dir is not None and current_dir != (ndx, ndy):
                        move_cost += 2.8
                    crossing_penalty = self._crossing_penalty(current, nxt, grid, existing_segments)
                    move_cost += crossing_penalty
                    next_state: tuple[tuple[int, int], tuple[int, int] | None] = (nxt, (ndx, ndy))
                    tentative = g_score[current_state] + move_cost
                    if tentative >= g_score.get(next_state, float("inf")):
                        continue

                    came_from[next_state] = current_state
                    g_score[next_state] = tentative
                    counter += 1
                    f = tentative + heuristic(nxt, end_n)
                    heapq.heappush(open_heap, (f, counter, next_state))

        return None

    def _crossing_penalty(
        self,
        from_node: tuple[int, int],
        to_node: tuple[int, int],
        grid: float,
        existing_segments: list[tuple[tuple[float, float], tuple[float, float], str]],
    ) -> float:
        p1 = (from_node[0] * grid, from_node[1] * grid)
        p2 = (to_node[0] * grid, to_node[1] * grid)
        crossings = 0
        for q1, q2, _ in existing_segments:
            if orthogonal_intersection_point(p1, p2, q1, q2) is not None:
                crossings += 1
        return crossings * 2.0

    def _route_penalty(self, source_id: str, target_id: str, points: list[tuple[float, float]]) -> float:
        penalty = 0.0
        length = 0.0
        bends = 0
        total_segments = len(points) - 1
        for index in range(total_segments):
            x1, y1 = points[index]
            x2, y2 = points[index + 1]
            length += abs(x2 - x1) + abs(y2 - y1)
            for component_id, rect in self._component_bounds_world.items():
                if self._segment_hits_component_with_endpoint_allowance(
                    (x1, y1),
                    (x2, y2),
                    component_id,
                    rect,
                    10.0,
                    source_id,
                    target_id,
                    index,
                    total_segments,
                ):
                    penalty += 1000.0
            for rect in self._text_obstacles_world:
                if self._segment_intersects_rect((x1, y1), (x2, y2), rect, pad=2.0):
                    penalty += 1800.0
        for index in range(1, total_segments):
            prev = (points[index - 1], points[index])
            curr = (points[index], points[index + 1])
            if self._segment_direction(prev[0], prev[1]) != self._segment_direction(curr[0], curr[1]):
                bends += 1
        # Keep length as a tie-breaker only; prefer routes with fewer bends.
        return penalty + bends * 300.0 + length * 0.0001

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

    def _reduce_tiny_doglegs(
        self,
        points: list[tuple[float, float]],
        source_id: str,
        target_id: str,
        min_len: float = 10.0,
    ) -> list[tuple[float, float]]:
        route = points[:]
        changed = True
        while changed and len(route) >= 4:
            changed = False
            if len(route) >= 5:
                for i in range(len(route) - 4):
                    a, b, c, d, e = route[i], route[i + 1], route[i + 2], route[i + 3], route[i + 4]
                    ab_len = self._axis_distance(a, b)
                    bc_len = self._axis_distance(b, c)
                    if ab_len >= min_len or bc_len >= min_len:
                        continue
                    dirs = [
                        self._segment_direction(a, b),
                        self._segment_direction(b, c),
                        self._segment_direction(c, d),
                        self._segment_direction(d, e),
                    ]
                    if "d" in dirs:
                        continue
                    candidates: list[list[tuple[float, float]]] = []
                    if dirs == ["v", "h", "v", "h"]:
                        pivot = (a[0], d[1])
                        candidate = route[: i + 1] + [pivot] + route[i + 4 :]
                        candidates.append(candidate)
                    elif dirs == ["h", "v", "h", "v"]:
                        pivot = (d[0], a[1])
                        candidate = route[: i + 1] + [pivot] + route[i + 4 :]
                        candidates.append(candidate)

                    best = None
                    best_score = float("inf")
                    for candidate in candidates:
                        candidate = self._normalize_route_geometry(candidate)
                        if self._polyline_hits_obstacles(candidate, source_id, target_id, pad=12.0):
                            continue
                        score = self._route_penalty(source_id, target_id, candidate)
                        if score < best_score:
                            best = candidate
                            best_score = score
                    if best is not None:
                        route = best
                        changed = True
                        break
                if changed:
                    continue

            for i in range(len(route) - 3):
                a, b, c, d = route[i], route[i + 1], route[i + 2], route[i + 3]
                ab_len = self._axis_distance(a, b)
                cd_len = self._axis_distance(c, d)
                if ab_len >= min_len or cd_len >= min_len:
                    continue
                ab_dir = self._segment_direction(a, b)
                bc_dir = self._segment_direction(b, c)
                cd_dir = self._segment_direction(c, d)
                if ab_dir == "d" or bc_dir == "d" or cd_dir == "d":
                    continue
                if ab_dir != cd_dir or ab_dir == bc_dir:
                    continue

                candidates: list[list[tuple[float, float]]] = []
                if ab_dir == "h" and bc_dir == "v":
                    candidate1 = route[: i + 1] + [(a[0], c[1])] + route[i + 3 :]
                    candidate2 = route[: i + 1] + [(d[0], c[1])] + route[i + 3 :]
                elif ab_dir == "v" and bc_dir == "h":
                    candidate1 = route[: i + 1] + [(c[0], a[1])] + route[i + 3 :]
                    candidate2 = route[: i + 1] + [(c[0], d[1])] + route[i + 3 :]
                else:
                    continue
                candidates.extend([candidate1, candidate2])

                best = None
                best_score = float("inf")
                for candidate in candidates:
                    candidate = self._normalize_route_geometry(candidate)
                    if self._polyline_hits_obstacles(candidate, source_id, target_id, pad=12.0):
                        continue
                    score = self._route_penalty(source_id, target_id, candidate)
                    if score < best_score:
                        best = candidate
                        best_score = score
                if best is not None:
                    route = best
                    changed = True
                    break
        return route

    def _collapse_short_bridge_jogs(
        self,
        points: list[tuple[float, float]],
        source_id: str,
        target_id: str,
        max_jog_len: float = 8.0,
    ) -> list[tuple[float, float]]:
        route = points[:]
        changed = True
        while changed and len(route) >= 4:
            changed = False
            for i in range(1, len(route) - 3):
                a, b, c, d = route[i], route[i + 1], route[i + 2], route[i + 3]
                ab_dir = self._segment_direction(a, b)
                bc_dir = self._segment_direction(b, c)
                cd_dir = self._segment_direction(c, d)
                if "d" in {ab_dir, bc_dir, cd_dir}:
                    continue
                jog_len = self._axis_distance(b, c)
                if jog_len > max_jog_len:
                    continue

                prev_dir = self._segment_direction(route[i - 1], a)
                candidate: list[tuple[float, float]] | None = None
                if ab_dir == "h" and bc_dir == "v" and cd_dir == "h" and prev_dir == "v":
                    lifted = (a[0], c[1])
                    candidate = route[:i] + [lifted, d] + route[i + 4 :]
                elif ab_dir == "v" and bc_dir == "h" and cd_dir == "v" and prev_dir == "h":
                    shifted = (c[0], a[1])
                    candidate = route[:i] + [shifted, d] + route[i + 4 :]

                if candidate is None:
                    continue

                candidate = self._simplify_polyline(candidate)
                if self._polyline_hits_obstacles(candidate, source_id, target_id, pad=12.0):
                    continue
                if self._route_penalty(source_id, target_id, candidate) + 1e-6 >= self._route_penalty(
                    source_id,
                    target_id,
                    route,
                ):
                    continue

                route = candidate
                changed = True
                break
        return route

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
