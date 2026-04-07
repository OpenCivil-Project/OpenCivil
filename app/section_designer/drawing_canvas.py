"""
drawing_canvas.py
-----------------
The interactive 2-D drawing canvas for the Section Designer.

Responsibilities
----------------
- Draw a SAP2000-style grid with local 2-3 axes at the origin
- Let the user click to place polygon vertices (DRAW mode)
- Show a live rubber-band edge from the last placed vertex to the cursor
- Close the polygon when the user clicks near the first vertex or double-clicks
- Pan (middle-mouse drag or Space+drag) and zoom (wheel)
- Show the computed centroid after analysis
- Emit signals so the parent dialog can update the status bar and buttons

Coordinate convention
---------------------
World space  : (y, z) in base SI metres — same as get_shape_coords().
               y grows rightward (local-2 / horizontal)
               z grows upward    (local-3 / vertical)
Qt pixel space: x grows right, y grows DOWN → z is flipped when converting.

All vertices stored internally are in base SI metres.
The SnapGrid handles all pixel ↔ world conversion and snapping.
"""

from enum import Enum, auto

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore    import Qt, pyqtSignal, QPoint, QPointF
from PyQt6.QtGui     import (
    QPainter, QColor, QPen, QBrush, QPainterPath,
    QPolygonF, QCursor,
)

from app.section_designer.snap_grid import SnapGrid

class DrawMode(Enum):
    DRAW   = auto()                            
    SELECT = auto()                                        
    PAN    = auto()                

_BG          = QColor(255, 255, 255)                           
_GRID_MINOR  = QColor(220, 220, 220)                         
_GRID_MAJOR  = QColor(190, 190, 190)                             
_AXIS_Y      = QColor( 30, 160,  30)                                           
_AXIS_Z      = QColor(200,  30,  30)                                         
_AXIS_LABEL  = QColor(100, 100, 100)

_POLY_FILL_OPEN   = QColor( 80, 130, 220,  45)                                 
_POLY_FILL_CLOSED = QColor( 80, 130, 220,  70)                         
_POLY_EDGE        = QColor( 30,  80, 200)                          
_POLY_EDGE_W      = 2.0

_VERTEX_FILL      = QColor( 30,  80, 200)
_VERTEX_FIRST     = QColor(220,  30,  30)                                      
_VERTEX_R         = 4                                                        
_VERTEX_R_FIRST   = 6                                                  

_PREVIEW_EDGE     = QColor(140, 140, 140)                           
_PREVIEW_SNAP     = QColor( 30,  80, 200, 160)                    

_CENTROID_COL     = QColor(220,  30,  30)                          
_CENTROID_R       = 5

_CLOSE_THRESHOLD  = 12                                                        

