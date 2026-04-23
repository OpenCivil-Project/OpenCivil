"""
SolidResultsViewer — Phase 5d
==============================
Standalone PyQt6 window that renders Tet4/10 solid mesh with von Mises
stress colors using GLMeshItem. Now with real-time deflection scaling
and exact 3D Ray-Casting for Element Selection!
"""

import numpy as np
import sys, os, json, tempfile

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget,
                             QVBoxLayout, QHBoxLayout, QLabel,
                             QComboBox, QPushButton, QFrame, QSizePolicy,
                             QSlider)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QFont

import pyqtgraph.opengl as gl
from pyqtgraph.opengl import GLMeshItem
import pyqtgraph as pg
from PyQt6.QtCore import QEvent

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from solid_color_mapper import stress_to_colors, element_to_node_stresses

class ColorBar(QWidget):
    def __init__(self, vmin=0.0, vmax=1.0, label="Von Mises (Pa)", parent=None):
        super().__init__(parent)
        self.vmin  = vmin
        self.vmax  = vmax
        self.label = label
        self.setFixedWidth(80)
        self.setMinimumHeight(300)

    def update_range(self, vmin, vmax, label=None):
        self.vmin  = vmin
        self.vmax  = vmax
        if label:
            self.label = label
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        bar_x, bar_w, bar_y, bar_h = 10, 12, 10, h - 30

        grad = QLinearGradient(bar_x, bar_y, bar_x, bar_y + bar_h)
        grad.setColorAt(0.00, QColor(255,   0,   0))   
        grad.setColorAt(0.25, QColor(255, 255,   0))   
        grad.setColorAt(0.50, QColor(  0, 255,   0))   
        grad.setColorAt(0.75, QColor(  0, 255, 255))   
        grad.setColorAt(1.00, QColor(  0,   0, 255))   

        painter.fillRect(bar_x, bar_y, bar_w, bar_h, grad)
        
        painter.setPen(QColor(50, 50, 50))
        font = QFont("Consolas", 8)
        painter.setFont(font)
        for i in range(6):
            t = i / 5
            val = self.vmax - t * (self.vmax - self.vmin)
            y_pos = int(bar_y + t * bar_h)
            painter.drawText(bar_x + bar_w + 8, y_pos + 4, f"{val:.2e}")

        painter.setPen(QColor(20, 20, 20))
        font_title = QFont("Consolas", 7, QFont.Weight.Bold)
        painter.setFont(font_title)
        painter.save()
        painter.translate(5, bar_y + bar_h // 2)
        painter.rotate(-90)
        painter.drawText(-60, 0, self.label)
        painter.restore()

class SolidResultsViewer(QMainWindow):
    def __init__(self, solid_dm, stress_results, U_full=None, parent=None):
        super().__init__(parent)
        self.dm      = solid_dm
        self.results = stress_results
        self.U_full  = U_full
        self.scale_factor = 0.0

        self.cut_enabled = False
        self.cut_axis    = 0          
        self.cut_value   = 0.0        

        self._node_coords_arr   = None  
        self._node_disp_arr     = None  
        self._elem_stress_arr   = None  
        self.current_verts      = None                                  
        self.face_to_elem       = None                                        
        self._selected_elem_idx = None
        self._highlight_item    = None
        self._current_component = "von_mises"

        self.setWindowTitle("OpenCivil — Solid FEM Stress Viewer")
        self.resize(1000, 700)
        self.setStyleSheet("background-color: #FFFFFF; color: #333333;")                   

        self._build_ui()
        self._render("von_mises")

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.gl_view = gl.GLViewWidget()
        self.gl_view.setBackgroundColor('#F8F9FA')                               
        self.gl_view.opts['distance'] = 3.0
        self.gl_view.installEventFilter(self)   
        layout.addWidget(self.gl_view, stretch=1)

        self.sidebar = QFrame()
        self.sidebar.setStyleSheet("""
            QFrame { 
                background-color: #FFFFFF; 
                border-left: 1px solid #DDDDDD;
            }
            QLabel { color: #555; font-family: 'Segoe UI', sans-serif; font-size: 11px; }
            QComboBox { 
                background: #FFFFFF; color: #333; border: 1px solid #CCC; 
                border-radius: 3px; padding: 4px; font-size: 12px;
            }
            QPushButton {
                background: #E0E0E0; color: #333; border: 1px solid #CCC; border-radius: 4px; 
                padding: 6px; font-weight: bold; font-size: 10px;
            }
            QPushButton:hover { background: #D0D0D0; }
        """)
        
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(15, 20, 15, 20)
        side_layout.setSpacing(15)

        side_layout.addWidget(QLabel("RESULTS COMPONENT"))
        self.combo = QComboBox()
        self.combo.addItems(["von_mises", "sxx", "syy", "szz", "sxy", "syz", "sxz"])
        self.combo.currentTextChanged.connect(self._render)
        side_layout.addWidget(self.combo)

        side_layout.addSpacing(10)
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setStyleSheet("color: #DDDDDD"); side_layout.addWidget(line)
        side_layout.addSpacing(10)

        side_layout.addWidget(QLabel("DEFLECTION SCALE"))
        self.lbl_scale = QLabel("Scale: 0.0x")
        self.lbl_scale.setStyleSheet("color: #eee; font-weight: bold; font-family: Consolas;")
        side_layout.addWidget(self.lbl_scale)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 500) 
        self.slider.setValue(0)
        
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #DDDDDD; border-radius: 2px; }
            QSlider::handle:horizontal { background: #666666; width: 14px; margin: -5px 0; border-radius: 7px; }
        """)
        self.slider.valueChanged.connect(self._on_scale_changed)
        side_layout.addWidget(self.slider)

        btn_lay = QHBoxLayout()
        btn_reset = QPushButton("REAL (0x)")
        btn_reset.clicked.connect(lambda: self.slider.setValue(0))
        btn_auto = QPushButton("MAX (100x)")
        btn_auto.clicked.connect(lambda: self.slider.setValue(100))
        btn_lay.addWidget(btn_reset)
        btn_lay.addWidget(btn_auto)
        side_layout.addLayout(btn_lay)

        side_layout.addSpacing(10)
        line2 = QFrame(); line2.setFrameShape(QFrame.Shape.HLine); line2.setStyleSheet("color: #DDDDDD"); side_layout.addWidget(line2)
        side_layout.addSpacing(10)

        side_layout.addWidget(QLabel("SECTION CUT"))

        axis_btn_lay = QHBoxLayout()
        self._cut_axis_btns = []
        for i, ax in enumerate(["X", "Y", "Z"]):
            btn = QPushButton(ax)
            btn.setCheckable(True)
            btn.setFixedHeight(26)
            btn.clicked.connect(lambda checked, idx=i: self._on_cut_axis_changed(idx))
            self._cut_axis_btns.append(btn)
            axis_btn_lay.addWidget(btn)
        self._cut_axis_btns[0].setChecked(True)   
        self._update_axis_btn_styles()
        side_layout.addLayout(axis_btn_lay)

        self._cut_slider = QSlider(Qt.Orientation.Horizontal)
        self._cut_slider.setRange(0, 1000)
        self._cut_slider.setValue(1000)
        self._cut_slider.setStyleSheet("""
            QSlider::groove:horizontal { height: 4px; background: #DDDDDD; border-radius: 2px; }
            QSlider::handle:horizontal { background: #666666; width: 14px; margin: -5px 0; border-radius: 7px; }
        """)
        self._cut_slider.valueChanged.connect(self._on_cut_slider_changed)
        side_layout.addWidget(self._cut_slider)

        self._cut_lbl = QLabel("Cut: OFF")
        self._cut_lbl.setStyleSheet("color: #888; font-family: Consolas; font-size: 10px;")
        side_layout.addWidget(self._cut_lbl)

        btn_cut_row = QHBoxLayout()
        btn_cut_on  = QPushButton("ENABLE")
        btn_cut_on.clicked.connect(lambda: self._set_cut_enabled(True))
        btn_cut_off = QPushButton("RESET")
        btn_cut_off.clicked.connect(lambda: self._set_cut_enabled(False))
        btn_cut_row.addWidget(btn_cut_on)
        btn_cut_row.addWidget(btn_cut_off)
        side_layout.addLayout(btn_cut_row)

        side_layout.addSpacing(10)
        line3 = QFrame(); line3.setFrameShape(QFrame.Shape.HLine); line3.setStyleSheet("color: #DDDDDD"); side_layout.addWidget(line3)
        side_layout.addSpacing(10)

        side_layout.addWidget(QLabel("ELEMENT QUERY  [dbl-click]"))
        self._query_lbl = QLabel("—")
        self._query_lbl.setWordWrap(True)
        self._query_lbl.setStyleSheet(
            "color: #000000; font-family: Consolas; font-size: 10px; "
            "background: #F8F9FA; border: 1px solid #CCCCCC; border-radius: 4px; padding: 6px;"
        )
        side_layout.addWidget(self._query_lbl)

        side_layout.addStretch()

        self.colorbar = ColorBar(label="STRESS (Pa)")
        self.stats_label = QLabel()
        
        self.stats_label.setStyleSheet("color: #333; font-family: Consolas; font-size: 10px; background: rgba(255,255,255,220); padding: 6px; border-radius: 4px; border: 1px solid #ccc;")
                                                                      
        overlay_layout = QVBoxLayout(self.gl_view)
        overlay_layout.setContentsMargins(20, 20, 20, 20)
        overlay_layout.addStretch()                                   
        overlay_layout.addWidget(self.colorbar, alignment=Qt.AlignmentFlag.AlignLeft)
        overlay_layout.addWidget(self.stats_label, alignment=Qt.AlignmentFlag.AlignLeft)

        from PyQt6.QtWidgets import QScrollArea

        scroll = QScrollArea()
        scroll.setWidget(self.sidebar)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(200)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet("""
            QScrollArea { background-color: #FFFFFF; border-left: 1px solid #DDDDDD; border-top: none; border-bottom: none; border-right: none; }
            QScrollBar:vertical { background: #F0F0F0; width: 6px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #CCCCCC; border-radius: 3px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        layout.addWidget(scroll)

    def _on_scale_changed(self, val):
        self.scale_factor = float(val)
        self.lbl_scale.setText(f"Scale: {val:>.1f}x")
        
        if hasattr(self, 'mesh_item') and hasattr(self, 'base_verts'):
            new_verts = self.base_verts + self.delta_verts * self.scale_factor
            self.current_verts = new_verts                               
            self.mesh_item.setMeshData(
                vertexes=new_verts, 
                faces=self.faces, 
                vertexColors=self.colors
            )
            self._update_highlight()

    def _get_stress_array(self, component):
        comp_map = {
            "von_mises": None,
            "sxx": 0, "syy": 1, "szz": 2,
            "sxy": 3, "syz": 4, "sxz": 5
        }
        out = []
        for r in self.results:
            if component == "von_mises":
                out.append(r['von_mises'])
            else:
                idx = comp_map[component]
                out.append([node_s[idx] for node_s in r['stress']])
        return np.array(out, dtype=float)

    def _render(self, component):
        self._current_component = component
        for item in list(self.gl_view.items):
            if isinstance(item, GLMeshItem):
                if hasattr(self, '_cut_plane_item') and item is self._cut_plane_item:
                    continue
                self.gl_view.removeItem(item)

        nodes    = self.dm.nodes
        elements = self.dm.elements
        n_nodes  = len(nodes)

        coords = np.zeros((n_nodes, 3))
        for node in nodes:
            coords[node['idx']] = node['coords']

        # ── MESH PREVIEW MODE (no stress results) ──────────────────────────────
        # When called from Preview Mesh, stresses=[] so results is empty.
        # Guard here instead of crashing inside _get_stress_array / element_to_node_stresses.
        is_preview_only = (len(self.results) == 0)

        if is_preview_only:
            node_colors = np.full((n_nodes, 4), [0.55, 0.65, 0.72, 1.0], dtype=np.float32)
            vmin, vmax  = 0.0, 0.0
        else:
            self._elem_stress_arr = self._get_stress_array(component)
            node_idx_list = [el['node_indices'] for el in elements]
            node_stress   = element_to_node_stresses(self._elem_stress_arr, n_nodes, node_idx_list)

            if component == "von_mises":
                vmin = float(np.percentile(node_stress, 2))
                vmax = float(np.percentile(node_stress, 98))
                node_colors, _, _ = stress_to_colors(node_stress, vmin=vmin, vmax=vmax)
            else:
                node_colors, vmin, vmax = stress_to_colors(node_stress)
        # ───────────────────────────────────────────────────────────────────────

        self._node_coords_arr = coords.astype(np.float32)
        if self.U_full is not None:
            disp = np.zeros((n_nodes, 3), dtype=np.float32)
            for node in nodes:
                i = node['idx']
                disp[i] = self.U_full[i*3 : i*3+3]
            self._node_disp_arr = disp

        self._model_min = coords.min(axis=0)
        self._model_max = coords.max(axis=0)
        if self.cut_value == 0.0:
            self.cut_value = float(self._model_max[self.cut_axis])

        tet_faces = [(0,1,2),(0,1,3),(0,2,3),(1,2,3)]
        all_verts, all_colors, all_deltas = [], [], []
        face_elem_mapping = []

        for elem_idx, el in enumerate(elements):
            ni = el['node_indices']

            if self.cut_enabled:
                ax = self.cut_axis
                keep = any(coords[ni[fi]][ax] <= self.cut_value + 1e-9
                           for f in tet_faces for fi in f)
                if not keep:
                    continue

            for f in tet_faces:
                if self.cut_enabled:
                    ax = self.cut_axis
                    if all(coords[ni[fi]][ax] > self.cut_value + 1e-9 for fi in f):
                        continue
                for fi in f:
                    n_idx = ni[fi]
                    all_verts.append(coords[n_idx])
                    all_colors.append(node_colors[n_idx])
                    if self.U_full is not None:
                        dx = self.U_full[n_idx*3]
                        dy = self.U_full[n_idx*3 + 1]
                        dz = self.U_full[n_idx*3 + 2]
                        all_deltas.append([dx, dy, dz])

                face_elem_mapping.append(elem_idx)

        self.face_to_elem = np.array(face_elem_mapping, dtype=int)
        self.base_verts   = np.array(all_verts,  dtype=np.float32)
        self.colors       = np.array(all_colors, dtype=np.float32)

        if self.U_full is not None:
            self.delta_verts = np.array(all_deltas, dtype=np.float32)
        else:
            self.delta_verts = np.zeros_like(self.base_verts)

        self.current_verts = self.base_verts + self.delta_verts * self.scale_factor

        n_tris     = len(self.base_verts) // 3
        self.faces = np.arange(n_tris * 3, dtype=np.uint32).reshape(n_tris, 3)

        self.mesh_item = GLMeshItem(
            vertexes=self.current_verts, faces=self.faces,
            faceColors=None, vertexColors=self.colors,
            smooth=True, drawEdges=True,
            edgeColor=(0.15, 0.15, 0.15, 0.6),
        )
        self.mesh_item.setGLOptions('opaque')
        self.gl_view.addItem(self.mesh_item)

        self._update_highlight()

        if not hasattr(self, '_camera_set'):
            centre = self.base_verts.mean(axis=0)
            span   = float(np.max(self.base_verts.max(axis=0) - self.base_verts.min(axis=0)))
            self.gl_view.opts['center']    = pg.Vector(float(centre[0]),
                                                        float(centre[1]),
                                                        float(centre[2]))
            self.gl_view.opts['distance']  = max(span * 3.0, 1.0)
            self.gl_view.opts['elevation'] = 25
            self.gl_view.opts['azimuth']   = -120
            self._camera_set = True

        if is_preview_only:
            self.colorbar.update_range(0, 1, "MESH PREVIEW")
            self.stats_label.setText(
                f"MESH PREVIEW\n(run full analysis for stress)\n\n"
                f"Nodes: {n_nodes}\nElems: {len(elements)}"
            )
        else:
            self.colorbar.update_range(vmin, vmax, f"{component} (Pa)")
            self.stats_label.setText(
                f"Min: {vmin:.3e}\nMax: {vmax:.3e}\n\n"
                f"Nodes: {n_nodes}\nElems: {len(elements)}"
            )
                  
    def _update_axis_btn_styles(self):
        for i, btn in enumerate(self._cut_axis_btns):
            if btn.isChecked():
                btn.setStyleSheet(
                    "background: #0078D7; color: #fff; border: none; border-radius: 4px; "
                    "padding: 4px; font-weight: bold; font-size: 11px;"
                )
            else:
                btn.setStyleSheet(
                    "background: #E0E0E0; color: #333; border: 1px solid #CCC; border-radius: 4px; "
                    "padding: 4px; font-size: 11px;"
                )

    def _on_cut_axis_changed(self, axis_id):
        self.cut_axis = axis_id
        for i, btn in enumerate(self._cut_axis_btns):
            btn.setChecked(i == axis_id)
        self._update_axis_btn_styles()
        if hasattr(self, '_model_min'):
            self.cut_value = float(self._model_max[axis_id])
            self._cut_slider.setValue(1000)
        if self.cut_enabled:
            self._render(self._current_component)
            self._update_cut_plane()

    def _on_cut_slider_changed(self, val):
        if not hasattr(self, '_model_min'):
            return
        lo = float(self._model_min[self.cut_axis])
        hi = float(self._model_max[self.cut_axis])
        self.cut_value = lo + (val / 1000.0) * (hi - lo)
        ax_name = ["X", "Y", "Z"][self.cut_axis]
        self._cut_lbl.setText(f"Cut {ax_name}: {self.cut_value:.3f} m")
        self._cut_lbl.setStyleSheet("color: #eee; font-family: Consolas; font-size: 10px;")
        if self.cut_enabled:
            self._render(self._current_component)
            self._update_cut_plane()

    def _set_cut_enabled(self, enabled):
        self.cut_enabled = enabled
        if not enabled:
            self._cut_slider.setValue(1000)
            self._cut_lbl.setText("Cut: OFF")
            self._cut_lbl.setStyleSheet("color: #888; font-family: Consolas; font-size: 10px;")
            self._remove_cut_plane()
        else:
            self._update_cut_plane()
        self._render(self._current_component)

    def _update_cut_plane(self):
        self._remove_cut_plane()
        if not hasattr(self, '_model_min') or not self.cut_enabled:
            return

        mn = self._model_min
        mx = self._model_max
        pad = (mx - mn).max() * 0.05   
        v   = self.cut_value
        ax  = self.cut_axis

        if ax == 0:   
            corners = np.array([
                [v, mn[1]-pad, mn[2]-pad],
                [v, mx[1]+pad, mn[2]-pad],
                [v, mx[1]+pad, mx[2]+pad],
                [v, mn[1]-pad, mx[2]+pad],
            ], dtype=np.float32)
        elif ax == 1: 
            corners = np.array([
                [mn[0]-pad, v, mn[2]-pad],
                [mx[0]+pad, v, mn[2]-pad],
                [mx[0]+pad, v, mx[2]+pad],
                [mn[0]-pad, v, mx[2]+pad],
            ], dtype=np.float32)
        else:         
            corners = np.array([
                [mn[0]-pad, mn[1]-pad, v],
                [mx[0]+pad, mn[1]-pad, v],
                [mx[0]+pad, mx[1]+pad, v],
                [mn[0]-pad, mx[1]+pad, v],
            ], dtype=np.float32)

        faces  = np.array([[0,1,2],[0,2,3]], dtype=np.uint32)
        color  = np.array([[0.4, 0.7, 1.0, 0.25]] * 4, dtype=np.float32)

        self._cut_plane_item = GLMeshItem(
            vertexes=corners, faces=faces,
            vertexColors=color, smooth=False, drawEdges=True,
            edgeColor=(0.5, 0.8, 1.0, 0.6),
        )
        self._cut_plane_item.setGLOptions('translucent')
        self.gl_view.addItem(self._cut_plane_item)

    def _remove_cut_plane(self):
        if hasattr(self, '_cut_plane_item') and self._cut_plane_item is not None:
            if self._cut_plane_item in self.gl_view.items:
                self.gl_view.removeItem(self._cut_plane_item)
            self._cut_plane_item = None

    def eventFilter(self, obj, event):
        if obj is self.gl_view:
            if event.type() == QEvent.Type.MouseButtonDblClick:
                self._on_canvas_click(event)
                return True
        return super().eventFilter(obj, event)

    def _on_canvas_click(self, event):
        """Double-click: cast a 3D ray to pick the exact visible element face."""
        if not hasattr(self, 'current_verts') or self.current_verts is None:
            return

        try:
            pos = event.position()
            mx, my = float(pos.x()), float(pos.y())
        except AttributeError:
            mx, my = float(event.x()), float(event.y())

        w, h = self.gl_view.width(), self.gl_view.height()
        opts = self.gl_view.opts
        dist = float(opts['distance'])
        az   = np.radians(float(opts['azimuth']))
        el   = np.radians(float(opts['elevation']))
        cx   = float(opts['center'].x())
        cy   = float(opts['center'].y())
        cz   = float(opts['center'].z())
        fov  = float(opts.get('fov', 60))
        aspect = w / max(h, 1)

        fwd = np.array([
            -(np.cos(el) * np.cos(az)),
            -(np.cos(el) * np.sin(az)),
            -np.sin(el),
        ])
        world_up = np.array([0.0, 0.0, 1.0])
        if abs(fwd[2]) > 0.95:
            world_up = np.array([0.0, 1.0, 0.0])
        right = np.cross(fwd, world_up); right /= np.linalg.norm(right)
        up    = np.cross(right, fwd)
        cam   = np.array([cx, cy, cz]) - fwd * dist

        if fov < 1.0:                        
            world_y = (0.5 - my / h) * dist
            world_x = (mx / w - 0.5) * dist * aspect
            O = cam + world_x * right + world_y * up
            D = fwd
        else:                      
            ndc_x = (mx / w - 0.5) * 2.0
            ndc_y = (0.5 - my / h) * 2.0
            f_val = 1.0 / np.tan(np.radians(fov) / 2.0)
            D = fwd + (ndc_x * aspect / f_val) * right + (ndc_y / f_val) * up
            D /= np.linalg.norm(D)
            O = cam

        V0 = self.current_verts[self.faces[:, 0]]
        V1 = self.current_verts[self.faces[:, 1]]
        V2 = self.current_verts[self.faces[:, 2]]

        E1 = V1 - V0
        E2 = V2 - V0
        P = np.cross(D, E2)
        det = np.sum(E1 * P, axis=1)

        eps = 1e-8
        valid = np.abs(det) > eps

        inv_det = np.zeros_like(det)
        inv_det[valid] = 1.0 / det[valid]
        
        T = O - V0
        u = np.sum(T * P, axis=1) * inv_det
        valid &= (u >= 0.0) & (u <= 1.0)

        Q = np.cross(T, E1)
        v = np.sum(D * Q, axis=1) * inv_det
        valid &= (v >= 0.0) & (u + v <= 1.0)

        t = np.sum(E2 * Q, axis=1) * inv_det
        valid &= (t > eps)

        if not np.any(valid):
            self._selected_elem_idx = None
            self._update_highlight()
            self._query_lbl.setText("—")
            return

        valid_idx = np.where(valid)[0]
        hit_t = t[valid_idx]
        closest_hit_idx = valid_idx[np.argmin(hit_t)]
        hit_elem_idx = self.face_to_elem[closest_hit_idx]

        self._selected_elem_idx = hit_elem_idx
        self._update_highlight()

        el_data  = self.dm.elements[hit_elem_idx]
        node_ids = [self.dm.nodes[ni].get('id', ni+1) for ni in el_data['node_indices']]

        # Preview mode: no stress results loaded yet
        if self._elem_stress_arr is None:
            self._query_lbl.setText(
                f"ELEMENT #{el_data.get('id', hit_elem_idx+1)}\n"
                f"Type: Tetra\n"
                f"Nodes: {node_ids}\n\n"
                f"(No stress — run full\nanalysis first)"
            )
            return

        s_val = self._elem_stress_arr[hit_elem_idx]
        comp  = self._current_component
        
        disp_str = ""
        if self._node_disp_arr is not None:
            ni = el_data['node_indices']
            avg_d = np.mean(self._node_disp_arr[ni], axis=0)
            mag = float(np.linalg.norm(avg_d))
            disp_str = (f"\n\nAvg Disp:\n"
                        f"Ux: {avg_d[0]:.3e} m\n"
                        f"Uy: {avg_d[1]:.3e} m\n"
                        f"Uz: {avg_d[2]:.3e} m\n"
                        f"|U|: {mag:.3e} m")

        node_ids = [self.dm.nodes[ni].get('id', ni+1) for ni in el_data['node_indices']]

        self._query_lbl.setText(
            f"ELEMENT #{el_data.get('id', hit_elem_idx+1)}\n"
            f"Type: Tetra\n"
            f"Nodes: {node_ids}\n"
            f"\n{comp} (Avg):\n  {np.mean(s_val):.4e} Pa"
            f"{disp_str}"
        )

    def _update_highlight(self):
        """Draws the selected Tet element slightly scaled out so it's always visible."""
        if hasattr(self, '_highlight_item') and self._highlight_item in self.gl_view.items:
            self.gl_view.removeItem(self._highlight_item)
            
        if not hasattr(self, '_selected_elem_idx') or self._selected_elem_idx is None:
            return
            
        el = self.dm.elements[self._selected_elem_idx]
        ni = el['node_indices']
        
        pts = self._node_coords_arr[ni].copy()
        if hasattr(self, '_node_disp_arr') and self._node_disp_arr is not None:
            pts += self._node_disp_arr[ni] * self.scale_factor
            
        centroid = np.mean(pts, axis=0)
        pts = centroid + (pts - centroid) * 1.02
        
        faces = np.array([[0,1,2],[0,1,3],[0,2,3],[1,2,3]], dtype=np.uint32)
        colors = np.array([[1.0, 0.2, 0.8, 0.6]] * 4, dtype=np.float32) 
        
        self._highlight_item = GLMeshItem(
            vertexes=pts, faces=faces, vertexColors=colors,
            drawEdges=True, edgeColor=(1.0, 1.0, 0.0, 1.0), smooth=False
        )
        self._highlight_item.setGLOptions('translucent')
        self.gl_view.addItem(self._highlight_item)

    def closeEvent(self, event):
        """
        Clear every GL item before Qt tears down the OpenGL context.
        Without this, pyqtgraph's GLMeshItem.paint() fires one last time
        on a dead context and crashes with:
            AttributeError: 'NoneType' object has no attribute 'hasExtension'
        """
        try:
            for item in list(self.gl_view.items):
                self.gl_view.removeItem(item)
        except Exception:
            pass
        super().closeEvent(event)

class _DmProxy:
    def __init__(self, nodes, elements, total_dofs):
        self.nodes      = nodes
        self.elements   = elements
        self.total_dofs = total_dofs

if __name__ == "__main__":
    import ctypes
    from PyQt6.QtGui import QIcon

    if sys.platform == 'win32':
        myappid = 'metu.civil.OPENCIVIL.v03'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    if len(sys.argv) >= 2:
                                                                       
        import pickle
        pkl_path = sys.argv[1]
        try:
            with open(pkl_path, 'rb') as f:
                data = pickle.load(f)
            try:
                os.unlink(pkl_path)                                      
            except Exception:
                pass
            dm_proxy = _DmProxy(
                nodes      = data['nodes'],
                elements   = data['elements'],
                total_dofs = data['total_dofs'],
            )
            stress_results = data['stress_results']
            U_full = data.get('U_full', None)
        except Exception as e:
            print(f"[Viewer] Failed to load data: {e}")
            sys.exit(1)

        app = QApplication(sys.argv)
        viewer = SolidResultsViewer(dm_proxy, stress_results, U_full=U_full)
        
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'graphic', 'logo.png'))
        if os.path.exists(icon_path):
            viewer.setWindowIcon(QIcon(icon_path))
            
        viewer.show()
        sys.exit(app.exec())

    else:
        from solid_data_manager import SolidDataManager
        from solid_assembler import SolidAssembler

        L, b, h = 1.0, 0.1, 0.1
        E, nu   = 210e9, 0.3
        P       = 1000.0
        nx, ny, nz = 12, 2, 2

        xs = np.linspace(0, L, nx+1)
        ys = np.linspace(0, b, ny+1)
        zs = np.linspace(0, h, nz+1)

        def nid(i, j, k):
            return i*(ny+1)*(nz+1) + j*(nz+1) + k

        node_coords = []
        for i in range(nx+1):
            for j in range(ny+1):
                for k in range(nz+1):
                    node_coords.append([xs[i], ys[j], zs[k]])

        elements_raw = []
        for i in range(nx):
            for j in range(ny):
                for k in range(nz):
                    n0=nid(i,j,k); n1=nid(i+1,j,k); n2=nid(i+1,j+1,k)
                    n3=nid(i,j+1,k); n4=nid(i,j,k+1); n5=nid(i+1,j,k+1)
                    n6=nid(i+1,j+1,k+1); n7=nid(i,j+1,k+1)
                    elements_raw += [
                        [n0,n1,n3,n4],[n1,n2,n3,n6],
                        [n4,n5,n6,n1],[n4,n6,n7,n3],[n1,n3,n4,n6]
                    ]

        tol = 1e-9
        tip_nodes = [i for i,c in enumerate(node_coords) if abs(c[0]-L)<tol]
        p_each    = P / len(tip_nodes)

        model = {
            "materials": [{"name": "Steel", "E": E, "nu": nu}],
            "nodes": [
                {"id": i+1, "x": float(c[0]), "y": float(c[1]), "z": float(c[2]),
                 "restraints": [bool(abs(c[0])<tol)]*3}
                for i, c in enumerate(node_coords)
            ],
            "elements": [
                {"id": eid+1, "n1": int(e[0]+1), "n2": int(e[1]+1),
                 "n3": int(e[2]+1), "n4": int(e[3]+1), "mat": "Steel"}
                for eid, e in enumerate(elements_raw)
            ],
            "loads": [
                {"node_id": int(ni+1), "fx": 0.0, "fy": 0.0, "fz": -p_each}
                for ni in tip_nodes
            ]
        }

        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        json.dump(model, tmp); tmp.close()

        dm = SolidDataManager(tmp.name)
        dm.process_all()
        asm = SolidAssembler(dm)
        asm.assemble_system()
        U, _ = asm.solve()
        stress_results = asm.compute_element_stresses(U)
        os.unlink(tmp.name)

        print(f"Launching viewer — {len(dm.nodes)} nodes, {len(dm.elements)} elements")
        app = QApplication.instance() or QApplication(sys.argv)
        viewer = SolidResultsViewer(dm, stress_results, U_full=U)
        viewer.show()
        sys.exit(app.exec())