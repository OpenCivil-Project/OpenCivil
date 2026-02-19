import sys
import json
import os
import numpy as np
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QTableWidget, 
                             QTableWidgetItem, QHeaderView, QLabel, QWidget)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D

from core.units import unit_registry

class MatrixSpyDialog(QDialog):
    def __init__(self, element_id, matrices_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Element {element_id} - Internal Matrices Spy")
        self.resize(900, 600)
        self.element_id = str(element_id)
        self.matrices_data = self._load_json(matrices_path)
        
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        self.tab_k = QWidget(); self.tab_k_layout = QVBoxLayout(self.tab_k)
        tabs.addTab(self.tab_k, "Local Stiffness [k]")
        
        self.tab_t = QWidget(); self.tab_t_layout = QVBoxLayout(self.tab_t)
        tabs.addTab(self.tab_t, "Transformation [T]")
        
        self.tab_fef = QWidget(); self.tab_fef_layout = QVBoxLayout(self.tab_fef)
        tabs.addTab(self.tab_fef, "Fixed End Forces (FEE)")

        self._populate_ui()

    def _load_json(self, path):
        if not os.path.exists(path): return {}
        with open(path, 'r') as f: return json.load(f)

    def _populate_ui(self):
        if self.element_id not in self.matrices_data:
            self.tab_k_layout.addWidget(QLabel("No matrix data found."))
            return
        data = self.matrices_data[self.element_id]
        self._add_matrix_table(self.tab_k_layout, data['k'], "12x12 Local Stiffness")
        self._add_matrix_table(self.tab_t_layout, data['t'], "12x12 Transformation Matrix")
        fef_col = [[x] for x in data['fef']]
        self._add_matrix_table(self.tab_fef_layout, fef_col, "12x1 Fixed End Force Vector")

    def _add_matrix_table(self, layout, matrix_data, title):
        if not matrix_data: return
        lbl = QLabel(title); lbl.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(lbl)
        rows = len(matrix_data); cols = len(matrix_data[0])
        table = QTableWidget(rows, cols)
        for r in range(rows):
            for c in range(cols):
                val = matrix_data[r][c]
                txt = f"{val:.4e}" if (abs(val)>1e7 or (abs(val)<1e-4 and abs(val)>0)) else f"{val:.4f}"
                item = QTableWidgetItem(txt)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if abs(val) < 1e-9: item.setForeground(Qt.GlobalColor.gray)
                table.setItem(r, c, item)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)

