"""
section_designer_commands.py
----------------------------
QUndoCommand subclasses for the Section Designer canvas.

Same pattern as the project's main commands.py — each command stores its
own old/new state and manipulates the canvas directly via its semi-private
attributes.  Nothing here touches the structural model or the main window.

Commands
--------
CmdAddVertex    — place one vertex while drawing
CmdClosePolygon — seal the open polygon
CmdMoveVertex   — drag an existing vertex to a new position
CmdSetVertices  — replace the entire vertex list (shape generators)
"""

from PyQt6.QtGui import QUndoCommand

class CmdAddVertex(QUndoCommand):
    """Push one vertex onto the in-progress polygon."""

    def __init__(self, canvas, vertex: tuple, description: str = "Add Vertex"):
        super().__init__(description)
        self._canvas = canvas
        self._vertex = vertex

    def redo(self):
        self._canvas._vertices.append(self._vertex)
        self._canvas._centroid        = None
        self._canvas._principal_angle = None
        self._canvas.polygon_changed.emit(list(self._canvas._vertices))
        self._canvas.update()

    def undo(self):
        if self._canvas._vertices:
            self._canvas._vertices.pop()
            self._canvas._is_closed       = False
            self._canvas._centroid        = None
            self._canvas._principal_angle = None
            self._canvas.polygon_changed.emit(list(self._canvas._vertices))
            self._canvas.update()

class CmdClosePolygon(QUndoCommand):
    """Seal the open polygon into a closed shape."""

    def __init__(self, canvas, description: str = "Close Polygon"):
        super().__init__(description)
        self._canvas = canvas

    def redo(self):
        self._canvas._is_closed       = True
        self._canvas._centroid        = None
        self._canvas._principal_angle = None
        self._canvas.polygon_changed.emit(list(self._canvas._vertices))
        self._canvas.polygon_closed.emit()
        self._canvas.update()

    def undo(self):
        self._canvas._is_closed       = False
        self._canvas._centroid        = None
        self._canvas._principal_angle = None
        self._canvas.polygon_changed.emit(list(self._canvas._vertices))
        self._canvas.update()

class CmdMoveVertex(QUndoCommand):
    """Record a vertex drag from old_pos → new_pos."""

    def __init__(self, canvas, index: int,
                 old_pos: tuple, new_pos: tuple,
                 description: str = "Move Vertex"):
        super().__init__(description)
        self._canvas  = canvas
        self._index   = index
        self._old_pos = old_pos
        self._new_pos = new_pos

    def redo(self):
        self._canvas._vertices[self._index] = self._new_pos
        self._canvas._centroid              = None
        self._canvas._principal_angle       = None
        self._canvas.polygon_changed.emit(list(self._canvas._vertices))
        self._canvas.update()

    def undo(self):
        self._canvas._vertices[self._index] = self._old_pos
        self._canvas._centroid              = None
        self._canvas._principal_angle       = None
        self._canvas.polygon_changed.emit(list(self._canvas._vertices))
        self._canvas.update()

class CmdSetVertices(QUndoCommand):
    """
    Replace the entire vertex list in one shot.
    Used by shape generators (rectangle, circle, I-section …).
    Polygon is automatically marked closed when ≥ 3 vertices are supplied.
    """

    def __init__(self, canvas, old_vertices: list, new_vertices: list,
                 description: str = "Set Shape"):
        super().__init__(description)
        self._canvas = canvas
        self._old    = list(old_vertices)
        self._new    = list(new_vertices)

    def redo(self):
        self._canvas._vertices        = list(self._new)
        self._canvas._is_closed       = len(self._new) >= 3
        self._canvas._centroid        = None
        self._canvas._principal_angle = None
        self._canvas.polygon_changed.emit(list(self._canvas._vertices))
        if self._canvas._is_closed:
            self._canvas.polygon_closed.emit()
        self._canvas.update()

    def undo(self):
        self._canvas._vertices        = list(self._old)
        self._canvas._is_closed       = len(self._old) >= 3
        self._canvas._centroid        = None
        self._canvas._principal_angle = None
        self._canvas.polygon_changed.emit(list(self._canvas._vertices))
        self._canvas.update()
