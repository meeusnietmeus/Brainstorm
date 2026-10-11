import math

import pytest

from brainstorm.domain import Node
from brainstorm.geometry import HEAD_ANGLE, edge_geometry, nodes_inside


def angle_between(a, b):
    dot = a[0] * b[0] + a[1] * b[1]
    return math.acos(dot / (math.hypot(*a) * math.hypot(*b)))


def test_target_to_the_right_connects_right_side_to_left_side():
    g = edge_geometry((0, 0, 100, 50), (300, 0, 100, 50))
    assert g.start == (100, 25)
    assert g.end == (300, 25)
    # Control points leave and enter horizontally.
    assert g.c1[1] == g.start[1] and g.c1[0] > g.start[0]
    assert g.c2[1] == g.end[1] and g.c2[0] < g.end[0]


def test_target_to_the_left_connects_left_side_to_right_side():
    g = edge_geometry((300, 0, 100, 50), (0, 0, 100, 50))
    assert g.start == (300, 25)
    assert g.end == (100, 25)


def test_target_below_connects_bottom_to_top():
    g = edge_geometry((0, 0, 100, 50), (0, 300, 100, 50))
    assert g.start == (50, 50)
    assert g.end == (50, 300)
    assert g.c1[0] == g.start[0] and g.c1[1] > g.start[1]
    assert g.c2[0] == g.end[0] and g.c2[1] < g.end[1]


def test_target_above_connects_top_to_bottom():
    g = edge_geometry((0, 300, 100, 50), (0, 0, 100, 50))
    assert g.start == (50, 300)
    assert g.end == (50, 50)


def test_diagonal_picks_the_dominant_axis():
    wide = edge_geometry((0, 0, 100, 50), (400, 100, 100, 50))
    assert wide.start == (100, 25)
    tall = edge_geometry((0, 0, 100, 50), (100, 400, 100, 50))
    assert tall.start == (50, 50)


def test_a_wide_frame_prefers_its_long_sides_relative_to_its_size():
    # Same center offset, but the wide source is "closer" vertically relative to its size.
    g = edge_geometry((0, 0, 1000, 100), (200, 300, 100, 50))
    assert g.start == (500, 100)  # bottom side


def test_overlapping_rectangles_still_produce_a_finite_curve():
    g = edge_geometry((0, 0, 100, 100), (50, 50, 100, 100))
    for point in (g.start, g.end, g.c1, g.c2, g.mid, *g.head_end, *g.head_start):
        assert all(math.isfinite(v) for v in point)


def test_identical_rectangles_do_not_crash():
    g = edge_geometry((0, 0, 100, 100), (0, 0, 100, 100))
    assert all(math.isfinite(v) for v in g.mid)


def test_arrowhead_points_back_along_the_curve_and_is_symmetric():
    g = edge_geometry((0, 0, 100, 50), (300, 0, 100, 50), head_size=20)
    p1, p2 = g.head_end
    tip = g.end
    # Arriving horizontally from the left: both corners sit to the left of the tip.
    assert p1[0] < tip[0] and p2[0] < tip[0]
    assert math.dist(p1, tip) == pytest.approx(20)
    assert math.dist(p2, tip) == pytest.approx(20)
    # Mirror images across the line of travel, and spread by twice the head angle.
    assert p1[1] - tip[1] == pytest.approx(-(p2[1] - tip[1]))
    spread = angle_between((p1[0] - tip[0], p1[1] - tip[1]), (p2[0] - tip[0], p2[1] - tip[1]))
    assert spread == pytest.approx(2 * HEAD_ANGLE)


def test_vertical_arrowhead_points_up_into_the_target():
    g = edge_geometry((0, 0, 100, 50), (0, 300, 100, 50))
    p1, p2 = g.head_end
    assert p1[1] < g.end[1] and p2[1] < g.end[1]  # the head sits above the top side it enters


def test_start_arrowhead_mirrors_the_end_one():
    g = edge_geometry((0, 0, 100, 50), (300, 0, 100, 50))
    p1, p2 = g.head_start
    assert p1[0] > g.start[0] and p2[0] > g.start[0]  # base lies along the line, inside the curve


def test_midpoint_lies_between_the_ends():
    g = edge_geometry((0, 0, 100, 50), (300, 200, 100, 50))
    assert g.start[0] < g.mid[0] < g.end[0]
    assert g.start[1] < g.mid[1] < g.end[1]


def test_as_dict_has_everything_qml_needs():
    d = edge_geometry((0, 0, 10, 10), (100, 0, 10, 10)).as_dict()
    assert set(d) == {"start", "end", "c1", "c2", "headEnd", "headStart", "mid"}
    assert set(d["start"]) == {"x", "y"} and len(d["headEnd"]) == 2


def make(node_id, x, y, w, h, kind="note"):
    return Node(
        id=node_id, space_id="s", kind=kind, created_at="t", updated_at="t", x=x, y=y, w=w, h=h
    )


def test_nodes_inside_requires_the_whole_rectangle_inside():
    frame = make("f", 0, 0, 500, 400, "frame")
    inside = make("in", 10, 10, 100, 50)
    touching = make("edge", 400, 350, 100, 50)  # exactly flush with the frame's corner
    sticking_out = make("out1", 450, 10, 100, 50)
    outside = make("out2", 600, 600, 50, 50)
    result = nodes_inside(frame, [frame, inside, touching, sticking_out, outside])
    assert {n.id for n in result} == {"in", "edge"}


def test_nodes_inside_skips_nodes_without_a_position_and_the_frame_itself():
    frame = make("f", 0, 0, 500, 400, "frame")
    hidden = Node(id="h", space_id="s", kind="code_todo", created_at="t", updated_at="t")
    assert nodes_inside(frame, [frame, hidden]) == []


def test_nested_frames_count_as_inside():
    outer = make("outer", 0, 0, 800, 600, "frame")
    inner = make("inner", 50, 50, 300, 200, "frame")
    assert [n.id for n in nodes_inside(outer, [outer, inner])] == ["inner"]