class FBDViewerDialog(QDialog):
                                                   
    COLORS = {
        'beam': '#000000',                  
        'node': '#000000',                   
        'axial': '#D32F2F',                    
        'shear': '#1976D2',                     
        'moment': '#388E3C',                       
        'torsion': '#7B1FA2'                        
    }
    
    def __init__(self, element_id, model, results_path, matrices_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Element {element_id} - Free Body Diagrams")
        self.resize(1000, 700)
        
        self.element_id = str(element_id)
        self.model = model
        self.results = self._load_json(results_path)
        self.matrices = self._load_json(matrices_path)
        
        self.element = model.elements[int(element_id)]
        self.beam_length = self.element.length()                               
        self.beam_length_display = unit_registry.to_display_length(self.beam_length)
        
        self.forces_base = self.calculate_forces()
        
        self.forces = self._convert_forces_to_display()
        
        self.force_unit = unit_registry.force_unit_name
        self.length_unit = unit_registry.length_unit_name
        self.moment_unit = f"{self.force_unit}·{self.length_unit}"
        
        layout = QVBoxLayout(self)
        
        info_text = (f"Element Length: {self.beam_length_display:.3f} {self.length_unit}  |  "
                    f"Units: Force [{self.force_unit}], Moment [{self.moment_unit}]")
        unit_label = QLabel(info_text)
        unit_label.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        unit_label.setStyleSheet("color: #555; padding: 5px;")
        layout.addWidget(unit_label)
        
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        self.add_axial_tab()

        self.add_Minor_axis_tab()

        self.add_Major_axis_tab()

        self.add_torsion_tab()

    def _load_json(self, path):
        if not os.path.exists(path): return {}
        with open(path, 'r') as f: return json.load(f)

    def calculate_forces(self):
        """Calculate forces in BASE units (Newtons, Newton-meters)"""
        if self.element_id not in self.matrices: return None
        if int(self.element_id) not in self.model.elements: return None

        el = self.model.elements[int(self.element_id)]
        k = np.array(self.matrices[self.element_id]['k'])
        t = np.array(self.matrices[self.element_id]['t'])
        fef = np.array(self.matrices[self.element_id]['fef'])
        
        n1, n2 = str(el.node_i.id), str(el.node_j.id)
        u1 = self.results['displacements'].get(n1, [0]*6)
        u2 = self.results['displacements'].get(n2, [0]*6)
        u_global = np.array(u1 + u2)

        return k @ (t @ u_global) + fef

    def _convert_forces_to_display(self):
        """Convert forces from BASE (N, N·m) to DISPLAY units (kN, kN·m, etc.)"""
        if self.forces_base is None:
            return None
        
        forces_display = np.zeros(12)
        
        for i in range(12):
            if i % 6 < 3:                                 
                forces_display[i] = unit_registry.to_display_force(self.forces_base[i])
            else:                                  
                                                                                                
                forces_display[i] = unit_registry.to_display_force(self.forces_base[i])
        
        return forces_display

    def add_axial_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        figure = Figure(figsize=(8, 4), dpi=100, facecolor='white')
        canvas = FigureCanvas(figure)
        layout.addWidget(canvas)
        self.tabs.addTab(tab, "Axial Force (P)")

        if self.forces is None: return

        ax = figure.add_subplot(111)
        
        L_display = self.beam_length_display
        L_norm = 10                                 
        
        ax.plot([0, L_norm], [0, 0], color=self.COLORS['beam'], linewidth=3, solid_capstyle='round')
        ax.plot([0, 0], [-0.3, 0.3], color=self.COLORS['node'], linewidth=2.5)          
        ax.plot([L_norm, L_norm], [-0.3, 0.3], color=self.COLORS['node'], linewidth=2.5)          
        
        ax.text(0, -0.8, f'i\n(0.00)', ha='center', va='top', fontsize=10, fontweight='bold')
        ax.text(L_norm, -0.8, f'j\n({L_display:.2f})', ha='center', va='top', fontsize=10, fontweight='bold')
        
        fx_i = self.forces[0]
        fx_j = self.forces[6]
        
        self._draw_axial_arrow(ax, 0, fx_i, 'left', L_norm)
        self._draw_axial_arrow(ax, L_norm, fx_j, 'right', L_norm)

        ax.set_ylim(-2, 2)
        ax.set_xlim(-3, L_norm + 3)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(f'Axial Force Diagram (Fx) [{self.force_unit}]', 
                    fontsize=12, fontweight='bold', pad=20)
        
        figure.tight_layout()
        canvas.draw()

    def add_Minor_axis_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        figure = Figure(figsize=(8, 5), dpi=100, facecolor='white')
        canvas = FigureCanvas(figure)
        layout.addWidget(canvas)
        self.tabs.addTab(tab, "Minor Axis (V3-M2)")

        if self.forces is None: return

        ax = figure.add_subplot(111)
        
        L_display = self.beam_length_display
        L_norm = 10
        
        ax.plot([0, L_norm], [0, 0], color=self.COLORS['beam'], linewidth=3, solid_capstyle='round')
        ax.plot([0, 0], [-0.3, 0.3], color=self.COLORS['node'], linewidth=2.5)
        ax.plot([L_norm, L_norm], [-0.3, 0.3], color=self.COLORS['node'], linewidth=2.5)
        
        ax.text(0, -0.6, f'i\n(0.00)', ha='center', va='top', fontsize=10, fontweight='bold')
        ax.text(L_norm, -0.6, f'j\n({L_display:.2f})', ha='center', va='top', fontsize=10, fontweight='bold')
        
        fy_i = self.forces[1]
        fy_j = self.forces[7]
        
        self._draw_shear_arrow(ax, 0, fy_i, 'left', L_norm)
        self._draw_shear_arrow(ax, L_norm, -fy_j, 'right', L_norm)
        
        mz_i = self.forces[5]
        mz_j = self.forces[11]
        
        self._draw_moment(ax, 0, mz_i, 'left', L_norm)
        self._draw_moment(ax, L_norm, mz_j, 'right', L_norm)

        ax.set_ylim(-3.5, 3.5)
        ax.set_xlim(-3, L_norm + 3)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(f'Minor Axis Bending - Fy [{self.force_unit}], Mz [{self.moment_unit}]', 
                    fontsize=12, fontweight='bold', pad=20)
        
        figure.tight_layout()
        canvas.draw()

    def add_Major_axis_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        figure = Figure(figsize=(8, 5), dpi=100, facecolor='white')
        canvas = FigureCanvas(figure)
        layout.addWidget(canvas)
        self.tabs.addTab(tab, "Major Axis (M3-V2)")

        if self.forces is None: return

        ax = figure.add_subplot(111)
        
        L_display = self.beam_length_display
        L_norm = 10
        
        ax.plot([0, L_norm], [0, 0], color=self.COLORS['beam'], linewidth=3, solid_capstyle='round')
        ax.plot([0, 0], [-0.3, 0.3], color=self.COLORS['node'], linewidth=2.5)
        ax.plot([L_norm, L_norm], [-0.3, 0.3], color=self.COLORS['node'], linewidth=2.5)
        
        ax.text(0, -0.6, f'i\n(0.00)', ha='center', va='top', fontsize=10, fontweight='bold')
        ax.text(L_norm, -0.6, f'j\n({L_display:.2f})', ha='center', va='top', fontsize=10, fontweight='bold')
        
        fz_i = self.forces[2]
        fz_j = self.forces[8]
        
        self._draw_shear_arrow(ax, 0, fz_i, 'left', L_norm)
        self._draw_shear_arrow(ax, L_norm, fz_j, 'right', L_norm)
        
        my_i = self.forces[4]
        my_j = self.forces[10]
        
        self._draw_moment(ax, 0, my_i, 'left', L_norm)
        self._draw_moment(ax, L_norm, my_j, 'right', L_norm)

        ax.set_ylim(-3.5, 3.5)
        ax.set_xlim(-3, L_norm + 3)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(f'Major Axis Bending - Fz [{self.force_unit}], My [{self.moment_unit}]', 
                    fontsize=12, fontweight='bold', pad=20)
        
        figure.tight_layout()
        canvas.draw()

    def add_torsion_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        figure = Figure(figsize=(8, 4), dpi=100, facecolor='white')
        canvas = FigureCanvas(figure)
        layout.addWidget(canvas)
        self.tabs.addTab(tab, "Torsion (T)")

        if self.forces is None: return

        ax = figure.add_subplot(111)
        
        L_display = self.beam_length_display
        L_norm = 10
        
        ax.plot([0, L_norm], [0, 0], color=self.COLORS['beam'], linewidth=3, solid_capstyle='round')
        ax.plot([0, 0], [-0.3, 0.3], color=self.COLORS['node'], linewidth=2.5)
        ax.plot([L_norm, L_norm], [-0.3, 0.3], color=self.COLORS['node'], linewidth=2.5)
        
        ax.text(0, -0.8, f'i\n(0.00)', ha='center', va='top', fontsize=10, fontweight='bold')
        ax.text(L_norm, -0.8, f'j\n({L_display:.2f})', ha='center', va='top', fontsize=10, fontweight='bold')
        
        mx_i = self.forces[3]
        mx_j = self.forces[9]
        
        self._draw_torsion(ax, 0, mx_i, 'left', L_norm)
        self._draw_torsion(ax, L_norm, mx_j, 'right', L_norm)

        ax.set_ylim(-2, 2)
        ax.set_xlim(-3, L_norm + 3)
        ax.set_aspect('equal')
        ax.axis('off')
        ax.set_title(f'Torsional Moment Diagram (Mx) [{self.moment_unit}]', 
                    fontsize=12, fontweight='bold', pad=20)
        
        figure.tight_layout()
        canvas.draw()

    def _draw_axial_arrow(self, ax, x_pos, force, side, beam_length=10):
        if abs(force) < 0.001:
            return

        arrow_len = 1.2
        y_pos = 0.5

        s = 1 if force > 0 else -1

        if side == 'left':                 
            dx = s * arrow_len
        else:                              
            dx =  s * arrow_len

        ax.arrow(
            x_pos, y_pos,
            dx * 0.85, 0,
            head_width=0.25,
            head_length=0.15,
            fc=self.COLORS['axial'],
            ec=self.COLORS['axial'],
            linewidth=2,
            length_includes_head=True
        )

        ax.text(
            x_pos + dx * 0.5, y_pos + 0.6,
            f'{abs(force):.2f}',
            ha='center', va='bottom', fontsize=10,
            bbox=dict(
                boxstyle='round,pad=0.3',
                facecolor='white',
                edgecolor=self.COLORS['axial'],
                linewidth=1.5
            )
        )

    def _draw_shear_arrow(self, ax, x_pos, force, side, beam_length=10):
        """Draw standard shear force arrow with unit label"""
        if abs(force) < 0.001: return
        
        arrow_len = 1.0
        
        dy = arrow_len if force > 0 else -arrow_len
        
        ax.arrow(x_pos, 0, 0, dy * 0.85,
                head_width=0.2, head_length=0.15,
                fc=self.COLORS['shear'], ec=self.COLORS['shear'],
                linewidth=2, length_includes_head=True)
        
        label_y = dy * 1.2
        label_x = x_pos + (0.7 if side == 'right' else -0.7)
        
        ax.text(label_x, label_y, f'{abs(force):.2f}',
               ha='center', va='center', fontsize=10,
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                        edgecolor=self.COLORS['shear'], linewidth=1.5))

    def _draw_moment(self, ax, x_pos, moment, side, beam_length=10):
        """Draw standard moment with curved arrow and unit label"""
        if abs(moment) < 0.001:
            return

        radius = 0.5
        theta = np.linspace(0, 1.5 * np.pi, 30)

        if moment < 0:
            arc_x = x_pos + radius * np.cos(theta)
            arc_y = radius * np.sin(theta)
        else:
            arc_x = x_pos + radius * np.cos(-theta)
            arc_y = radius * np.sin(-theta)

        ax.plot(arc_x, arc_y, color=self.COLORS['moment'], linewidth=2)

        ax.annotate(
            '',
            xy=(arc_x[-1], arc_y[-1]),
            xytext=(arc_x[-3], arc_y[-3]),
            arrowprops=dict(arrowstyle='->', color=self.COLORS['moment'], lw=2)
        )

        ax.text(
            x_pos, 2.0, f'{abs(moment):.2f}',
            ha='center', va='center', fontsize=10,
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                    edgecolor=self.COLORS['moment'], linewidth=1.5)
        )

    def _draw_torsion(self, ax, x_pos, torque, side, beam_length=10):
        """Draw torsion moment with double-headed arrow and unit label"""
        if abs(torque) < 0.001: return
        
        ax.plot([x_pos, x_pos], [-0.8, 0.8], 
               color=self.COLORS['torsion'], linewidth=2, linestyle='--', alpha=0.6)
        
        theta = np.linspace(0, 2 * np.pi, 20)
        radius = 0.4
        circ_x = x_pos + radius * np.cos(theta)
        circ_y = radius * np.sin(theta)
        
        ax.plot(circ_x, circ_y, color=self.COLORS['torsion'], 
               linewidth=2, linestyle='-', alpha=0.8)
        
        direction = '⟲' if torque > 0 else '⟳'
        ax.text(x_pos, 0, direction, ha='center', va='center',
               fontsize=18, color=self.COLORS['torsion'], fontweight='bold')
        
        label_y = 1.3
        ax.text(x_pos, label_y, f'{abs(torque):.2f}',
               ha='center', va='center', fontsize=10,
               bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                        edgecolor=self.COLORS['torsion'], linewidth=1.5))

    def add_3d_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        figure = Figure(figsize=(8, 6), dpi=100, facecolor='white')
        canvas = FigureCanvas(figure)
        layout.addWidget(canvas)
        self.tabs.addTab(tab, "3D Summary")

        if self.forces is None: return

        ax = figure.add_subplot(111, projection='3d')
        ax.set_proj_type('ortho')
        
        L_norm = 10
        
        ax.plot([0, L_norm], [0, 0], [0, 0], color=self.COLORS['beam'], linewidth=4)
        ax.scatter([0, L_norm], [0, 0], [0, 0], color=self.COLORS['node'], s=100, depthshade=False)
        
        ax.text(L_norm/2, 0, -1, f'L = {self.beam_length_display:.2f} {self.length_unit}',
               ha='center', fontsize=9, color='#555')
        
        force_config = [
            (0, [1,0,0], self.COLORS['axial'], 'Fx', self.force_unit),          
            (1, [0,1,0], self.COLORS['shear'], 'Fy', self.force_unit),            
            (2, [0,0,1], self.COLORS['shear'], 'Fz', self.force_unit),            
        ]
        
        for i, (idx, vec, color, label, unit) in enumerate(force_config):
            for node_offset in [0, 6]:
                force_idx = idx + node_offset
                val = self.forces[force_idx]
                if abs(val) < 0.001: continue
                
                x_pos = L_norm if node_offset == 6 else 0
                scale = 1.5 * (1 if val > 0 else -1)
                
                if idx == 0:               
                    y_offset = 0.8
                                                               
                    if node_offset == 0:             
                        x_start = x_pos - 0.5
                    else:              
                        x_start = x_pos + 0.5
                    
                    ax.quiver(x_start, y_offset, 0, vec[0]*scale, vec[1]*scale, vec[2]*scale,
                             color=color, arrow_length_ratio=0.2, linewidth=2)
                    
                    text_pos = [x_start + vec[0]*scale*1.2, 
                               y_offset + vec[1]*scale*1.2,
                               vec[2]*scale*1.2]
                else:                             
                    ax.quiver(x_pos, 0, 0, vec[0]*scale, vec[1]*scale, vec[2]*scale,
                             color=color, arrow_length_ratio=0.2, linewidth=2)
                    
                    text_pos = [x_pos + vec[0]*scale*1.2, 
                               vec[1]*scale*1.2,
                               vec[2]*scale*1.2]
                
                ax.text(text_pos[0], text_pos[1], text_pos[2],
                       f'{label}\n{abs(val):.1f} {unit}',
                       color=color, fontsize=9, ha='center', fontweight='bold')

        ax.set_xlim(-3, L_norm + 3)
        ax.set_ylim(-2.5, 2.5)
        ax.set_zlim(-2.5, 2.5)
        ax.set_xlabel('X', fontsize=10, fontweight='bold')
        ax.set_ylabel('Y', fontsize=10, fontweight='bold')
        ax.set_zlabel('Z', fontsize=10, fontweight='bold')
        ax.set_title(f'3D Force Summary [{self.force_unit}]', 
                    fontsize=12, fontweight='bold', pad=20)
        
        figure.tight_layout()
        canvas.draw()
