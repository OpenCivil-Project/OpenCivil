from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QToolButton, QButtonGroup,
    QFrame, QLabel, QComboBox, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui  import QIcon, QFont

from app.section_designer.drawing_canvas import DrawMode
from core.units import unit_registry

class ToolbarWidget(QWidget):
    """
    Signals
    -------
    mode_changed(DrawMode)   — user switched tool
    snap_toggled(bool)       — snap on/off
    grid_step_changed(float) — new grid spacing in display units
    zoom_fit_requested()     — zoom-to-fit button clicked
    reset_requested()        — clear canvas button clicked
    """

    mode_changed       = pyqtSignal(object)                        
    snap_toggled       = pyqtSignal(bool)
    grid_step_changed  = pyqtSignal(float)
    zoom_fit_requested = pyqtSignal()
    reset_requested    = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        self._tool_group = QButtonGroup(self)
        self._tool_group.setExclusive(True)

        self._btn_draw   = self._make_tool_btn("Draw",   "✏",  checkable=True, checked=True)
        self._btn_select = self._make_tool_btn("Select", "↖",  checkable=True)
        self._btn_pan    = self._make_tool_btn("Pan",    "✋",  checkable=True)

        for btn in (self._btn_draw, self._btn_select, self._btn_pan):
            self._tool_group.addButton(btn)
            layout.addWidget(btn)

        self._tool_group.buttonClicked.connect(self._on_tool_clicked)

        layout.addWidget(self._separator())

        self._btn_snap = self._make_tool_btn("Snap", "⊞", checkable=True, checked=True)
        self._btn_snap.setToolTip("Toggle snap to grid  (S)")
        self._btn_snap.clicked.connect(lambda checked: self.snap_toggled.emit(checked))
        layout.addWidget(self._btn_snap)

        layout.addWidget(QLabel("Grid:"))
        self._grid_combo = QComboBox()
        self._grid_combo.setFixedWidth(90)
        self._populate_grid_steps()
        self._grid_combo.currentIndexChanged.connect(self._on_grid_step_changed)
        layout.addWidget(self._grid_combo)

        layout.addWidget(self._separator())

        btn_fit = self._make_tool_btn("Fit", "⊡", checkable=False)
        btn_fit.setToolTip("Zoom to fit polygon")
        btn_fit.clicked.connect(self.zoom_fit_requested.emit)
        layout.addWidget(btn_fit)

        btn_reset = self._make_tool_btn("Clear", "✕", checkable=False)
        btn_reset.setToolTip("Clear all vertices")
        btn_reset.clicked.connect(self.reset_requested.emit)
        layout.addWidget(btn_reset)

        layout.addStretch()

        unit_lbl = QLabel(unit_registry.length_unit_name)
        unit_lbl.setStyleSheet("color: #888; font-size: 11px;")
        unit_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(unit_lbl)

    def _populate_grid_steps(self):
        """Fill the combo with sensible steps for the current display unit."""
        self._grid_combo.blockSignals(True)
        self._grid_combo.clear()

        unit  = unit_registry.length_unit_name
        scale = unit_registry.length_scale                            

        steps_m = [0.001, 0.002, 0.005,
                   0.01,  0.02,  0.05,
                   0.1,   0.2,   0.5,
                   1.0,   2.0]

        self._step_values_display = []
        default_idx = 0

        for i, sm in enumerate(steps_m):
            sd = sm * scale
                                                
            if sd == int(sd):
                label = f"{int(sd)} {unit}"
            else:
                label = f"{sd:g} {unit}"
            self._grid_combo.addItem(label)
            self._step_values_display.append(sd)

            if abs(sm - 0.05) < 1e-9:
                default_idx = i

        self._grid_combo.setCurrentIndex(default_idx)
        self._grid_combo.blockSignals(False)

    def _on_grid_step_changed(self, idx: int):
        if 0 <= idx < len(self._step_values_display):
            self.grid_step_changed.emit(self._step_values_display[idx])

    def _on_tool_clicked(self, btn: QToolButton):
        if btn is self._btn_draw:
            self.mode_changed.emit(DrawMode.DRAW)
        elif btn is self._btn_select:
            self.mode_changed.emit(DrawMode.SELECT)
        elif btn is self._btn_pan:
            self.mode_changed.emit(DrawMode.PAN)

    @staticmethod
    def _make_tool_btn(label: str, icon_char: str,
                       checkable: bool = True,
                       checked: bool   = False) -> QToolButton:
        btn = QToolButton()
        btn.setText(f"{icon_char}  {label}")
        btn.setCheckable(checkable)
        btn.setChecked(checked)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setFixedHeight(28)
        btn.setMinimumWidth(64)
        f = btn.font()
        f.setPointSize(10)
        btn.setFont(f)
        btn.setStyleSheet("""
            QToolButton {
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 2px 8px;
                background: #f5f5f5;
            }
            QToolButton:checked {
                background: #d0e4f7;
                border-color: #3a7fc1;
                color: #1a4a80;
            }
            QToolButton:hover {
                background: #e8f0fb;
                border-color: #3a7fc1;
            }
        """)
        return btn

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        sep.setFixedWidth(2)
        return sep

    @property
    def snap_enabled(self) -> bool:
        return self._btn_snap.isChecked()

    @property
    def current_grid_step(self) -> float:
        idx = self._grid_combo.currentIndex()
        return self._step_values_display[idx] if self._step_values_display else 0.05
