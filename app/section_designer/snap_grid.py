import math
from core.units import unit_registry

_DISPLAY_STEPS = [
    0.001, 0.002, 0.005,
    0.01,  0.02,  0.05,
    0.1,   0.2,   0.5,
    1.0,   2.0,   5.0,
    10.0,  20.0,  50.0,
    100.0,
]

class SnapGrid:
    """
    Coordinate system and optional snap-to-grid for the Section Designer canvas.

    World space  : base SI metres, origin at centroid of canvas.
    Display space: current unit system (mm, cm, m, ft, in).
    Pixel space  : Qt widget pixels, y-axis flipped (screen y grows downward).

    Parameters
    ----------
    snap_enabled : bool   — snap mouse to grid points when True
    """

    def __init__(self, snap_enabled: bool = True):
        self.snap_enabled = snap_enabled

        self._scale: float = 200.0                      

        self._origin_px: tuple = (0.0, 0.0)

        self._grid_spacing_m: float = 0.05                 

        self._display_step: float = 0.05

    def set_origin(self, cx_px: float, cy_px: float):
        """Call this from the canvas resizeEvent and on first paint."""
        self._origin_px = (cx_px, cy_px)

    def set_scale(self, px_per_metre: float):
        """Zoom level. Canvas calls this on wheel events."""
        self._scale = max(1.0, px_per_metre)
        self._auto_pick_grid_step()

    def zoom(self, factor: float, anchor_world: tuple = (0.0, 0.0)):
        """
        Multiply current scale by factor.
        anchor_world keeps that world point fixed under the mouse.
        """
        self._scale = max(1.0, self._scale * factor)
        self._auto_pick_grid_step()

    def pan(self, delta_px_x: float, delta_px_y: float):
        """Shift the world origin by a pixel delta (from mouse drag)."""
        ox, oy = self._origin_px
        self._origin_px = (ox + delta_px_x, oy + delta_px_y)

    def pixel_to_world(self, px: float, py: float) -> tuple:
        """
        Pixel (Qt coords) → world (metres).
        Qt y grows downward; world y grows rightward, z grows upward.
        Returns (y_world, z_world) matching get_shape_coords() convention.
        """
        ox, oy = self._origin_px
        y = (px - ox) / self._scale
        z = -(py - oy) / self._scale                       
        return (y, z)

    def world_to_pixel(self, y_w: float, z_w: float) -> tuple:
        """World (metres) → pixel (Qt coords)."""
        ox, oy = self._origin_px
        px = ox + y_w * self._scale
        py = oy - z_w * self._scale                        
        return (px, py)

    def snap(self, y_w: float, z_w: float) -> tuple:
        """
        If snap is enabled, round world coords to the nearest grid point.
        Always returns a (y, z) tuple in metres.
        """
        if not self.snap_enabled:
            return (y_w, z_w)
        s = self._grid_spacing_m
        return (
            round(y_w / s) * s,
            round(z_w / s) * s,
        )

    def pixel_to_snapped_world(self, px: float, py: float) -> tuple:
        """Convenience: pixel → world → snap. Use this in mouseMoveEvent."""
        y, z = self.pixel_to_world(px, py)
        return self.snap(y, z)

    def grid_lines(self, viewport_w: int, viewport_h: int) -> dict:
        """
        Returns pixel positions of all visible grid lines.

        Returns
        -------
        dict with:
            'vertical'   : list of x pixel positions
            'horizontal' : list of y pixel positions
            'spacing_px' : grid spacing in pixels (for line opacity scaling)
            'origin_px'  : (ox, oy) pixel position of world origin
        """
        s = self._grid_spacing_m

        y_min, z_max = self.pixel_to_world(0, 0)
        y_max, z_min = self.pixel_to_world(viewport_w, viewport_h)

        i_y_start = math.floor(y_min / s)
        i_y_end   = math.ceil(y_max / s)
        i_z_start = math.floor(z_min / s)
        i_z_end   = math.ceil(z_max / s)

        verticals   = []
        horizontals = []

        for i in range(i_y_start, i_y_end + 1):
            px, _ = self.world_to_pixel(i * s, 0)
            verticals.append(px)

        for i in range(i_z_start, i_z_end + 1):
            _, py = self.world_to_pixel(0, i * s)
            horizontals.append(py)

        return {
            'vertical':   verticals,
            'horizontal': horizontals,
            'spacing_px': s * self._scale,
            'origin_px':  self._origin_px,
        }

    def format_coords(self, y_w: float, z_w: float) -> str:
        """
        Format a world coordinate pair for the status bar.
        Converts to display units and appends the unit name.

        Example:  "X = 125.00 mm   Y = 300.00 mm"
                  "X =   0.42 m    Y =   0.75 m"
        """
        scale = unit_registry.length_scale
        unit  = unit_registry.length_unit_name
        y_d = y_w * scale
        z_d = z_w * scale
        return f"X = {y_d:8.3f} {unit}    Y = {z_d:8.3f} {unit}"

    def format_snap_state(self) -> str:
        """Short label for the snap toggle button / status indicator."""
        scale = unit_registry.length_scale
        unit  = unit_registry.length_unit_name
        step_d = self._grid_spacing_m * scale
        state = "ON" if self.snap_enabled else "OFF"
        return f"Snap: {state}  ({step_d:g} {unit})"

    def set_grid_step_display(self, step_display: float):
        """
        Manually set grid spacing in DISPLAY units.
        E.g. step_display=50 when unit is mm → 0.05 m internally.
        """
        self._display_step = step_display
        self._grid_spacing_m = step_display / unit_registry.length_scale

    @property
    def grid_spacing_display(self) -> float:
        """Current grid spacing in display units."""
        return self._grid_spacing_m * unit_registry.length_scale

    @property
    def scale(self) -> float:
        """Current zoom level in px/metre."""
        return self._scale

    def _auto_pick_grid_step(self):
        """
        Pick the smallest display-unit step that keeps grid lines
        at least 20 px apart. Called after every zoom change.
        """
        scale = unit_registry.length_scale
        target_px = 30.0                                                       

        for step_d in _DISPLAY_STEPS:
            step_m = step_d / scale
            if step_m * self._scale >= target_px:
                self._display_step   = step_d
                self._grid_spacing_m = step_m
                return

        self._display_step   = _DISPLAY_STEPS[-1]
        self._grid_spacing_m = _DISPLAY_STEPS[-1] / scale
