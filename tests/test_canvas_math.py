import math

import pytest

from brainstorm.canvas_math import MAX_ZOOM, MIN_ZOOM, zoom_at


def screen_of(world, offset, scale):
    return offset[0] + world[0] * scale, offset[1] + world[1] * scale


@pytest.mark.parametrize("factor", [0.5, 1.2, 3.0])
@pytest.mark.parametrize("offset", [(0.0, 0.0), (-300.0, 120.0)])
@pytest.mark.parametrize("scale", [0.1, 1.0, 4.0])
def test_point_under_cursor_stays_fixed(offset, scale, factor):
    cursor = (410.0, 255.0)
    world = ((cursor[0] - offset[0]) / scale, (cursor[1] - offset[1]) / scale)
    ox, oy, new_scale = zoom_at(offset, scale, cursor, factor)
    sx, sy = screen_of(world, (ox, oy), new_scale)
    assert math.isclose(sx, cursor[0], abs_tol=1e-6)
    assert math.isclose(sy, cursor[1], abs_tol=1e-6)


def test_scale_is_multiplied_by_factor():
    assert zoom_at((0, 0), 1.0, (10, 10), 2.0)[2] == 2.0


def test_zoom_is_clamped():
    assert zoom_at((0, 0), 1.0, (0, 0), 1e6)[2] == MAX_ZOOM
    assert zoom_at((0, 0), 1.0, (0, 0), 1e-6)[2] == MIN_ZOOM


def test_cursor_stays_fixed_even_when_clamped():
    offset, scale, cursor = (50.0, 60.0), 7.0, (200.0, 100.0)
    world = ((cursor[0] - offset[0]) / scale, (cursor[1] - offset[1]) / scale)
    ox, oy, new_scale = zoom_at(offset, scale, cursor, 10.0)
    assert new_scale == MAX_ZOOM
    sx, sy = screen_of(world, (ox, oy), new_scale)
    assert math.isclose(sx, cursor[0], abs_tol=1e-6)
    assert math.isclose(sy, cursor[1], abs_tol=1e-6)


def test_zooming_in_then_out_returns_to_start():
    start = ((12.0, -40.0), 1.0)
    ox, oy, s = zoom_at(start[0], start[1], (300, 200), 2.0)
    ox, oy, s = zoom_at((ox, oy), s, (300, 200), 0.5)
    assert (round(ox, 6), round(oy, 6), s) == (12.0, -40.0, 1.0)
