import math

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QWidget, QGroupBox, QFormLayout, QLabel,
    QLineEdit, QComboBox, QPushButton, QGridLayout,
    QFrame, QSizePolicy, QMessageBox, QDoubleSpinBox,
    QColorDialog,
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui  import QFont, QColor

from core.units    import unit_registry
from core.properties import ArbitrarySection

from app.section_designer.toolbar_widget  import ToolbarWidget
from app.section_designer.drawing_canvas  import DrawingCanvas, DrawMode
from app.section_designer.section_analyzer import SectionAnalyzer

class SectionDesignerDialog(QDialog):
    """
    Parameters
    ----------
    model          : StructuralModel  — needed to populate material list
    section_data   : ArbitrarySection | None
                     Pass an existing section to re-open it for editing.
    parent         : QWidget | None
    """

    def __init__(self, model, section_data=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Section Designer")
        self.resize(1000, 680)
        self.setMinimumSize(800, 560)

        self.model        = model
        self.section_data = section_data

        self._computed_props: dict | None = None
        self._color = (0.259, 0.110, 0.749, 1.0)                  
        self._modifiers = {
            "A": 1.0, "As2": 1.0, "As3": 1.0, "J": 1.0,
            "I2": 1.0, "I3": 1.0, "Mass": 1.0, "Weight": 1.0
        }

        self._build_ui()
        self._connect_signals()
        self._update_color_button()                                    

        if section_data is not None:
            self._load_existing(section_data)
        else:
            self._set_default_name()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.toolbar = ToolbarWidget(self)
        self.toolbar.setFixedHeight(40)
        root.addWidget(self.toolbar)

        root.addWidget(self._h_line())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(4)

        splitter.addWidget(self._build_options_panel())
        self.canvas = DrawingCanvas(self)
        splitter.addWidget(self.canvas)
        splitter.setStretchFactor(0, 0)                        
        splitter.setStretchFactor(1, 1)                   
        splitter.setSizes([220, 780])

        root.addWidget(splitter, stretch=1)

        root.addWidget(self._h_line())

        root.addWidget(self._build_props_panel())

        root.addWidget(self._h_line())

        root.addWidget(self._build_bottom_bar())

    def _build_options_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(220)
        panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)

        grp_id = QGroupBox("Section identity")
        form_id = QFormLayout(grp_id)
        form_id.setSpacing(6)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. ARB1")
        form_id.addRow("Name:", self.name_edit)

        self.mat_combo = QComboBox()
        for m in self.model.materials:
            self.mat_combo.addItem(m)
        form_id.addRow("Material:", self.mat_combo)

        layout.addWidget(grp_id)

        grp_dt = QGroupBox("Design type")
        form_dt = QFormLayout(grp_dt)
        form_dt.setSpacing(6)

        self.design_combo = QComboBox()
        self.design_combo.addItems([
            "No check / no design",
            "Steel frame design",
            "Concrete column — check",
            "Concrete column — design",
        ])
        form_dt.addRow("Type:", self.design_combo)

        layout.addWidget(grp_dt)

        grp_hint = QGroupBox("Drawing")
        hint_layout = QVBoxLayout(grp_hint)
        hint_layout.setSpacing(4)

        hints = [
            "Left-click  — place vertex",
            "Right-click — close polygon",
            "Dbl-click   — close polygon",
            "Esc / ⌫    — undo last vertex",
            "Wheel       — zoom",
            "Middle drag — pan",
            "Space drag  — pan",
        ]
        for h in hints:
            lbl = QLabel(h)
            lbl.setStyleSheet("color: #666; font-size: 10px;")
            lbl.setWordWrap(True)
            hint_layout.addWidget(lbl)

        layout.addWidget(grp_hint)

        grp_style = QGroupBox("Appearance & Modifiers")
        style_layout = QVBoxLayout(grp_style)
        style_layout.setSpacing(6)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color:"))
        self.btn_color = QPushButton()
        self.btn_color.setFixedSize(50, 22)
        self.btn_color.clicked.connect(self._pick_color)
        color_row.addWidget(self.btn_color)
        color_row.addStretch()
        style_layout.addLayout(color_row)

        self.btn_mods = QPushButton("Property Modifiers…")
        self.btn_mods.setFixedHeight(24)
        self.btn_mods.clicked.connect(self._open_modifiers)
        style_layout.addWidget(self.btn_mods)

        layout.addWidget(grp_style)
        layout.addStretch()

        self.vertex_lbl = QLabel("Vertices: 0")
        self.vertex_lbl.setStyleSheet("color: #555; font-size: 11px;")
        layout.addWidget(self.vertex_lbl)

        return panel

    def _build_props_panel(self) -> QGroupBox:
        grp = QGroupBox("Section properties  (after running analysis)")
        grp.setFixedHeight(110)
        grid = QGridLayout(grp)
        grid.setSpacing(6)
        grid.setContentsMargins(8, 6, 8, 6)

        u = unit_registry.length_unit_name

        self._prop_fields: dict[str, QLineEdit] = {}

        fields = [
            ("A",    f"Area ({u}²)"),
            ("I33",  f"I33 ({u}⁴)"),
            ("I22",  f"I22 ({u}⁴)"),
            ("J",    f"J ({u}⁴)"),
            ("S33",  f"S33 ({u}³)"),
            ("S22",  f"S22 ({u}³)"),
            ("r33",  f"r33 ({u})"),
            ("r22",  f"r22 ({u})"),
            ("y_c",  f"ȳ ({u})"),
            ("z_c",  f"z̄ ({u})"),
        ]

        for col, (key, label) in enumerate(fields):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            lbl.setStyleSheet("font-size: 10px; color: #555;")
            le = QLineEdit("—")
            le.setReadOnly(True)
            le.setFixedWidth(90)
            le.setStyleSheet("background:#f5f5f5; font-size: 10px;")
            le.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(lbl, 0, col * 2)
            grid.addWidget(le,  1, col * 2)
            self._prop_fields[key] = le

        return grp

    def _build_bottom_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(40)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        self.coord_lbl = QLabel("X =      —        Y =      —")
        self.coord_lbl.setStyleSheet("font-family: monospace; font-size: 11px; color: #444;")
        self.coord_lbl.setFixedWidth(280)
        layout.addWidget(self.coord_lbl)

        self.snap_lbl = QLabel("Snap: ON")
        self.snap_lbl.setStyleSheet("font-size: 11px; color: #555;")
        layout.addWidget(self.snap_lbl)

        layout.addStretch()

        self.btn_run = QPushButton("Run Analysis")
        self.btn_run.setEnabled(False)
        self.btn_run.setFixedHeight(28)
        self.btn_run.setStyleSheet(
            "QPushButton { background: #3a7fc1; color: white; border-radius: 4px; padding: 0 12px; }"
            "QPushButton:disabled { background: #aaa; }"
            "QPushButton:hover:!disabled { background: #2a6aaa; }"
        )
        self.btn_run.clicked.connect(self._run_analysis)

        self.btn_accept = QPushButton("Accept")
        self.btn_accept.setEnabled(False)
        self.btn_accept.setFixedHeight(28)
        self.btn_accept.setDefault(True)
        self.btn_accept.setStyleSheet(
            "QPushButton { background: #ffffff; color: black; border-radius: 4px; padding: 0 12px; }"
            "QPushButton:disabled { background: #aaa; }"
            "QPushButton:hover:!disabled { background:#ffffff; }"
        )
        self.btn_accept.clicked.connect(self._on_accept)

        btn_cancel = QPushButton("Cancel")
        btn_cancel.setFixedHeight(28)
        btn_cancel.clicked.connect(self.reject)

        for btn in (self.btn_run, self.btn_accept, btn_cancel):
            layout.addWidget(btn)

        return bar

    @staticmethod
    def _h_line() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setFixedHeight(1)
        return line

    def _connect_signals(self):
                          
        self.toolbar.mode_changed.connect(self.canvas.set_mode)
        self.toolbar.snap_toggled.connect(self._on_snap_toggled)
        self.toolbar.grid_step_changed.connect(self.canvas.set_grid_step)
        self.toolbar.zoom_fit_requested.connect(self.canvas.zoom_to_fit)
        self.toolbar.reset_requested.connect(self._on_reset)

        self.canvas.coords_changed.connect(self._on_coords_changed)
        self.canvas.polygon_changed.connect(self._on_polygon_changed)
        self.canvas.polygon_closed.connect(self._on_polygon_closed)

        self.canvas.set_grid_step(self.toolbar.current_grid_step)

    @pyqtSlot(str)
    def _on_coords_changed(self, text: str):
        self.coord_lbl.setText(text)

    @pyqtSlot(list)
    def _on_polygon_changed(self, vertices: list):
        n = len(vertices)
        self.vertex_lbl.setText(f"Vertices: {n}")
                                                
        can_run = self.canvas.is_closed
        self.btn_run.setEnabled(can_run)
        if not can_run:
            self.btn_accept.setEnabled(False)
            self._computed_props = None

    @pyqtSlot()
    def _on_polygon_closed(self):
        self.btn_run.setEnabled(True)

    @pyqtSlot(bool)
    def _on_snap_toggled(self, enabled: bool):
        self.canvas.set_snap(enabled)
        self.snap_lbl.setText(
            f"Snap: ON  ({self.canvas.snap_grid.format_snap_state().split('(')[-1].rstrip(')')}"
            if enabled else "Snap: OFF"
        )

    @pyqtSlot()
    def _on_reset(self):
        reply = QMessageBox.question(
            self, "Clear canvas",
            "Clear all vertices and start over?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.canvas.reset()
            self._computed_props = None
            self.btn_run.setEnabled(False)
            self.btn_accept.setEnabled(False)
            self._clear_prop_fields()

    @pyqtSlot()
    def _run_analysis(self):
        verts = self.canvas.get_vertices()
        if len(verts) < 3:
            QMessageBox.warning(self, "Too few vertices",
                                "Need at least 3 vertices to analyse a section.")
            return

        props = SectionAnalyzer.compute(verts)

        if props['A'] < 1e-12:
            QMessageBox.warning(self, "Degenerate section",
                                "Computed area is effectively zero. "
                                "Check that vertices form a valid polygon.")
            return

        self._computed_props = props
        self._update_prop_fields(props)
        self.canvas.set_centroid(props['y_c'], props['z_c'])
        self.btn_accept.setEnabled(True)

    def _update_prop_fields(self, props: dict):
        scale  = unit_registry.length_scale
        s2, s3, s4 = scale**2, scale**3, scale**4

        conversions = {
            'A':   s2,   'I33': s4,  'I22': s4,
            'J':   s4,   'S33': s3,  'S22': s3,
            'r33': scale, 'r22': scale,
            'y_c': scale, 'z_c': scale,
        }

        for key, le in self._prop_fields.items():
            raw = props.get(key, 0.0)
            val = raw * conversions.get(key, 1.0)
            if abs(val) < 1e-3 and val != 0.0:
                le.setText(f"{val:.4e}")
            else:
                le.setText(f"{val:.5g}")

    def _clear_prop_fields(self):
        for le in self._prop_fields.values():
            le.setText("—")

    @pyqtSlot()
    def _on_accept(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Name required", "Please enter a section name.")
            return

        if not self._computed_props:
            QMessageBox.warning(self, "Run analysis first",
                                "Please run the section analysis before accepting.")
            return

        mat_name = self.mat_combo.currentText()
        if not mat_name or mat_name not in self.model.materials:
            QMessageBox.critical(self, "No material", "Please select a valid material.")
            return

        mat   = self.model.materials[mat_name]
        verts = self.canvas.get_vertices()                        

        p = self._computed_props
        props_dict = {
            'A':   p['A'],
            'J':   p['J'],
            'I33': p['I33'],
            'I22': p['I22'],
            'As2': p['Asy'],                                          
            'As3': p['Asz'],                                          
        }

        y_c, z_c = p['y_c'], p['z_c']
        shifted_verts = [(y - y_c, z - z_c) for (y, z) in verts]
        section = ArbitrarySection(name, mat, shifted_verts, props_dict)
        section.color = self._color
        section.modifiers = self._modifiers.copy()

        self.result_section = section

        self.accept()

    def _load_existing(self, sec: ArbitrarySection):
        """Pre-populate the dialog from an existing ArbitrarySection."""
        self.name_edit.setText(sec.name)

        idx = self.mat_combo.findText(sec.material.name)
        if idx >= 0:
            self.mat_combo.setCurrentIndex(idx)

        if hasattr(sec, 'color') and sec.color:
            self._color = sec.color
            self._update_color_button()
        if hasattr(sec, 'modifiers') and sec.modifiers:
            self._modifiers = sec.modifiers.copy()

        if sec.vertices:
            self.canvas.set_vertices(sec.vertices)
            self.canvas.zoom_to_fit()

            self._computed_props = {
                'A':   sec.A,   'J':   sec.J,
                'I33': sec.I33, 'I22': sec.I22,
                'Asy': sec.Asy, 'Asz': sec.Asz,
                'S33': sec.S33, 'S22': sec.S22,
                'r33': sec.r33, 'r22': sec.r22,
                'y_c': 0.0,     'z_c': 0.0,
            }
            self._update_prop_fields(self._computed_props)
            self.btn_run.setEnabled(True)
            self.btn_accept.setEnabled(True)

    def _set_default_name(self):
        base = "ARB"
        idx  = 1
        while f"{base}{idx}" in self.model.sections:
            idx += 1
        self.name_edit.setText(f"{base}{idx}")

    def _pick_color(self):
        r, g, b = [int(c * 255) for c in self._color[:3]]
        c = QColorDialog.getColor(QColor(r, g, b), self, "Section Color")
        if c.isValid():
            self._color = (c.redF(), c.greenF(), c.blueF(), 1.0)
            self._update_color_button()

    def _update_color_button(self):
        r, g, b = [int(c * 255) for c in self._color[:3]]
        self.btn_color.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); border: 1px solid gray;"
        )

    def _open_modifiers(self):
        dlg = _ModifiersDialog(self._modifiers, self)
        if dlg.exec():
            self._modifiers = dlg.modifiers

