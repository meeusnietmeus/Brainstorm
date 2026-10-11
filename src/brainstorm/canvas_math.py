"""Pure viewport math for the canvas. QML calls this through CanvasController."""

MIN_ZOOM = 0.05
MAX_ZOOM = 8.0


def clamp_zoom(scale: float) -> float:
    return max(MIN_ZOOM, min(MAX_ZOOM, scale))


def zoom_at(
    offset: tuple[float, float],
    scale: float,
    cursor: tuple[float, float],
    factor: float,
) -> tuple[float, float, float]:
    """Zoom by `factor` keeping the world point under `cursor` fixed on screen.

    `offset` is the screen position of the world origin (world.x, world.y). A world point w
    appears at screen = offset + w * scale. Returns (new_offset_x, new_offset_y, new_scale).
    """
    new_scale = clamp_zoom(scale * factor)
    world_x = (cursor[0] - offset[0]) / scale
    world_y = (cursor[1] - offset[1]) / scale
    return cursor[0] - world_x * new_scale, cursor[1] - world_y * new_scale, new_scale
