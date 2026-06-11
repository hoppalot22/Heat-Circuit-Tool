"""Shared geometry utilities for the UI layer."""


def segment_intersects_rect(
    p1: tuple[float, float],
    p2: tuple[float, float],
    rect: tuple[float, float, float, float],
    pad: float = 0.0,
) -> bool:
    """Check if an axis-aligned segment intersects a rectangle.

    p1, p2: segment endpoints (must share either x or y).
    rect: (x1, y1, x2, y2) bounding box.
    pad: extra padding applied to all sides of the rect.
    """
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