class _ModifiersDialog(QDialog):
    """Lightweight stiffness modifier dialog, embedded in the Section Designer."""
    def __init__(self, current: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Property / Stiffness Modifiers")
        self.resize(320, 300)
        self.modifiers = current.copy()

        layout = QVBoxLayout(self)
        grp = QGroupBox("Analysis Factors (Multipliers)")
        form = QFormLayout(grp)

        labels = {
            "A":   "Cross-section Area",
            "As2": "Shear Area (Local 2)",
            "As3": "Shear Area (Local 3)",
            "J":   "Torsional Constant",
            "I2":  "Moment of Inertia (Local 2)",
            "I3":  "Moment of Inertia (Local 3)",
            "Mass":   "Mass",
            "Weight": "Weight",
        }
        self._inputs = {}
        for key, text in labels.items():
            sb = QDoubleSpinBox()
            sb.setRange(0.0001, 1000.0)
            sb.setSingleStep(0.1)
            sb.setDecimals(4)
            sb.setValue(self.modifiers.get(key, 1.0))
            form.addRow(text, sb)
            self._inputs[key] = sb

        layout.addWidget(grp)

        btns = QHBoxLayout()
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self._save)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)
        layout.addLayout(btns)

    def _save(self):
        for key, sb in self._inputs.items():
            self.modifiers[key] = sb.value()
        self.accept()
