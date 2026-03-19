"""
SolidAnalysisDialog — OpenCivil
================================
Launches SolidResultsViewer as a SUBPROCESS to avoid OpenGL context
conflicts between the main canvas and the viewer on Windows.

Place at:  app/dialogs/solid_analysis_dialog.py
"""

import sys
import os
import pickle
import tempfile
import subprocess

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
                              QLabel, QComboBox, QDoubleSpinBox, QPushButton,
                              QProgressBar, QFrame, QMessageBox)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

_SOLID_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)),
                 '..', '..', 'core', 'solver', 'solid_elements')
)
if _SOLID_DIR not in sys.path:
    sys.path.insert(0, _SOLID_DIR)

_VIEWER_SCRIPT = os.path.join(_SOLID_DIR, 'solid_results_viewer.py')

class MeshWorker(QThread):
    signal_finished = pyqtSignal(bool, object)
    signal_status   = pyqtSignal(str)

    def __init__(self, mf_path, case_name, mesh_size):
        super().__init__()
        self.mf_path, self.case_name, self.mesh_size = mf_path, case_name, mesh_size

    def run(self):
        try:
            import sys, os, traceback
            _dir = os.path.normpath(os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'core', 'solver', 'solid_elements'))
            if _dir not in sys.path: sys.path.insert(0, _dir)
            from solid_main_engine import run_mesh_only
            self.signal_status.emit("Meshing…")
            success, dm = run_mesh_only(self.mf_path, self.case_name, self.mesh_size)
            self.signal_finished.emit(success, dm)
        except Exception as e:
            import traceback; traceback.print_exc()
            self.signal_status.emit(f"Mesh error: {e}")
            self.signal_finished.emit(False, None)

class SolveWorker(QThread):
    signal_finished = pyqtSignal(bool, object, object, object)
    signal_step     = pyqtSignal(str)

    def __init__(self, mf_path, case_name, mesh_size, existing_dm):
        super().__init__()
        self.mf_path, self.case_name = mf_path, case_name
        self.mesh_size, self.existing_dm = mesh_size, existing_dm

    def run(self):
        try:
            import sys, os, traceback
            _dir = os.path.normpath(os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                '..', '..', 'core', 'solver', 'solid_elements'))
            if _dir not in sys.path: sys.path.insert(0, _dir)
            from solid_main_engine import run_solid_analysis
            self.signal_step.emit("Assembling stiffness matrix…")
            success, dm, stress, U = run_solid_analysis(                      
                mf_path=self.mf_path, case_name=self.case_name,
                mesh_size=self.mesh_size, existing_dm=self.existing_dm,
                launch_viewer=False)
            
            self.signal_finished.emit(success, dm, stress, U)
        except Exception as e:
            import traceback; traceback.print_exc()
            self.signal_step.emit(f"Solver error: {e}")
            self.signal_finished.emit(False, None, [], None)

class SolidAnalysisDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window   = main_window
        self.model         = main_window.model
        self._dm           = None
        self._mesh_worker  = None
        self._solve_worker = None
        self._pkl_path     = None                                      

        self.setWindowTitle("Run Solid Element Analysis")
        self.setFixedSize(460, 300)
        self.setModal(False)
        self.setWindowFlags(Qt.WindowType.Window)
        self._build_ui()
        self._populate_load_cases()
        self.main_window.set_interface_state(False)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(14, 14, 14, 14)

        grp = QGroupBox("Analysis Settings")
        gl  = QHBoxLayout(grp); gl.setSpacing(10)
        gl.addWidget(QLabel("Load Case:"))
        self.combo_case = QComboBox(); self.combo_case.setMinimumWidth(120)
        gl.addWidget(self.combo_case)
        gl.addSpacing(10)
        gl.addWidget(QLabel("Mesh Size (m):"))
        self.spin_mesh = QDoubleSpinBox()
        self.spin_mesh.setRange(0.01, 10.0); self.spin_mesh.setValue(0.15)
        self.spin_mesh.setSingleStep(0.05);  self.spin_mesh.setDecimals(3)
        self.spin_mesh.setFixedWidth(120)
        self.spin_mesh.setToolTip("Target edge length for Gmsh tet mesh (m).\nSmaller = finer = slower.")
        gl.addWidget(self.spin_mesh); gl.addStretch()
        root.addWidget(grp)

        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet("QFrame{background:#f5f5f5;border-radius:4px;}")
        fl = QVBoxLayout(frame); fl.setSpacing(3); fl.setContentsMargins(10,8,10,8)
        title = QLabel("Mesh Info"); f = QFont(); f.setBold(True); title.setFont(f)
        fl.addWidget(title)
        self.lbl_nodes = QLabel("Nodes:     —")
        self.lbl_elems = QLabel("Elements:  —")
        self.lbl_dofs  = QLabel("DOFs:      —")
        mono = "color:#333;font-family:Consolas,monospace;font-size:11px;"
        for l in (self.lbl_nodes, self.lbl_elems, self.lbl_dofs):
            l.setStyleSheet(mono); fl.addWidget(l)
        root.addWidget(frame)

        self.progress = QProgressBar()
        self.progress.setRange(0,0); self.progress.setVisible(False)
        self.progress.setFixedHeight(5); self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar{border:none;background:#e0e0e0;border-radius:2px;}
            QProgressBar::chunk{background:#0F62FE;border-radius:2px;}""")
        root.addWidget(self.progress)
        self.lbl_step = QLabel("")
        self.lbl_step.setStyleSheet("color:#666;font-size:10px;")
        root.addWidget(self.lbl_step)
        root.addStretch()

        btn_row = QHBoxLayout()
        self.btn_preview = QPushButton("Create Mesh")
        self.btn_preview.clicked.connect(self._on_preview)
        btn_row.addWidget(self.btn_preview)
        btn_row.addStretch()
        self.btn_run = QPushButton("Run Analysis")
        self.btn_run.setEnabled(False)
        self.btn_run.setStyleSheet("""
            QPushButton{background:#0F62FE;color:white;border:none;
                border-radius:4px;padding:5px 14px;font-weight:600;}
            QPushButton:disabled{background:#b0b0b0;}
            QPushButton:hover{background:#0353e9;}""")
        self.btn_run.clicked.connect(self._on_run)
        btn_row.addWidget(self.btn_run)
        btn_row.addSpacing(6)
        self.btn_close = QPushButton("Close")
        self.btn_close.setFixedWidth(70)
        self.btn_close.clicked.connect(self.close)
        btn_row.addWidget(self.btn_close)
        root.addLayout(btn_row)

    def _populate_load_cases(self):
        self.combo_case.clear()
        for name, lc in sorted(self.model.load_cases.items()):
            if lc.case_type == "Linear Static":
                self.combo_case.addItem(name)

    def _ensure_saved(self):
        path = getattr(self.model, 'file_path', None)
        if not path:
            QMessageBox.warning(self, "Save Required", "Save the model first (File → Save As…).")
            return None
        try:
            self.model.save_to_file(path)
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save:\n{e}")
            return None
        return path

    def _set_busy(self, busy, msg=""):
        self.progress.setVisible(busy)
        self.lbl_step.setText(msg)
        self.btn_preview.setEnabled(not busy)
        self.btn_close.setEnabled(not busy)

    def _on_preview(self):
        mf_path = self._ensure_saved()
        if not mf_path: return
        self._dm = None
        self.btn_run.setEnabled(False)
        self.lbl_nodes.setText("Nodes:     —")
        self.lbl_elems.setText("Elements:  —")
        self.lbl_dofs.setText("DOFs:      —")
        self._set_busy(True, "Building mesh…")
        self._mesh_worker = MeshWorker(mf_path, self.combo_case.currentText(),
                                       self.spin_mesh.value())
        self._mesh_worker.signal_status.connect(self.lbl_step.setText)
        self._mesh_worker.signal_finished.connect(self._on_preview_done)
        self._mesh_worker.start()

    def _on_preview_done(self, success, dm):
        self._set_busy(False)
        if not success or dm is None:
            QMessageBox.warning(self, "Mesh Failed", "Could not generate mesh.\nCheck console.")
            self.lbl_step.setText("Mesh failed.")
            return
        self._dm = dm
        self.lbl_nodes.setText(f"Nodes:     {len(dm.nodes):,}")
        self.lbl_elems.setText(f"Elements:  {len(dm.elements):,}  (Tet10)")
        self.lbl_dofs.setText(f"DOFs:      {dm.total_dofs:,}")
        self.lbl_step.setText("Mesh ready — click  Run Analysis  to solve.")
        self.btn_run.setEnabled(True)

    def _on_run(self):
        if self._dm is None:
            QMessageBox.warning(self, "No Mesh", "Run  ▶ Create Mesh  first."); return

        dofs = self._dm.total_dofs
        if dofs >= 1_000_000:
            QMessageBox.critical(self, "Model Too Large",
                f"This mesh has {dofs:,} DOFs — analysis is blocked above 1,000,000 DOFs.\n"
                f"Increase the mesh size and re-mesh.")
            return
        elif dofs >= 500_000:
            reply = QMessageBox.question(self, "Very Large Model",
                f"This mesh has {dofs:,} DOFs.\nAnalysis may take several hours. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes: return
        elif dofs >= 200_000:
            reply = QMessageBox.question(self, "Large Model",
                f"This mesh has {dofs:,} DOFs.\nAnalysis may take a few minutes. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes: return

        mf_path = self._ensure_saved()
        if not mf_path: return
        self._set_busy(True, "Solving…")
        self.btn_run.setEnabled(False)
        self._solve_worker = SolveWorker(mf_path, self.combo_case.currentText(),
                                         self.spin_mesh.value(), self._dm)
        self._solve_worker.signal_step.connect(self.lbl_step.setText)
        self._solve_worker.signal_finished.connect(self._on_solve_done)
        self._solve_worker.start()

    def _on_solve_done(self, success, dm, stress_results, U):
        self._set_busy(False)
        if not success:
            QMessageBox.critical(self, "Analysis Failed", "Solid FEM failed.\nCheck console.")
            self.btn_run.setEnabled(True)
            return

        self.lbl_step.setText("Done — launching viewer…")
        self.main_window.set_interface_state(True)

        try:
                                                                        
            import numpy as np
            data = {
                'nodes':         dm.nodes,
                'elements':      dm.elements,
                'total_dofs':    dm.total_dofs,
                'stress_results': stress_results,
                'U_full': U,
            }
            tmp = tempfile.NamedTemporaryFile(suffix='.pkl', delete=False)
            pickle.dump(data, tmp, protocol=pickle.HIGHEST_PROTOCOL)
            tmp.close()
            self._pkl_path = tmp.name

            if getattr(sys, 'frozen', False):
                subprocess.Popen([sys.executable, self._pkl_path], close_fds=True)
            else:
                subprocess.Popen([sys.executable, _VIEWER_SCRIPT, self._pkl_path], close_fds=True)
            self.close()

        except Exception as e:
            import traceback; traceback.print_exc()
            QMessageBox.warning(self, "Viewer Error", f"Could not launch viewer:\n{e}")

    def closeEvent(self, event):
        if ((self._mesh_worker  and self._mesh_worker.isRunning()) or
                (self._solve_worker and self._solve_worker.isRunning())):
            QMessageBox.information(self, "Busy", "Wait for the operation to finish.")
            event.ignore(); return

        self.main_window.set_interface_state(True)
        event.accept()
