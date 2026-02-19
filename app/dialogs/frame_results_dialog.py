import sys
import os
import math
import json
import numpy as np
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QComboBox, QRadioButton, QGroupBox, QSlider, 
                             QWidget, QFrame, QLineEdit, QGridLayout, QSizePolicy,
                             QPushButton)
from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor, QBrush, QPolygonF

current_dir = os.path.dirname(os.path.abspath(__file__))
app_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(app_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from core.solver.linear_static.element_library import get_local_stiffness_matrix, get_rotation_matrix, get_eccentricity_matrix

class MemberAnalyzer:
    def __init__(self, element, model, num_stations=21):
        self.el = element
        self.model = model
        self.n_stations = num_stations
        
        self.element_fef = np.zeros(12) 

        try:
            if hasattr(self.model, "file_path") and self.model.file_path:
                matrix_path = self.model.file_path.replace(".mf", "_matrices.json")
                
                if os.path.exists(matrix_path):
                    with open(matrix_path, "r") as f:
                        data = json.load(f)
                        str_id = str(self.el.id)
                        if str_id in data:
                            self.element_fef = np.array(data[str_id]["fef"])
                            print(f"Loaded FEF for Element {self.el.id}: {self.element_fef}")
            else:
                print("Warning: Model does not have a file_path attribute. Cannot find matrices.")
        except Exception as e:
            print(f"Error loading FEF: {e}")

        self.L_clear = self.el.length()                                                               
        self.stations = np.linspace(0, self.L_clear, num_stations)
        
        self.P = np.zeros(num_stations)
        self.V2 = np.zeros(num_stations); self.M3 = np.zeros(num_stations)
        self.V3 = np.zeros(num_stations); self.M2 = np.zeros(num_stations)
        self.Defl_2_Rel = np.zeros(num_stations)                                     
        self.Defl_3_Rel = np.zeros(num_stations)
        self.end_forces = np.zeros(12) 

        self.calculate_results()

    def calculate_results(self):
                                             
        res = self.model.results["displacements"]
                                     
        u_i = np.array(res.get(str(self.el.node_i.id), [0.0]*6))
        u_j = np.array(res.get(str(self.el.node_j.id), [0.0]*6))
        u_global = np.concatenate((u_i, u_j))              
        
        p1 = self.el.node_i.get_coords()
        p2 = self.el.node_j.get_coords()
        R_3x3 = get_rotation_matrix(p1, p2, self.el.beta_angle)
        
        T_rot = np.zeros((12, 12))
        for k in range(4): T_rot[k*3:(k+1)*3, k*3:(k+1)*3] = R_3x3
        
        off_i_vec_g = np.array(getattr(self.el, 'offset_i', [0,0,0]))
        off_j_vec_g = np.array(getattr(self.el, 'offset_j', [0,0,0]))
        
        off_i_loc = R_3x3 @ off_i_vec_g
        off_j_loc = R_3x3 @ off_j_vec_g
        
        off_i_loc[0] += getattr(self.el, 'end_off_i', 0.0)
        off_j_loc[0] -= getattr(self.el, 'end_off_j', 0.0)
        
        T_ecc = get_eccentricity_matrix(off_i_loc, off_j_loc)
        
        u_local_node = T_rot @ u_global
        u_flex = T_ecc @ u_local_node
        
        sec = self.el.section
        mat = sec.material
        
        As2 = getattr(sec, 'As2', getattr(sec, 'Asy', 0.0))
        As3 = getattr(sec, 'As3', getattr(sec, 'Asz', 0.0))
        I22 = getattr(sec, 'I22', getattr(sec, 'Iy', 0.0))
        I33 = getattr(sec, 'I33', getattr(sec, 'Iz', 0.0))

        k_local = get_local_stiffness_matrix(
            mat.E, mat.G, sec.A, sec.J, I22, I33, As2, As3, self.L_clear
        )
        
        self.end_forces = (k_local @ u_flex) + self.element_fef
        
        Fx1, Fy1, Fz1 = self.end_forces[0], self.end_forces[1], self.end_forces[2]
        Mx1, My1, Mz1 = self.end_forces[3], self.end_forces[4], self.end_forces[5]

        u1, v1, w1, thx1, thy1, thz1 = u_flex[0:6]
        u2, v2, w2, thx2, thy2, thz2 = u_flex[6:12]

        for i, x in enumerate(self.stations):
            xi = x / self.L_clear
            
            self.P[i] = -Fx1                                    
            
            self.V2[i] = -Fy1                 
            self.M3[i] = -Mz1 - self.V2[i]*x                     
            
            self.V3[i] = -Fz1
            self.M2[i] = -My1 - self.V3[i]*x                                                  
            
            N1 = 1 - 3*xi**2 + 2*xi**3
            N2 = x * (1 - 2*xi + xi**2)
            N3 = 3*xi**2 - 2*xi**3
            N4 = x * (xi**2 - xi)
            
            defl_2_abs = N1*v1 + N2*thz1 + N3*v2 + N4*thz2
            defl_3_abs = N1*w1 + N2*thy1 + N3*w2 + N4*thy2
            
            chord_2 = v1 + (v2 - v1) * xi
            chord_3 = w1 + (w2 - w1) * xi
            
            self.Defl_2_Rel[i] = defl_2_abs - chord_2
            self.Defl_3_Rel[i] = defl_3_abs - chord_3

class DiagramWidget(QWidget):
    def __init__(self, color, parent=None):
        super().__init__(parent)
        self.data_x = []
        self.data_y = []
        self.fill_color = color
        self.cursor_x = 0.0
        self.cursor_val = 0.0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(100)

    def set_data(self, x, y):
        self.data_x = x
        self.data_y = y
        self.update()

    def set_cursor(self, x):
        self.cursor_x = x
        if len(self.data_x) > 0:
            self.cursor_val = np.interp(x, self.data_x, self.data_y)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        
        painter.fillRect(0, 0, w, h, QColor(255, 255, 255))
        painter.setPen(QPen(QColor(220, 220, 220), 1))
        painter.drawRect(0, 0, w-1, h-1)

        if len(self.data_x) == 0: return

        y_abs = np.abs(self.data_y)
        max_y = np.max(y_abs) if len(y_abs) > 0 else 0
        if max_y < 1e-9: max_y = 1.0                
        
        padding_y = 20
        padding_x = 20
        scale_y = (h / 2.0 - padding_y) / max_y
        
        L_total = self.data_x[-1]
        if L_total == 0: L_total = 1.0
        scale_x = (w - 2 * padding_x) / L_total
        
        mid_y = h / 2.0

        def to_pt(x, y):
            px = padding_x + x * scale_x
            py = mid_y - (y * scale_y)                         
            return QPointF(px, py)

        painter.setPen(QPen(QColor(80, 80, 80), 1, Qt.PenStyle.DashLine))
        painter.drawLine(to_pt(0, 0), to_pt(L_total, 0))

        poly = QPolygonF()
        poly.append(to_pt(0, 0))                     
        for i in range(len(self.data_x)):
            poly.append(to_pt(self.data_x[i], self.data_y[i]))
        poly.append(to_pt(L_total, 0))                   

        painter.setBrush(QBrush(self.fill_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(poly)
        
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(self.fill_color.darker(140), 2))
        painter.drawPolyline(poly)

        cx_pt = to_pt(self.cursor_x, 0)
        painter.setPen(QPen(QColor(0, 0, 0), 1, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(cx_pt.x(), 0), QPointF(cx_pt.x(), h))

class FreeBodyWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.forces = np.zeros(12)
        self.L = 1.0
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(80)

    def set_data(self, forces, length):
        self.forces = forces                        
        self.L = length
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        painter.fillRect(0, 0, w, h, QColor(255, 255, 255))
        painter.setPen(QPen(QColor(200, 200, 200), 1)); painter.drawRect(0,0,w-1,h-1)

        y_beam = h / 2
        margin = 50
        x1, x2 = margin, w - margin
        
        painter.setPen(QPen(QColor(40, 40, 40), 4))
        painter.drawLine(int(x1), int(y_beam), int(x2), int(y_beam))
        
        def draw_val(x, val, is_moment, label):
            if abs(val) < 1e-2: return
            
            painter.setPen(QPen(QColor(0, 0, 180), 2))
            text = f"{label}: {val:.1f}"
            
            if is_moment:
                     
                rect = QRectF(x-15, y_beam-15, 30, 30)
                painter.drawArc(rect, 0, 16*360)
                painter.drawText(int(x)-20, int(y_beam)-25, text)
            else:
                             
                dir = -1 if val > 0 else 1
                p_tip = QPointF(x, y_beam)
                p_tail = QPointF(x, y_beam + dir * 30)
                painter.drawLine(p_tail, p_tip)
                painter.drawText(int(x)+5, int(y_beam + dir * 40), text)

        draw_val(x1, self.forces[1], False, "V")
        draw_val(x1, self.forces[5], True, "M")
        
        draw_val(x2, self.forces[7], False, "V")
        draw_val(x2, self.forces[11], True, "M")

class ResultRow(QWidget):
    def __init__(self, title, widget, unit_str, parent=None):
        super().__init__(parent)
        self.unit_str = unit_str
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        grp = QGroupBox(title)
        grp.setStyleSheet("QGroupBox { font-weight: bold; color: #202020; }")
        v = QVBoxLayout(grp); v.setContentsMargins(5,20,5,5)
        v.addWidget(widget)
        
        self.lbl_val = QLabel("0.0")
        self.lbl_val.setFixedWidth(120)
        self.lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_val.setStyleSheet("font-weight: bold; font-size: 12pt; padding-right: 10px; color: #333;")
        
        layout.addWidget(grp)
        layout.addWidget(self.lbl_val)

    def update_val(self, val):
        self.lbl_val.setText(f"{val:.3f} {self.unit_str}")

class FrameResultDialog(QDialog):
    def __init__(self, element, model, parent=None):
        super().__init__(parent)
        self.element = element
        self.model = model
        
        self.setWindowTitle(f"Analysis Results: Element {element.id}")
        self.resize(1000, 700)
        self.setStyleSheet("background-color: #f5f5f5;")
        
        self.analyzer = MemberAnalyzer(element, model)
        self.init_ui()
        self.update_view_mode()

    def init_ui(self):
        main = QVBoxLayout(self)
        main.setSpacing(10)
        
        top_frame = QFrame()
        top_frame.setStyleSheet("background-color: white; border-radius: 5px;")
        top = QHBoxLayout(top_frame)
        
        top.addWidget(QLabel("<b>Component:</b>"))
        self.cb_mode = QComboBox()
        self.cb_mode.addItems(["Major Axis (Shear V2 / Moment M3)", "Minor Axis (Shear V3 / Moment M2)", "Axial Force (P)"])
        self.cb_mode.currentIndexChanged.connect(self.update_view_mode)
        top.addWidget(self.cb_mode)
        
        top.addStretch()
        main.addWidget(top_frame)
        
        self.wid_fbd = FreeBodyWidget()
        main.addWidget(ResultRow("Free Body Diagram (End Forces)", self.wid_fbd, ""))
        
        self.wid_shear = DiagramWidget(QColor(255, 230, 230))           
        self.row_shear = ResultRow("Shear Force", self.wid_shear, "kN")
        main.addWidget(self.row_shear)
        
        self.wid_mom = DiagramWidget(QColor(230, 230, 255))            
        self.row_mom = ResultRow("Bending Moment", self.wid_mom, "kN-m")
        main.addWidget(self.row_mom)
        
        self.wid_defl = DiagramWidget(QColor(255, 230, 255))              
        self.row_defl = ResultRow("Relative Deflection", self.wid_defl, "m")
        main.addWidget(self.row_defl)
        
        bot_frame = QFrame()
        bot_frame.setStyleSheet("background-color: white; border-top: 1px solid #ddd;")
        bot = QHBoxLayout(bot_frame)
        
        bot.addWidget(QLabel("Location:"))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 1000)
        self.slider.valueChanged.connect(self.on_slider)
        bot.addWidget(self.slider)
        
        self.lbl_loc = QLabel("0.000 m")
        self.lbl_loc.setFixedWidth(80)
        bot.addWidget(self.lbl_loc)
        
        main.addWidget(bot_frame)
        
        btn_close = QPushButton("Done")
        btn_close.clicked.connect(self.accept)
        btn_close.setFixedWidth(100)
        main.addWidget(btn_close, 0, Qt.AlignmentFlag.AlignRight)

    def update_view_mode(self):
        idx = self.cb_mode.currentIndex()
        x = self.analyzer.stations
        
        self.wid_fbd.set_data(self.analyzer.end_forces, self.analyzer.L_clear)
        
        if idx == 0:        
            self.wid_shear.set_data(x, self.analyzer.V2)
            self.wid_mom.set_data(x, self.analyzer.M3)
            self.wid_defl.set_data(x, self.analyzer.Defl_2_Rel)
            
        elif idx == 1:        
            self.wid_shear.set_data(x, self.analyzer.V3)
            self.wid_mom.set_data(x, self.analyzer.M2)
            self.wid_defl.set_data(x, self.analyzer.Defl_3_Rel)
            
        elif idx == 2:        
            self.wid_shear.set_data(x, self.analyzer.P)
                             
            zero = np.zeros_like(x)
            self.wid_mom.set_data(x, zero)
            self.wid_defl.set_data(x, zero)

        self.on_slider(self.slider.value())

    def on_slider(self, val):
        ratio = val / 1000.0
        loc = ratio * self.analyzer.L_clear
        
        self.lbl_loc.setText(f"{loc:.3f} m")
        
        for w in [self.wid_shear, self.wid_mom, self.wid_defl]:
            w.set_cursor(loc)
            
        self.row_shear.update_val(self.wid_shear.cursor_val)
        self.row_mom.update_val(self.wid_mom.cursor_val)
        self.row_defl.update_val(self.wid_defl.cursor_val)
