import sys
import os
import io
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QLineEdit, QTextEdit, 
                             QApplication, QMessageBox, QGroupBox, QWidget, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QCursor

# --- PATH ROUTING ---
current_dir = os.path.dirname(os.path.abspath(__file__))
solid_solver_dir = os.path.abspath(os.path.join(current_dir, '..', '..', 'core', 'solver', 'solid_elements'))
if solid_solver_dir not in sys.path:
    sys.path.append(solid_solver_dir)

from solid_main_engine import run_mesh_only, run_solid_analysis, run_submodel_analysis


class StreamRedirector(io.StringIO):
    def __init__(self, text_widget, original_stdout):
        super().__init__()
        self.text_widget = text_widget
        self.original_stdout = original_stdout

    def write(self, text):
        # 1. Always write to the real terminal first.
        self.original_stdout.write(text)
        self.original_stdout.flush()

        # 2. Post to the GUI thread safely from ANY thread.
        #
        #    *** BUG FIX ***
        #    The old code used QTimer.singleShot() here, which SILENTLY FAILS
        #    when called from a QThread because worker threads have no event
        #    loop of their own.  QMetaObject.invokeMethod with QueuedConnection
        #    is the correct cross-thread GUI update path — it posts directly to
        #    the main thread's event queue regardless of the calling thread.
        if text.strip():
            from PyQt6.QtCore import QMetaObject, Q_ARG
            QMetaObject.invokeMethod(
                self.text_widget,
                "append",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, text.strip()),
            )

    def flush(self):
        self.original_stdout.flush()


class SolidAnalysisWorker(QThread):
    finished = pyqtSignal(bool, object, list, object)

    def __init__(self, mf_path, case_name, mesh_size, mode="full", selected_ids=None):
        super().__init__()
        self.mf_path = mf_path
        self.case_name = case_name
        self.mesh_size = mesh_size
        self.mode = mode
        self.selected_ids = selected_ids

    def run(self):
        try:
            if self.mode == "mesh_only":
                success, dm = run_mesh_only(self.mf_path, self.case_name, self.mesh_size)
                self.finished.emit(success, dm, [], None)
            elif self.mode == "submodel":
                success, dm, stresses, U = run_submodel_analysis(
                    self.mf_path, self.selected_ids, self.case_name, self.mesh_size, launch_viewer=False
                )
                self.finished.emit(success, dm, stresses, U)
            else:
                success, dm, stresses, U = run_solid_analysis(
                    self.mf_path, self.case_name, self.mesh_size, launch_viewer=False
                )
                self.finished.emit(success, dm, stresses, U)
        except Exception as e:
            print(f"Worker Error: {e}")
            self.finished.emit(False, None, [], None)


class SolidAnalysisDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.setWindowTitle("OpenCivil — Solid FEM Engine")
        self.setMinimumWidth(650)
        self.setMinimumHeight(550)

        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #CCCCCC;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #FFFFFF;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                color: #333333;
            }
        """)

        self._build_ui()

        self._original_stdout = sys.stdout
        self._redirector = StreamRedirector(self.log_output, self._original_stdout)
        sys.stdout = self._redirector

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # --- Group 1: Configuration ---
        config_group = QGroupBox("Engine Configuration")
        config_layout = QHBoxLayout()
        config_layout.setSpacing(20)

        case_container = QVBoxLayout()
        case_container.addWidget(QLabel("Target Load Case:"))
        self.cmb_cases = QComboBox()
        self.cmb_cases.setMinimumHeight(28)
        self._populate_cases()
        case_container.addWidget(self.cmb_cases)
        config_layout.addLayout(case_container)

        mesh_container = QVBoxLayout()
        mesh_container.addWidget(QLabel("Tetra Mesh Size (m):"))
        self.txt_mesh_size = QLineEdit("0.15")
        self.txt_mesh_size.setMinimumHeight(28)
        self.txt_mesh_size.setFixedWidth(120)
        self.txt_mesh_size.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mesh_container.addWidget(self.txt_mesh_size)
        config_layout.addLayout(mesh_container)

        config_layout.addStretch()
        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group, stretch=0)

        # --- Group 2: Action Dashboard ---
        action_group = QGroupBox("Execution Dashboard")
        action_layout = QHBoxLayout()
        action_layout.setSpacing(10)

        self.btn_preview = QPushButton("Preview Mesh")
        self.btn_preview.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_preview.clicked.connect(self._on_preview_clicked)

        self.btn_run = QPushButton("Run Full Solid Analysis")
        self.btn_run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #D6E9FF;
                color: #003A75;
                border: 1px solid #A8CFFF;
                padding: 5px;
            }
            QPushButton:hover { background-color: #C4E0FF; }
        """)
        self.btn_run.clicked.connect(self._on_run_clicked)

        self.btn_submodel = QPushButton("Analyze Subsection")
        self.btn_submodel.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_submodel.setStyleSheet("""
            QPushButton {
                background-color: #EEEEEE;
                color: #333333;
                border: 1px solid #CCCCCC;
                padding: 5px;
            }
            QPushButton:hover { background-color: #E0E0E0; }
        """)
        self.btn_submodel.clicked.connect(self._on_submodel_clicked)

        action_layout.addWidget(self.btn_preview)
        action_layout.addWidget(self.btn_submodel)
        action_layout.addWidget(self.btn_run)
        action_group.setLayout(action_layout)
        main_layout.addWidget(action_group, stretch=0)

        # --- Console Output ---
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setFont(QFont("Consolas", 10))
        self.log_output.setFrameShape(QFrame.Shape.StyledPanel)
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: #FFFFFF;
                color: #000000;
                border: 1px solid #CCCCCC;
                border-radius: 4px;
                padding: 5px;
            }
        """)
        main_layout.addWidget(self.log_output, stretch=1)

        # --- Bottom Close Button ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_close = QPushButton("Close Viewer")
        self.btn_close.setFixedWidth(120)
        self.btn_close.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout, stretch=0)

    def _populate_cases(self):
        try:
            model = self.main_window.model
            if model is not None:
                cases = [c['name'] for c in model.raw.get('load_cases', [])]
                if cases:
                    self.cmb_cases.addItems(cases)
                    return
        except Exception:
            pass
        self.cmb_cases.addItem("DEAD")

    def _get_params(self):
        case = self.cmb_cases.currentText()
        try:
            ms = float(self.txt_mesh_size.text())
        except ValueError:
            ms = 0.15
        return case, ms

    def _set_ui_enabled(self, enabled):
        self.btn_preview.setEnabled(enabled)
        self.btn_run.setEnabled(enabled)
        self.btn_submodel.setEnabled(enabled)
        self.btn_close.setEnabled(enabled)
        self.cmb_cases.setEnabled(enabled)
        self.txt_mesh_size.setEnabled(enabled)

    # --- BUTTON SLOTS ---

    def _on_preview_clicked(self):
        case, ms = self._get_params()
        self._run_worker(mode="mesh_only", case=case, ms=ms)

    def _on_run_clicked(self):
        case, ms = self._get_params()
        self._run_worker(mode="full", case=case, ms=ms)

    def _on_submodel_clicked(self):
        case, ms = self._get_params()

        selected_elements = list(getattr(self.main_window, 'selected_ids', []))
        if not selected_elements:
            QMessageBox.warning(self, "No Selection",
                                "Please select frame elements in the 3D viewport first!")
            return

        model = self.main_window.model
        if not model or not model.file_path:
            QMessageBox.warning(self, "No File",
                                "Please save your model first before running solid analysis.")
            return

        results_path = model.file_path.replace(".mf", f"_{case}_results.json")
        if not os.path.exists(results_path):
            QMessageBox.warning(
                self, "Missing Global Results",
                f"Run the Linear Static solver for case '{case}' first.\n"
                f"Expected results at:\n{results_path}"
            )
            return

        self._run_worker(mode="submodel", case=case, ms=ms, selected_ids=selected_elements)

    def _run_worker(self, mode, case, ms, selected_ids=None):
        model = self.main_window.model
        if not model or not model.file_path:
            print("Error: No active .mf file saved. Save model first.")
            return
        if not os.path.exists(model.file_path):
            print(f"Error: File not found at {model.file_path}")
            return

        self.log_output.clear()
        self._set_ui_enabled(False)

        self.worker = SolidAnalysisWorker(model.file_path, case, ms, mode=mode, selected_ids=selected_ids)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_finished(self, success, dm, stresses, U):
        self._set_ui_enabled(True)

        if not success or not dm:
            print("\nAnalysis failed or cancelled.")
            return

        print("\nAnalysis complete. Preparing OpenCivil Solid Viewer...")

        # *** BUG FIX: OpenGL context crash ***
        #
        # Root cause: pyqtgraph's GLViewWidget acquires the GL context during
        # its first paintGL().  If a parent widget (this dialog) still holds an
        # active GL context at that moment, Qt cannot share it and returns None,
        # causing "AttributeError: 'NoneType' object has no attribute
        # 'hasExtension'" inside GLMeshItem.paint().
        #
        # Fix: hide the dialog BEFORE the viewer window is created and shown.
        # The dialog's own GL resources are released when it becomes invisible,
        # leaving the context free for the viewer to claim exclusively.
        # We restore the dialog after the viewer closes via a finished signal.
        self.hide()

        from PyQt6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self._launch_viewer(dm, stresses, U))

    def _launch_viewer(self, dm, stresses, U):
        try:
            from solid_results_viewer import SolidResultsViewer
            self.viewer = SolidResultsViewer(dm, stresses, U_full=U)

            icon_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), '..', '..', '..', 'graphic', 'logo.png')
            )
            if os.path.exists(icon_path):
                from PyQt6.QtGui import QIcon
                self.viewer.setWindowIcon(QIcon(icon_path))

            # Re-show the dialog when the viewer window is closed so the user
            # can run further analyses without reopening the dialog.
            self.viewer.destroyed.connect(self.show)

            self.viewer.show()
        except Exception as e:
            # If viewer fails, make sure the dialog comes back
            self.show()
            print(f"Viewer Error: {e}")

    def closeEvent(self, event):
        sys.stdout = self._original_stdout
        event.accept()