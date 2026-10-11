"""Pure geometry for arrows and frames. No Qt, so it is easy to test."""

import math
from collections.abc import Iterable
from dataclasses import dataclass

from brainstorm.domain import Node

Point = tuple[float, float]
Rect = tuple[float, float, float, float]  # x, y, width, height

HEAD_SIZE = 14.0
HEAD_ANGLE = math.radians(24)


@dataclass(frozen=True)
class EdgeGeometry:
    start: Point
    end: Point
    c1: Point  # cubic control point next to start
    c2: Point  # cubic control point next to end
    head_end: tuple[Point, Point]  # the two base corners of the arrowhead at `end`
    head_start: tuple[Point, Point]  # same, for an arrowhead at `start`
    mid: Point  # point on the curve at t = 0.5, where the label chip sits

    def as_dict(self) -> dict:
        def p(point: Point) -> dict:
            return {"x": point[0], "y": point[1]}

        return {
            "start": p(self.start),
            "end": p(self.end),
            "c1": p(self.c1),
            "c2": p(self.c2),
            "headEnd": [p(q) for q in self.head_end],
            "headStart": [p(q) for q in self.head_start],
            "mid": p(self.mid),
        }


def _center(rect: Rect) -> Point:
    return rect[0] + rect[2] / 2, rect[1] + rect[3] / 2


def _side(rect: Rect, direction: Point) -> tuple[Point, Point]:
    """Midpoint of the side facing `direction` (a unit axis vector), and that side's normal."""
    x, y, w, h = rect
    if direction == (1, 0):
        return (x + w, y + h / 2), (1, 0)
    if direction == (-1, 0):
        return (x, y + h / 2), (-1, 0)
    if direction == (0, 1):
        return (x + w / 2, y + h), (0, 1)
    return (x + w / 2, y), (0, -1)


def _facing(src: Rect, dst: Rect) -> tuple[Point, Point]:
    """Axis directions that the source and destination sides face each other along."""
    (sx, sy), (dx, dy) = _center(src), _center(dst)
    ddx, ddy = dx - sx, dy - sy
    # Compare in units of the shapes' sizes so a wide frame still prefers its long sides.
    if abs(ddx) * (src[3] + dst[3]) >= abs(ddy) * (src[2] + dst[2]):
        step = (1, 0) if ddx >= 0 else (-1, 0)
    else:
        step = (0, 1) if ddy >= 0 else (0, -1)
    return step, (-step[0], -step[1])


def _unit(vx: float, vy: float, fallback: Point) -> Point:
    length = math.hypot(vx, vy)
    return (vx / length, vy / length) if length > 1e-9 else fallback


def _head(tip: Point, direction: Point, size: float) -> tuple[Point, Point]:
    """Base corners of an arrowhead whose tip is `tip`, pointing along `direction`."""
    corners = []
    for sign in (1, -1):
        angle = sign * HEAD_ANGLE
        rx = direction[0] * math.cos(angle) - direction[1] * math.sin(angle)
        ry = direction[0] * math.sin(angle) + direction[1] * math.cos(angle)
        corners.append((tip[0] - rx * size, tip[1] - ry * size))
    return corners[0], corners[1]


def edge_geometry(src: Rect, dst: Rect, head_size: float = HEAD_SIZE) -> EdgeGeometry:
    """Cubic curve from the side of `src` that faces `dst` to the side of `dst` facing back."""
    src_dir, dst_dir_inward = _facing(src, dst)
    start, src_normal = _side(src, src_dir)
    end, dst_normal = _side(dst, dst_dir_inward)

    reach = max(30.0, min(200.0, math.dist(start, end) * 0.4))
    c1 = (start[0] + src_normal[0] * reach, start[1] + src_normal[1] * reach)
    c2 = (end[0] + dst_normal[0] * reach, end[1] + dst_normal[1] * reach)

    end_dir = _unit(end[0] - c2[0], end[1] - c2[1], (-dst_normal[0], -dst_normal[1]))
    start_dir = _unit(start[0] - c1[0], start[1] - c1[1], (-src_normal[0], -src_normal[1]))
    mid = (
        (start[0] + 3 * c1[0] + 3 * c2[0] + end[0]) / 8,
        (start[1] + 3 * c1[1] + 3 * c2[1] + end[1]) / 8,
    )
    return EdgeGeometry(
        start=start,
        end=end,
        c1=c1,
        c2=c2,
        head_end=_head(end, end_dir, head_size),
        head_start=_head(start, start_dir, head_size),
        mid=mid,
    )


def node_rect(node: Node) -> Rect | None:
    if node.x is None or node.y is None or node.w is None or node.h is None:
        return None
    return node.x, node.y, node.w, node.h


def nodes_inside(frame: Node, nodes: Iterable[Node]) -> list[Node]:
    """Nodes whose rectangle lies fully inside the frame's rectangle (the frame itself excluded).

    Computed fresh whenever it is needed, never stored: moving a frame carries whatever was
    inside it when the drag started.
    """
    bounds = node_rect(frame)
    if bounds is None:
        return []
    fx, fy, fw, fh = bounds
    inside = []
    for node in nodes:
        rect = node_rect(node)
        if node.id == frame.id or rect is None:
            continue
        x, y, w, h = rect
        if x >= fx and y >= fy and x + w <= fx + fw and y + h <= fy + fh:
            inside.append(node)
    return inside