class DrawingCanvas(QWidget):
    """
    Interactive polygon-drawing canvas for the Section Designer.

    Signals
    -------
    coords_changed(str)      — formatted coordinate string for the status bar
    polygon_changed(list)    — emitted whenever vertices list changes;
                               payload is list of (y,z) world tuples
    polygon_closed()         — emitted once when the polygon is completed
    """

    coords_changed  = pyqtSignal(str)
    polygon_changed = pyqtSignal(list)
    polygon_closed  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMinimumSize(400, 400)

        self._grid = SnapGrid(snap_enabled=True)

        self._mode: DrawMode   = DrawMode.DRAW
        self._vertices: list   = []                                    
        self._is_closed: bool  = False
        self._preview: tuple   = (0.0, 0.0)                                       
        self._near_close: bool = False                                            

        self._centroid: tuple | None = None                                  

        self._panning:      bool   = False
        self._pan_last:     QPoint = QPoint()
        self._space_held:   bool   = False

        self._grid.set_scale(200.0)

    def set_mode(self, mode: DrawMode):
        """Switch tool mode. Called by the toolbar."""
        self._mode = mode
        if mode == DrawMode.PAN:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))

    def set_snap(self, enabled: bool):
        """Toggle snap-to-grid."""
        self._grid.snap_enabled = enabled
        self.update()

    def set_grid_step(self, step_display: float):
        """Set grid spacing in display units."""
        self._grid.set_grid_step_display(step_display)
        self.update()

    @property
    def snap_grid(self) -> SnapGrid:
        return self._grid

    def get_vertices(self) -> list:
        """Return a copy of vertices as (y, z) tuples in base SI metres."""
        return list(self._vertices)

    def set_vertices(self, vertices: list):
        """
        Load an existing polygon (e.g. re-opening an ArbitrarySection).
        Vertices must be (y, z) tuples in base SI metres.
        """
        self._vertices  = list(vertices)
        self._is_closed = len(vertices) >= 3
        self._centroid  = None
        self.update()
        self.polygon_changed.emit(list(self._vertices))

    def reset(self):
        """Clear all vertices and centroid, return to empty canvas."""
        self._vertices  = []
        self._is_closed = False
        self._centroid  = None
        self._near_close = False
        self.update()
        self.polygon_changed.emit([])

    def set_centroid(self, y_c: float, z_c: float):
        """Show the centroid marker after running analysis."""
        self._centroid = (y_c, z_c)
        self.update()

    def clear_centroid(self):
        self._centroid = None
        self.update()

    @property
    def is_closed(self) -> bool:
        return self._is_closed

    @property
    def vertex_count(self) -> int:
        return len(self._vertices)

    def zoom_to_fit(self):
        """
        Fit all vertices into the viewport with 20 % padding.
        Falls back to default view if no vertices.
        """
        if not self._vertices:
            self._grid.set_origin(self.width() / 2, self.height() / 2)
            self._grid.set_scale(200.0)
            self.update()
            return

        ys = [v[0] for v in self._vertices]
        zs = [v[1] for v in self._vertices]
        y_span = max(ys) - min(ys) or 1.0
        z_span = max(zs) - min(zs) or 1.0

        pad = 0.20
        scale_y = self.width()  / (y_span * (1 + 2 * pad))
        scale_z = self.height() / (z_span * (1 + 2 * pad))
        new_scale = min(scale_y, scale_z)
        self._grid.set_scale(new_scale)

        y_mid = (max(ys) + min(ys)) / 2
        z_mid = (max(zs) + min(zs)) / 2
        cx, cy = self._grid.world_to_pixel(y_mid, z_mid)
        dx = self.width()  / 2 - cx
        dy = self.height() / 2 - cy
        self._grid.pan(dx, dy)
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
                                                      
        self._grid.set_origin(self.width() / 2, self.height() / 2)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        gl = self._grid.grid_lines(w, h)

        p.fillRect(0, 0, w, h, _BG)

        self._draw_grid(p, gl)

        self._draw_axes(p, gl['origin_px'])

        if self._vertices:
            self._draw_polygon(p)

        if self._mode == DrawMode.DRAW and self._vertices and not self._is_closed:
            self._draw_preview_edge(p)

        if self._centroid is not None:
            self._draw_centroid(p)

        if self._mode == DrawMode.DRAW and not self._is_closed:
            self._draw_snap_cursor(p)

        p.end()

    def _draw_grid(self, p: QPainter, gl: dict):
        spacing = gl['spacing_px']
        ox, oy  = gl['origin_px']

        for i, x in enumerate(gl['vertical']):
                                                                            
            idx = round((x - ox) / spacing) if spacing > 0 else 0
            col = _GRID_MAJOR if idx % 5 == 0 else _GRID_MINOR
            p.setPen(QPen(col, 0.5))
            p.drawLine(int(x), 0, int(x), self.height())

        for i, y in enumerate(gl['horizontal']):
            idx = round((y - oy) / spacing) if spacing > 0 else 0
            col = _GRID_MAJOR if idx % 5 == 0 else _GRID_MINOR
            p.setPen(QPen(col, 0.5))
            p.drawLine(0, int(y), self.width(), int(y))

    def _draw_axes(self, p: QPainter, origin_px: tuple):
        ox, oy = origin_px
        w, h   = self.width(), self.height()

        pen_y = QPen(_AXIS_Y, 1.5)
        p.setPen(pen_y)
        p.drawLine(0, int(oy), w, int(oy))

        pen_z = QPen(_AXIS_Z, 1.5)
        p.setPen(pen_z)
        p.drawLine(int(ox), 0, int(ox), h)

        lbl_font = p.font()
        lbl_font.setPointSize(9)
        p.setFont(lbl_font)

        if 0 < ox < w:
                                                               
            p.setPen(QPen(_AXIS_Z, 1))
            p.drawText(int(ox) + 4, 14, "3")

        if 0 < oy < h:
                                                 
            p.setPen(QPen(_AXIS_Y, 1))
            p.drawText(w - 14, int(oy) - 4, "2")

    def _draw_polygon(self, p: QPainter):
        verts = self._vertices
        if not verts:
            return

        pts = [QPointF(*self._grid.world_to_pixel(y, z)) for y, z in verts]

        if self._is_closed and len(pts) >= 3:
            poly = QPolygonF(pts)
            p.setBrush(QBrush(_POLY_FILL_CLOSED))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPolygon(poly)

        elif len(pts) >= 3:
                                                         
            preview_px = QPointF(*self._grid.world_to_pixel(*self._preview))
            preview_pts = pts + [preview_px]
            poly = QPolygonF(preview_pts)
            p.setBrush(QBrush(_POLY_FILL_OPEN))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPolygon(poly)

        edge_pen = QPen(_POLY_EDGE, _POLY_EDGE_W)
        edge_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        edge_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(edge_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        for i in range(len(pts) - 1):
            p.drawLine(pts[i], pts[i + 1])
        if self._is_closed:
            p.drawLine(pts[-1], pts[0])

        p.setBrush(QBrush(_VERTEX_FILL))
        p.setPen(Qt.PenStyle.NoPen)
        for i, pt in enumerate(pts):
            if i == 0:
                                                                              
                col = _VERTEX_FIRST
                r   = _VERTEX_R_FIRST
                p.setBrush(QBrush(col))
                p.drawEllipse(pt, r, r)
                p.setBrush(QBrush(_VERTEX_FILL))
            else:
                p.drawEllipse(pt, _VERTEX_R, _VERTEX_R)

    def _draw_preview_edge(self, p: QPainter):
        if not self._vertices:
            return
        last_px  = QPointF(*self._grid.world_to_pixel(*self._vertices[-1]))
        mouse_px = QPointF(*self._grid.world_to_pixel(*self._preview))

        pen = QPen(_PREVIEW_EDGE, 1.2)
        pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawLine(last_px, mouse_px)

        if len(self._vertices) >= 2 and self._near_close:
            first_px = QPointF(*self._grid.world_to_pixel(*self._vertices[0]))
            close_pen = QPen(_VERTEX_FIRST, 1.0)
            close_pen.setStyle(Qt.PenStyle.DotLine)
            p.setPen(close_pen)
            p.drawLine(mouse_px, first_px)

    def _draw_centroid(self, p: QPainter):
        yc, zc = self._centroid
        cx, cy = self._grid.world_to_pixel(yc, zc)
        r = _CENTROID_R

        pen = QPen(_CENTROID_COL, 2)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        p.drawLine(int(cx) - r * 3, int(cy), int(cx) + r * 3, int(cy))
        p.drawLine(int(cx), int(cy) - r * 3, int(cx), int(cy) + r * 3)

        p.drawEllipse(QPointF(cx, cy), float(r), float(r))

    def _draw_snap_cursor(self, p: QPainter):
        """Small crosshair at snapped cursor position."""
        mx, my = self._grid.world_to_pixel(*self._preview)
        pen = QPen(_PREVIEW_SNAP, 1)
        p.setPen(pen)
        sz = 6
        p.drawLine(int(mx) - sz, int(my), int(mx) + sz, int(my))
        p.drawLine(int(mx), int(my) - sz, int(mx), int(my) + sz)

    def mousePressEvent(self, event):
        btn = event.button()
        pos = event.position()

        if btn == Qt.MouseButton.MiddleButton or (
            btn == Qt.MouseButton.LeftButton and self._space_held
        ):
            self._panning  = True
            self._pan_last = event.position().toPoint()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return

        if btn == Qt.MouseButton.LeftButton:
            if self._mode == DrawMode.PAN:
                self._panning  = True
                self._pan_last = event.position().toPoint()
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                return

            if self._mode == DrawMode.DRAW and not self._is_closed:
                self._place_vertex(pos.x(), pos.y())

        elif btn == Qt.MouseButton.RightButton:
                                                             
            if self._mode == DrawMode.DRAW and len(self._vertices) >= 3 and not self._is_closed:
                self._close_polygon()

    def mouseMoveEvent(self, event):
        pos = event.position()

        if self._panning:
            cur = event.position().toPoint()
            dx  = cur.x() - self._pan_last.x()
            dy  = cur.y() - self._pan_last.y()
            self._grid.pan(dx, dy)
            self._pan_last = cur
            self.update()
            return

        y, z = self._grid.pixel_to_snapped_world(pos.x(), pos.y())
        self._preview = (y, z)

        self._near_close = False
        if self._vertices and not self._is_closed and len(self._vertices) >= 2:
            v0_px = self._grid.world_to_pixel(*self._vertices[0])
            dist  = ((pos.x() - v0_px[0])**2 + (pos.y() - v0_px[1])**2) ** 0.5
            self._near_close = dist < _CLOSE_THRESHOLD

        self.coords_changed.emit(self._grid.format_coords(y, z))
        self.update()

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            cur = Qt.CursorShape.OpenHandCursor if self._mode == DrawMode.PAN else Qt.CursorShape.CrossCursor
            self.setCursor(QCursor(cur))

    def mouseDoubleClickEvent(self, event):
        if (self._mode == DrawMode.DRAW
                and event.button() == Qt.MouseButton.LeftButton
                and len(self._vertices) >= 3
                and not self._is_closed):
            self._close_polygon()

    def wheelEvent(self, event):
        delta   = event.angleDelta().y()
        factor  = 1.15 if delta > 0 else 1.0 / 1.15
        pos     = event.position()

        y_before, z_before = self._grid.pixel_to_world(pos.x(), pos.y())
        self._grid.set_scale(self._grid.scale * factor)
        px_after, py_after = self._grid.world_to_pixel(y_before, z_before)
        self._grid.pan(pos.x() - px_after, pos.y() - py_after)
        self.update()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Space:
            self._space_held = True
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        elif key == Qt.Key.Key_Escape:
                                         
            if self._vertices and not self._is_closed:
                self._vertices.pop()
                self.polygon_changed.emit(list(self._vertices))
                self.update()
        elif key == Qt.Key.Key_Delete or key == Qt.Key.Key_Backspace:
            if self._vertices and not self._is_closed:
                self._vertices.pop()
                self.polygon_changed.emit(list(self._vertices))
                self.update()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self._space_held = False
            mode_cursor = (Qt.CursorShape.OpenHandCursor
                           if self._mode == DrawMode.PAN
                           else Qt.CursorShape.CrossCursor)
            self.setCursor(QCursor(mode_cursor))

    def _place_vertex(self, px: float, py: float):
        """Add a vertex at the snapped world position of pixel (px, py)."""
        y, z = self._grid.pixel_to_snapped_world(px, py)

        if (len(self._vertices) >= 3 and self._near_close):
            self._close_polygon()
            return

        self._vertices.append((y, z))
        self._centroid = None                                           
        self.polygon_changed.emit(list(self._vertices))
        self.update()

    def _close_polygon(self):
        """Mark the polygon as closed and emit the closed signal."""
        if len(self._vertices) < 3:
            return
        self._is_closed = True
        self._centroid  = None
        self.update()
        self.polygon_changed.emit(list(self._vertices))
        self.polygon_closed.emit()
