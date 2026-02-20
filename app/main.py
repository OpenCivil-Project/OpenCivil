import sys
import os
import ctypes
import time
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QPixmap,QCursor, QVector3D, QColor, QIcon
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QWidget, 
                             QMessageBox, QFileDialog, QSplashScreen, QLabel, 
                             QComboBox,QProgressBar, QProgressDialog)
from PyQt6.QtWidgets import QMenu
from PyQt6.QtGui import QCursor
from PyQt6.QtGui import QUndoStack  
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput, QMediaDevices, QSoundEffect
from PyQt6.QtCore import QUrl
from PyQt6.QtMultimediaWidgets import QVideoWidget  
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtCore import QUrl, pyqtSignal

if getattr(sys, 'frozen', False):

    if hasattr(sys, '_MEIPASS'):
        root_dir = sys._MEIPASS
    else:
        root_dir = os.path.dirname(sys.executable)

    current_dir = root_dir 
else:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)

sys.path.append(root_dir)

from app.commands import CmdDrawFrame, CmdDeleteSelection, CmdReplicate
from core.model import StructuralModel, LoadCase
from app.canvas import MCanvas3D
from app.dialogs.new_model_dialog import NewModelDialog
from app.dialogs.material_dialog import MaterialManagerDialog
from app.dialogs.section_dialog import SectionManagerDialog
from app.dialogs.draw_dialog import DrawFrameDialog
from app.dialogs.restraint_dialog import RestraintDialog
from app.dialogs.load_pattern_dialog import LoadPatternDialog
from app.dialogs.assign_load_dialog import AssignJointLoadDialog
from app.dialogs.assign_member_load_dialog import AssignFrameLoadDialog
from app.dialogs.release_dialog import FrameReleaseDialog
from app.dialogs.view_options_dialog import ViewOptionsDialog
from app.dialogs.assign_local_axis_dialog import AssignFrameAxisDialog
from app.dialogs.graphics_dialog import GraphicsOptionsDialog
from app.dialogs.element_info_dialog import ElementInfoDialog
from core.units import unit_registry
from app.dialogs.assign_frame_point_load_dialog import AssignFramePointLoadDialog
from app.dialogs.load_case_dialog import LoadCaseManagerDialog
from app.dialogs.analysis_dialog import AnalysisDialog
from app.solver_worker import SolverWorker
from app.dialogs.spy_dialogs import MatrixSpyDialog, FBDViewerDialog
from app.dialogs.deformed_shape_dialog import DeformedShapeDialog
from app.dialogs.mass_source_dialog import MassSourceManagerDialog
from app.dialogs.modal_results_dialog import ModalResultsDialog
from auth import GoogleAuthManager, UserProfileWidget

class OPENCIVILSplash(QSplashScreen):
    def __init__(self, pixmap):
        super().__init__(pixmap)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        
        w = pixmap.width()
        h = pixmap.height()
        bar_height = 10 
        
        self.label_status = QLabel(self)
        self.label_status.setGeometry(20, h - bar_height - 35, w - 40, 30) 
        self.label_status.setText("Initializing...")
        
        self.label_status.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-family: 'Segoe UI', sans-serif;
                font-size: 14px; 
                font-weight: 600;
                background-color: transparent;
            }
        """)

        self.progressBar = QProgressBar(self)
        self.progressBar.setGeometry(0, h - bar_height, w, bar_height)
        self.progressBar.setStyleSheet("""
            QProgressBar {
                border: none;
                background-color: #1e1e1e;
            }
            QProgressBar::chunk {
                background-color: #0078D7; 
            }
        """)
        self.progressBar.setTextVisible(False) 
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)

    def progress(self, value, message=None):
        self.progressBar.setValue(value)
        if message:
            self.label_status.setText(message)
                         
        QApplication.processEvents()

class VideoSplash(QWidget):
                                                     
    finished = pyqtSignal()

    def __init__(self, video_path):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        
        self.resize(800, 450) 
                          
        self.center_on_screen()

        self.video_widget = QVideoWidget(self)
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()

        self.player.setVideoOutput(self.video_widget)
        self.player.setAudioOutput(self.audio_output)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.video_widget)

        self.player.setSource(QUrl.fromLocalFile(video_path))
        self.audio_output.setVolume(0.7)

        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
                                                                
        self.player.errorOccurred.connect(self.finished.emit)

    def start(self):
        self.player.play()

    def on_media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.finished.emit()

    def center_on_screen(self):
        qr = self.frameGeometry()
        cp = QApplication.primaryScreen().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft()) 

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.model = None 

        self.undo_stack = QUndoStack(self)

        self.graphics_settings = {
            "background_color": (1.0, 1.0, 1.0, 1.0), 
            "antialias": True,
            "node_size": 6,
            "node_color": (1.0, 1.0, 0.0, 1.0),       
            "line_width": 2.0,
            "extrude_opacity": 0.35,
            "show_edges": False,
            "msaa_level": 2,
            "edge_width": 1.5,
            "edge_color": (0.0, 0.0, 0.0, 1.0),      
            "slab_opacity": 0.4
        }
        
        self.setWindowTitle("OPENCIVIL Analysis Engine")
        self.resize(1200, 800)

        icon_path = os.path.join(root_dir, "graphic", "logo.png") 
        
        if not os.path.exists(icon_path):
             icon_path = os.path.join(current_dir, "logo.ico")

        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.draw_mode_active = False
        self.draw_start_node = None 
        self.draw_dialog = None 
        self.selected_ids = []
        self.selected_node_ids = []
        
        self.picking_replicate = False 
        self.replicate_p1 = None      
        self.replicate_dialog = None

        self.current_view_mode = "3D"
        self.current_grid_index = 0

        self.sound_effect = QSoundEffect()
        
        self.sound_effect.setLoopCount(QSoundEffect.Loop.Infinite.value) 
        
        self.sound_effect.setVolume(0.5) 

        sound_path = os.path.join(root_dir, "graphic", "animation_loop.wav")
        if os.path.exists(sound_path):
            self.sound_effect.setSource(QUrl.fromLocalFile(sound_path))
        else:
            print(f"Warning: Sound file not found at {sound_path}")

        self.init_ui()
        self.set_interface_state(False)
    
    def init_ui(self):
        """Organizes all UI components"""
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        
        new_action = QAction("New Model...", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.on_new_model)
        file_menu.addAction(new_action)
        
        open_action = QAction("Open...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.on_open_model)
        file_menu.addAction(open_action)

        self.action_save = QAction("Save As...", self)
        self.action_save.setShortcut("Ctrl+S")
        self.action_save.triggered.connect(self.on_save_model)
        file_menu.addAction(self.action_save)
        
        file_menu.addSeparator()

        self.menu_edit = menubar.addMenu("Edit")

        undo_action = self.undo_stack.createUndoAction(self, "Undo")
        undo_action.setShortcut("Ctrl+Z")
        self.menu_edit.addAction(undo_action)

        redo_action = self.undo_stack.createRedoAction(self, "Redo")
        redo_action.setShortcut("Ctrl+Y")                                          
        self.menu_edit.addAction(redo_action)
        
        self.menu_edit.addSeparator()

        rep_action = QAction("Replicate...", self)
        rep_action.setShortcut("Ctrl+R") 
        rep_action.triggered.connect(self.on_edit_replicate)
        self.menu_edit.addAction(rep_action)

        merge_action = QAction("Merge Joints...", self)
        merge_action.triggered.connect(self.on_edit_merge)
        self.menu_edit.addAction(merge_action)

        self.menu_define = menubar.addMenu("Define")
        mat_action = QAction("Material Properties...", self)
        mat_action.triggered.connect(self.on_define_materials)
        self.menu_define.addAction(mat_action)
        
        sec_action = QAction("Section Properties...", self)
        sec_action.triggered.connect(self.on_define_sections) 
        self.menu_define.addAction(sec_action)

        mass_action = QAction("Mass Source...", self)
        mass_action.triggered.connect(self.on_define_mass_source)
        self.menu_define.addAction(mass_action)

        load_pat_action = QAction("Load Patterns...", self)
        load_pat_action.triggered.connect(self.on_define_load_patterns)
        self.menu_define.addAction(load_pat_action)

        load_case_action = QAction("Load Cases...", self)
        load_case_action.triggered.connect(self.on_define_load_cases)
        self.menu_define.addAction(load_case_action)

        self.menu_functions = self.menu_define.addMenu("Functions")
        
        rsa_action = QAction("Response Spectrum...", self)
        rsa_action.triggered.connect(self.on_define_response_spectrum)
        self.menu_functions.addAction(rsa_action)
        
        self.menu_define.addSeparator()
        
        self.menu_draw = menubar.addMenu("Draw")
        draw_action = QAction("Draw Frame/Cable...", self)
        draw_action.triggered.connect(self.on_draw_frame)
        self.menu_draw.addAction(draw_action)
        
        draw_slab_action = QAction("Create Slab from Selection", self)
        draw_slab_action.triggered.connect(self.on_create_slab_from_selection)
        self.menu_draw.addAction(draw_slab_action)

        self.toolbar = self.addToolBar("Views")
        
        btn_iso = QAction("🕶️ ISO", self)
        btn_iso.triggered.connect(self.set_view_iso) 
        self.toolbar.addAction(btn_iso)

        self.toolbar.addSeparator()

        btn_3d = QAction("3D", self)
        btn_3d.triggered.connect(self.set_view_3d)
        self.toolbar.addAction(btn_3d)
        
        self.toolbar.addSeparator()

        btn_xy = QAction("XY", self)
        btn_xy.triggered.connect(lambda: self.set_view_2d("XY"))
        self.toolbar.addAction(btn_xy)

        btn_xz = QAction("XZ", self)
        btn_xz.triggered.connect(lambda: self.set_view_2d("XZ"))
        self.toolbar.addAction(btn_xz)
        
        btn_yz = QAction("YZ", self)
        btn_yz.triggered.connect(lambda: self.set_view_2d("YZ"))
        self.toolbar.addAction(btn_yz)

        self.toolbar.addSeparator()

        self.btn_up = QAction("▲ Up", self)
        self.btn_up.triggered.connect(lambda: self.move_view_layer(1))
        self.toolbar.addAction(self.btn_up)
        
        self.btn_down = QAction("▼ Down", self)
        self.btn_down.triggered.connect(lambda: self.move_view_layer(-1))
        self.toolbar.addAction(self.btn_down)

        self.toolbar.addSeparator()
        self.btn_lock = QAction("🔓", self)
        self.btn_lock.setToolTip("Click to Unlock Model and Discard Results")
        self.btn_lock.triggered.connect(self.on_lock_clicked)
        self.toolbar.addAction(self.btn_lock)

        self.toolbar.addSeparator()

        self.btn_deform = QAction("Deformed Shape", self)
        self.btn_deform.setToolTip("Show/Hide Deformed Shape (Results Mode Only)")
        self.btn_deform.triggered.connect(self.on_view_deformed_shape)
                                                
        self.btn_deform.setEnabled(False) 
                                                
        self.toolbar.addSeparator()

        self.btn_opts = QAction("Display", self) 
        self.btn_opts.setShortcut("Ctrl+W")
        self.btn_opts.triggered.connect(self.on_view_options)
        self.toolbar.addAction(self.btn_opts)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        self.canvas = MCanvas3D()
        self.layout.addWidget(self.canvas)

        self.menu_assign = menubar.addMenu("Assign")
        
        joint_menu = self.menu_assign.addMenu("Joint")
        
        restraint_action = QAction("Restraints...", self)
        restraint_action.triggered.connect(self.on_assign_restraints)
        joint_menu.addAction(restraint_action)

        constraint_action = QAction("Diaphragms / Constraints...", self)
        constraint_action.triggered.connect(self.on_assign_constraints)
        joint_menu.addAction(constraint_action)

        load_action = QAction("Forces...", self)
        load_action.triggered.connect(self.on_assign_joint_load)
        joint_menu.addAction(load_action)

        frame_menu = self.menu_assign.addMenu("Frame")

        frame_point_action = QAction("Point Loads...", self)
        frame_point_action.triggered.connect(self.on_assign_frame_point_load)
        frame_menu.addAction(frame_point_action)

        frame_load_action = QAction("Distributed Loads...", self)
        frame_load_action.triggered.connect(self.on_assign_frame_load)
        frame_menu.addAction(frame_load_action)

        frame_rel_action = QAction("Releases & Partial Fixity...", self)
        frame_rel_action.triggered.connect(self.on_assign_releases)
        frame_menu.addAction(frame_rel_action)

        ins_point_action = QAction("Insertion Point...", self)
        ins_point_action.triggered.connect(self.on_assign_insertion_point)
        frame_menu.addAction(ins_point_action)

        end_offset_action = QAction("End Length Offsets...", self)
        end_offset_action.triggered.connect(self.on_assign_end_offsets)
        frame_menu.addAction(end_offset_action)

        local_axis_action = QAction("Local Axes...", self)
        local_axis_action.triggered.connect(self.on_assign_local_axis)
        frame_menu.addAction(local_axis_action)

        self.menu_analyze = menubar.addMenu("Analyze")

        self.run_action = QAction("Run Analysis...", self)
        self.run_action.setShortcut("F5") 
        self.run_action.triggered.connect(self.on_run_analysis_dialog)
        self.menu_analyze.addAction(self.run_action)

        self.menu_analyze.addAction(self.btn_deform)

        self.menu_analyze.addSeparator()
        self.res_action = QAction("Show Result Tables...", self)
        self.res_action.triggered.connect(self.on_show_modal_results)
        self.menu_analyze.addAction(self.res_action)

        self.menu_options = menubar.addMenu("Options")
        
        gfx_action = QAction("Graphics Preferences...", self)
        gfx_action.triggered.connect(self.on_graphics_options)
        self.menu_options.addAction(gfx_action)

        self.canvas.signal_canvas_clicked.connect(self.handle_canvas_click) 
        self.canvas.signal_right_clicked.connect(self.handle_right_click) 
        self.canvas.signal_box_selection.connect(self.handle_box_selection)
        self.canvas.signal_mouse_moved.connect(self.on_mouse_moved)
        
        self.setup_statusbar()

    def on_mouse_moved(self, x, y, z):
        self.lbl_coords.setText(f"X: {x:.2f}  Y: {y:.2f}  Z: {z:.2f}")

    def setup_statusbar(self):
        
        self.status = self.statusBar()
        self.status.showMessage("Welcome. Please create or open a model.")
        
        self.lbl_coords = QLabel("X: 0.00  Y: 0.00  Z: 0.00")
        self.lbl_coords.setStyleSheet("padding-right: 15px; color: #333;")
        self.status.addPermanentWidget(self.lbl_coords)

        self.combo_units = QComboBox()
        self.combo_units.addItems([
            "kN, m, C", 
            "N, m, C", 
            "N, mm, C", 
            "kN, mm, C",
            "Tonf, m, C",
            "kgf, m, C",
            "kip, ft, F"
        ])
                          
        self.combo_units.setCurrentIndex(0)
        self.combo_units.setToolTip("Global Display Units")
        
        self.combo_units.currentIndexChanged.connect(self.on_units_changed)
        
        self.status.addPermanentWidget(self.combo_units)

    def set_interface_state(self, editable: bool):
        """
        editable = True:  PRE-PROCESSING (Draw, Assign, Edit enabled).
        editable = False: POST-PROCESSING (Locked. Only View & Info enabled).
        """
                                                               
        self.menu_define.setEnabled(editable)
        self.menu_draw.setEnabled(editable)
        self.menu_assign.setEnabled(editable)
        self.run_action.setEnabled(editable)
        self.res_action.setEnabled(not editable)

        if hasattr(self, 'menu_edit'):
            self.menu_edit.setEnabled(editable)
        
        if not editable:
                                   
            self.canvas.setBackgroundColor('#F8F9FA')                  
            self.status.showMessage("Model Locked. Results Mode.")
        else:
                       
            bg_tuple = self.graphics_settings.get("background_color", (1.0, 1.0, 1.0, 1.0))
            c = QColor()
            c.setRgbF(bg_tuple[0], bg_tuple[1], bg_tuple[2], bg_tuple[3])
            self.canvas.setBackgroundColor(c)
            self.status.showMessage("Model Unlocked. Ready to edit.")

    def on_units_changed(self, index):
        unit_text = self.combo_units.currentText()
        
        unit_registry.set_unit_system(unit_text)
        
        self.status.showMessage(f"Units changed to: {unit_text}")
        
        if self.model:
            self.canvas.draw_model(self.model, self.selected_ids, self.selected_node_ids)

    def set_view_3d(self):
        self.current_view_mode = "3D"
        self.canvas.active_view_plane = None 
        self.canvas.set_standard_view("3D")  
        if self.model: self.canvas.draw_model(self.model, self.selected_ids, self.selected_node_ids)
        self.status.showMessage("View: Full 3D")

    def set_view_2d(self, axis):
        self.current_view_mode = axis
        self.current_grid_index = 0
        self.update_view_layer()

    def move_view_layer(self, direction):
        if self.current_view_mode == "3D": return
        self.current_grid_index += direction
        self.update_view_layer()

    def update_view_layer(self):
        grids = self.model.grid
        if self.current_view_mode == "XY":
            grid_list = grids.z_grids; axis = 'z'
        elif self.current_view_mode == "XZ":
            grid_list = grids.y_grids; axis = 'y'
        elif self.current_view_mode == "YZ":
            grid_list = grids.x_grids; axis = 'x'
        else: return

        if not grid_list: return 

        self.current_grid_index = max(0, min(self.current_grid_index, len(grid_list) - 1))
        val = grid_list[self.current_grid_index]
        self.canvas.active_view_plane = {'axis': axis, 'value': val}
        if self.model: self.canvas.draw_model(self.model, self.selected_ids, self.selected_node_ids)
        self.status.showMessage(f"Filtered View: {self.current_view_mode} @ {axis.upper()}={val:.2f}m")

    def set_view_iso(self):
        self.current_view_mode = "3D"
        self.canvas.active_view_plane = None
        self.canvas.set_standard_view("ISO") 
        if self.model: self.canvas.draw_model(self.model, self.selected_ids, self.selected_node_ids)
        self.status.showMessage("View: Orthogonal Isometric")  

    def on_new_model(self):
        dialog = NewModelDialog(self)
        if dialog.exec(): 
            if dialog.accepted_data:
                data = dialog.grid_data
                self.model = StructuralModel("New Project")
                self.undo_stack.clear()

                if not hasattr(self.model, 'mass_sources'):
                    self.model.mass_sources = {}
                                              
                    from core.model import MassSource
                    def_ms = MassSource("MSSSRC1")
                    self.model.mass_sources["MSSSRC1"] = def_ms
                    self.model.active_mass_source = "MSSSRC1"
                    
                self.model.file_path = None
                self.model.grid.create_uniform('x', 0.0, data['x_num'] - 1, data['x_dist'])
                self.model.grid.create_uniform('y', 0.0, data['y_num'] - 1, data['y_dist'])
                self.model.grid.create_uniform('z', 0.0, data['z_num'] - 1, data['z_dist'])   
                self.combo_units.blockSignals(True)
                self.combo_units.setCurrentText(dialog.selected_units)
                self.combo_units.blockSignals(False)

                self.on_units_changed(0) 

                self.model.functions = {
                    "FUNC1": {
                        "name": "FUNC1", "type": "TSC-2018", 
                        "Ss": 1.5, "S1": 0.4, "SiteClass": "ZC", 
                        "R": 8.0, "D": 3.0, "I": 1.0, "TL": 6.0
                    }
                }
                
                rsa_case = LoadCase("RSA_X", "Response Spectrum")
                rsa_case.function = "FUNC1"
                rsa_case.direction = "X"
                self.model.load_cases["RSA_X"] = rsa_case

                self.set_interface_state(True)
                self.canvas.draw_model(self.model)
                self.status.showMessage(f"New Model Created. Units: {dialog.selected_units}")
                self.update_window_title()

    def on_open_model(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Open Model", "", "OPENCIVIL Files (*.mf);;All Files (*)")
        if filename:
            try:
                                   
                if self.model is None:
                    self.model = StructuralModel("Loaded Project")
                                 
                self.model.load_from_file(filename)
                self.undo_stack.clear()
                self.model.file_path = filename

                if self.model.graphics_settings:
                                                                 
                    self.graphics_settings.update(self.model.graphics_settings)
                    
                    self.update_graphics_settings(self.graphics_settings)

                    self.canvas.view_extruded = self.graphics_settings.get('view_extruded', False)
                    self.canvas.show_slabs = self.graphics_settings.get('show_slabs', True)
                    self.canvas.show_joints = self.graphics_settings.get('show_joints', True)
                    self.canvas.show_supports = self.graphics_settings.get('show_supports', True)
                    self.canvas.show_loads = self.graphics_settings.get('show_loads', True)
                    self.canvas.show_local_axes = self.graphics_settings.get('show_local_axes', False)

                if hasattr(self.model, 'saved_unit_system'):
                    self.combo_units.blockSignals(True)
                    self.combo_units.setCurrentText(self.model.saved_unit_system)
                    self.combo_units.blockSignals(False)
                    self.on_units_changed(0) 
                
                self.canvas.draw_model(self.model)
                self.status.showMessage(f"Loaded: {filename}")
                self.canvas.set_standard_view("3D")
                self.set_interface_state(True) 
                self.update_window_title()
                
            except Exception as e:
                QMessageBox.critical(self, "Load Error", f"Corrupt file or version mismatch.\n{e}")
                
    def on_save_model(self):
        if not self.model: 
            return False                               

        current_path = getattr(self.model, 'file_path', None)
        
        if current_path:
            filename = current_path
        else:
            filename, _ = QFileDialog.getSaveFileName(self, "Save Model", "", "OPENCIVIL Files (*.mf);;All Files (*)")

        if filename:
            if not filename.endswith(".mf"): filename += ".mf"
            try:
                self.model.graphics_settings = self.graphics_settings

                self.graphics_settings['view_extruded'] = self.canvas.view_extruded
                self.graphics_settings['show_slabs'] = self.canvas.show_slabs
                self.graphics_settings['show_joints'] = self.canvas.show_joints
                self.graphics_settings['show_supports'] = self.canvas.show_supports
                self.graphics_settings['show_loads'] = self.canvas.show_loads
                self.graphics_settings['show_local_axes'] = self.canvas.show_local_axes
                self.model.graphics_settings = self.graphics_settings

                self.model.save_to_file(filename)
                self.model.file_path = filename
                
                self.undo_stack.setClean() 
                                            
                self.status.showMessage(f"Saved: {filename}")
                self.update_window_title()
                return True          
            except Exception as e:
                QMessageBox.critical(self, "Save Error", str(e))
                return False
        
        return False                 

    def on_define_materials(self):
        if not self.model: return
        dialog = MaterialManagerDialog(self.model, self)
        dialog.exec()

    def on_define_sections(self):
        if not self.model: return
        dialog = SectionManagerDialog(self.model, self)
        dialog.exec()
        self.canvas.draw_model(self.model)

    def on_define_load_patterns(self):
        if not self.model: return
        dialog = LoadPatternDialog(self.model, self)
        dialog.exec()

    def on_draw_frame(self):
        if not self.model.sections:
            QMessageBox.warning(self, "Error", "Define a Section Property first!")
            return
        self.draw_mode_active = True
        self.canvas.snapping_enabled = True
        self.draw_start_node = None
        self.status.showMessage("Draw Mode: Select Start Point...")
        
        if self.draw_dialog is None:
            self.draw_dialog = DrawFrameDialog(self.model, self)
            self.draw_dialog.signal_dialog_closed.connect(self.on_draw_finished)
        
        self.draw_dialog.refresh_sections()
        self.draw_dialog.show()

    def on_draw_finished(self):
        self.draw_mode_active = False
        self.canvas.snapping_enabled = False 
        self.draw_start_node = None
        self.canvas.hide_preview_line()
        self.canvas._draw_start = None
        self.canvas.snap_ring.setVisible(False)
        self.canvas.snap_dot.setVisible(False)
        
        self.status.showMessage("Ready")

    def handle_canvas_click(self, x, y, z):
        if self.picking_replicate:
            if self.replicate_p1 is None:
                self.replicate_p1 = (x, y, z)
                self.status.showMessage("Replicate: Click Second Point...")
            else:
                                 
                x1, y1, z1 = self.replicate_p1
                dx = x - x1
                dy = y - y1
                dz = z - z1
                
                self.picking_replicate = False
                self.replicate_p1 = None
                self.canvas.snapping_enabled = False                          
                
                if self.replicate_dialog:
                    self.replicate_dialog.set_increments(dx, dy, dz)
                
                self.status.showMessage("Replicate values set.")
            return                        
        if not self.draw_mode_active: return
        clicked_node = self.model.get_or_create_node(x, y, z)
            
        if self.draw_start_node is None:
            self.draw_start_node = clicked_node
            self.canvas._draw_start = (clicked_node.x, clicked_node.y, clicked_node.z)
            self.status.showMessage(f"Start Node {clicked_node.id} Selected. Select End Point...")
        else:
            end_node = clicked_node
            dx = end_node.x - self.draw_start_node.x
            dy = end_node.y - self.draw_start_node.y
            dz = end_node.z - self.draw_start_node.z
            if (dx**2 + dy**2 + dz**2) < 0.001:
                return
            
            section = self.draw_dialog.get_selected_section()
            if section:
                                          
                p1 = (self.draw_start_node.x, self.draw_start_node.y, self.draw_start_node.z)
                p2 = (end_node.x, end_node.y, end_node.z)
                
                cmd = CmdDrawFrame(self.model, self, p1, p2, section)
                self.add_command(cmd)
                
                self.draw_start_node = self.model.get_or_create_node(*p2)
                self.canvas._draw_start = (self.draw_start_node.x, self.draw_start_node.y, self.draw_start_node.z)
                
                self.status.showMessage(f"Element Drawn. Next Start: Node {end_node.id}...")
            else:
                self.status.showMessage("Error: No Section Selected")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.draw_mode_active:
                if self.draw_dialog:
                    self.draw_dialog.hide()
                self.on_draw_finished()
        
        elif event.key() == Qt.Key.Key_Delete:
            if getattr(self, 'is_locked', False):
                self.status.showMessage("⚠️ Cannot delete objects while Analysis Results are active. Unlock model first.")
                return
            self.delete_current_selection()
        
        super().keyPressEvent(event)
        
    def handle_right_click(self):
        if self.draw_mode_active:
            self.canvas.hide_preview_line()
            self.canvas._draw_start = None
            if self.draw_start_node:
                self.draw_start_node = None
                self.status.showMessage("Chain Broken. Select a new Start Point...")
            return
        
        menu = QMenu(self)
        hit_something = False 

        if hasattr(self.model, 'has_results') and self.model.has_results:
            clicked_node_id = self._get_node_under_mouse()
            
            if clicked_node_id is not None:
                                          
                res_action = menu.addAction(f"Joint {clicked_node_id} Results...")
                
                def show_node_dlg():
                    from app.dialogs.node_results_dialog import NodeResultsDialog
                                                                                
                    self._node_res_dlg = NodeResultsDialog(clicked_node_id, self.model, self)
                    
                    self._node_res_dlg.signal_mode_changed.connect(self.switch_modal_view)
                    
                    self._node_res_dlg.show()
                    
                res_action.triggered.connect(show_node_dlg)
                menu.addSeparator()
                hit_something = True

        if len(self.selected_ids) == 1:
            eid = self.selected_ids[0]
            menu.addAction(f"Frame {eid} Actions:").setEnabled(False)
            menu.addSeparator()
            
            menu.addAction(f"Frame {eid} Actions:").setEnabled(False)
            menu.addSeparator()

            info_action = menu.addAction(f"Frame Information...")
            def show_info():
                if eid in self.model.elements:
                    from app.dialogs.element_info_dialog import ElementInfoDialog
                    dlg = ElementInfoDialog(self.model.elements[eid], self.model, self)
                    dlg.exec()
            info_action.triggered.connect(show_info)

            if hasattr(self.model, 'has_results') and self.model.has_results:
                
                spy_action = menu.addAction("Show Matrices (K, T, FEE)")
                def show_spy():
                    if hasattr(self, 'solver_output_path') and self.solver_output_path:
                        base = self.solver_output_path.replace("_results.json", "_matrices.json")
                        dlg = MatrixSpyDialog(eid, base, self)
                        dlg.exec()
                spy_action.triggered.connect(show_spy)

                fbd_action = menu.addAction("Show Free Body Diagram")
                def show_fbd():
                    if hasattr(self, 'solver_output_path') and self.solver_output_path:
                        base = self.solver_output_path.replace("_results.json", "_matrices.json")
                        dlg = FBDViewerDialog(eid, self.model, self.solver_output_path, base, self)
                        dlg.exec()
                fbd_action.triggered.connect(show_fbd)
                
                diag_action = menu.addAction("Show Shear/Moment Diagrams")
                def show_diagrams():
                    if eid in self.model.elements:
                        from app.dialogs.frame_results_dialog import FrameResultDialog
                        dlg = FrameResultDialog(self.model.elements[eid], self.model, self)
                        dlg.exec()
                diag_action.triggered.connect(show_diagrams)

            hit_something = True

        if self.selected_ids or self.selected_node_ids:
            delete_action = menu.addAction("Delete Selection")
            
            action = menu.exec(QCursor.pos())
            
            if action == delete_action:
                self.delete_current_selection()
            
            hit_something = True

        if not hit_something:
            grid_action = menu.addAction("Edit Grid Data...")
            action = menu.exec(QCursor.pos())
            
            if action == grid_action:
                self.open_grid_editor()
                     
    def open_grid_editor(self):
        if not self.model: return
        from app.dialogs.grid_dialog import GridEditorDialog
        
        dialog = GridEditorDialog(self.model.grid, self)
        if dialog.exec():
                                
            new_grids = dialog.get_final_grids()
            
            self.model.grid.x_lines = new_grids["x"]
            self.model.grid.y_lines = new_grids["y"]
            self.model.grid.z_lines = new_grids["z"]
            
            self.canvas.draw_model(self.model)
            self.status.showMessage("Grid System Updated.")

    def handle_box_selection(self, node_ids, elem_ids, is_additive, is_deselect):
        if is_deselect:
            for nid in node_ids:
                if nid in self.selected_node_ids:
                    self.selected_node_ids.remove(nid)
            for eid in elem_ids:
                if eid in self.selected_ids:
                    self.selected_ids.remove(eid)
            self.status.showMessage(f"Selection: {len(self.selected_ids)} Frames, {len(self.selected_node_ids)} Joints")
        else:
            hit_something = (len(node_ids) > 0) or (len(elem_ids) > 0)
            if hit_something:
                for nid in node_ids:
                    if nid not in self.selected_node_ids: self.selected_node_ids.append(nid)
                for eid in elem_ids:
                    if eid not in self.selected_ids: self.selected_ids.append(eid)
                self.status.showMessage(f"Selected: {len(self.selected_ids)} Frames, {len(self.selected_node_ids)} Joints")
            else:
                if not is_additive:
                    self.selected_ids = []
                    self.selected_node_ids = []
                    self.status.showMessage("Selection Cleared")
        
        self.canvas.draw_model(self.model, self.selected_ids, self.selected_node_ids)

        if len(node_ids) == 1 and not elem_ids:
                           
            nid = node_ids[0]
            n = self.model.nodes[nid]
            target = QVector3D(n.x, n.y, n.z)
            self.canvas.camera.animate_to(target_center=target)
            self.status.showMessage(f"Selected Node {nid} (Camera Focused)")
            
        elif len(elem_ids) == 1 and not node_ids:
                                     
            eid = elem_ids[0]
            el = self.model.elements[eid]
            mid_x = (el.node_i.x + el.node_j.x) / 2
            mid_y = (el.node_i.y + el.node_j.y) / 2
            mid_z = (el.node_i.z + el.node_j.z) / 2
            target = QVector3D(mid_x, mid_y, mid_z)
            self.canvas.camera.animate_to(target_center=target)
            self.status.showMessage(f"Selected Frame {eid} (Camera Focused)")

    def delete_current_selection(self):
        if not self.model: return
        
        if not self.selected_ids and not self.selected_node_ids:
            return

        final_elem_ids = list(self.selected_ids)
        
        final_node_ids = []
        
        for nid in self.selected_node_ids:
            is_safe_to_delete = True
            
            for el in self.model.elements.values():
                                                        
                if el.node_i.id == nid or el.node_j.id == nid:
                                                                                       
                    if el.id not in final_elem_ids:
                        is_safe_to_delete = False
                        break                                                                  
            
            if is_safe_to_delete:
                for slab in self.model.slabs.values():
                    slab_node_ids = [n.id for n in slab.nodes]
                    if nid in slab_node_ids:
                                                                                                
                        is_safe_to_delete = False 
                        break

            if is_safe_to_delete:
                final_node_ids.append(nid)
            else:
                print(f"Node {nid} is protected because it supports an existing object.")

        if self.selected_node_ids and not final_node_ids and not final_elem_ids:
            self.status.showMessage("⚠️ Cannot delete selected joints. They are supporting existing frames.")
            return

        cmd = CmdDeleteSelection(
            self.model, 
            self, 
            final_node_ids, 
            final_elem_ids
        )
        self.add_command(cmd)
        
        self.selected_ids = [] 
        self.selected_node_ids = []
        
        self.status.showMessage(f"Deleted {len(final_elem_ids)} Frames and {len(final_node_ids)} Joints.")

    def is_node_connected(self, node_id):
        """Helper to check if any element in the model uses this node."""
        for el in self.model.elements.values():
            if el.node_i.id == node_id or el.node_j.id == node_id:
                return True
        return False
    
    def on_assign_restraints(self):
        if not hasattr(self, 'restraint_dlg') or not self.restraint_dlg.isVisible():
            from app.dialogs.restraint_dialog import RestraintDialog
            self.restraint_dlg = RestraintDialog(self)
            self.restraint_dlg.show()
        else: self.restraint_dlg.raise_()

    def on_assign_constraints(self):
        if not hasattr(self, 'constraint_dlg') or not self.constraint_dlg.isVisible():
            from app.dialogs.assign_constraint_dialog import AssignConstraintDialog
            self.constraint_dlg = AssignConstraintDialog(self)
            self.constraint_dlg.show()
        else: self.constraint_dlg.raise_()

    def on_assign_joint_load(self):
        if not hasattr(self, 'joint_load_dlg') or not self.joint_load_dlg.isVisible():
            from app.dialogs.assign_load_dialog import AssignJointLoadDialog
            self.joint_load_dlg = AssignJointLoadDialog(self)
            self.joint_load_dlg.show()
        else: self.joint_load_dlg.raise_()

    def on_assign_frame_load(self):
        if not hasattr(self, 'frame_load_dlg') or not self.frame_load_dlg.isVisible():
            from app.dialogs.assign_member_load_dialog import AssignFrameLoadDialog
            self.frame_load_dlg = AssignFrameLoadDialog(self)
            self.frame_load_dlg.show()
        else: self.frame_load_dlg.raise_()

    def on_assign_releases(self):
        if not hasattr(self, 'release_dlg') or not self.release_dlg.isVisible():
            from app.dialogs.release_dialog import FrameReleaseDialog
            self.release_dlg = FrameReleaseDialog(self)
            self.release_dlg.show()
        else: self.release_dlg.raise_()

    def on_assign_local_axis(self):
        if not hasattr(self, 'axis_dlg') or not self.axis_dlg.isVisible():
            from app.dialogs.assign_local_axis_dialog import AssignFrameAxisDialog
            self.axis_dlg = AssignFrameAxisDialog(self)
            self.axis_dlg.show()
        else: self.axis_dlg.raise_()

    def on_create_slab_from_selection(self):
        if len(self.selected_node_ids) < 3:
            QMessageBox.warning(self, "Selection Error", "Select at least 3 Joints.")
            return
        selected_nodes = []
        for nid in self.selected_node_ids:
            if nid in self.model.nodes: selected_nodes.append(self.model.nodes[nid])
        
        cx = sum(n.x for n in selected_nodes) / len(selected_nodes)
        cy = sum(n.y for n in selected_nodes) / len(selected_nodes)
        import math
        selected_nodes.sort(key=lambda n: math.atan2(n.y - cy, n.x - cx))

        self.model.add_slab(selected_nodes, thickness=0.2)
        self.canvas.draw_model(self.model)
        self.status.showMessage(f"Slab Created with {len(selected_nodes)} nodes.")

    def on_view_options(self):
        current_settings = {
            'extrude': self.canvas.view_extruded,
            'areas': self.canvas.show_slabs,
            'joints': self.canvas.show_joints,
            'supports': self.canvas.show_supports,
            'constraints': self.canvas.show_constraints,
            'releases': self.canvas.show_releases,
            'loads': self.canvas.show_loads,
            'axes': self.canvas.show_local_axes  
        }
        dialog = ViewOptionsDialog(self, current_settings)
        dialog.exec()

    def apply_view_options(self, settings):
        self.canvas.view_extruded = settings.get('extrude', False)
        self.canvas.show_slabs = settings.get('areas', True)
        self.canvas.show_joints = settings.get('joints', True)
        self.canvas.show_supports = settings.get('supports', True)
        self.canvas.show_constraints = settings.get('constraints', True)
        self.canvas.show_releases = settings.get('releases', True)
        self.canvas.show_loads = settings.get('loads', True)
        self.canvas.show_local_axes = settings.get('axes', False)
        self.canvas.load_type_filter = settings.get('load_type', 'both')
        self.canvas.visible_load_patterns = settings.get('visible_patterns', [])
        
        self.canvas.draw_model(self.model, self.selected_ids, self.selected_node_ids)
        self.status.showMessage(f"Display Options Updated")

    def on_edit_replicate(self):
        if not self.selected_ids and not self.selected_node_ids:
            QMessageBox.warning(self, "Selection", "Please select objects to replicate first.")
            return

        if self.replicate_dialog is None:
            from app.dialogs.replicate_dialog import ReplicateDialog
            self.replicate_dialog = ReplicateDialog(self)
            self.replicate_dialog.signal_pick_points.connect(self.start_replicate_picking)
        
        if self.replicate_dialog.exec():
                                              
            dx = self.replicate_dialog.dx
            dy = self.replicate_dialog.dy
            dz = self.replicate_dialog.dz
            num = self.replicate_dialog.num
            delete = self.replicate_dialog.delete_original

            cmd = CmdReplicate(
                self.model, 
                self, 
                list(self.selected_node_ids), 
                list(self.selected_ids), 
                dx, dy, dz, num, delete
            )
            self.add_command(cmd)
            
            self.status.showMessage("Replication Complete.")
            
    def start_replicate_picking(self):
        """Called when user clicks 'Pick Two Points' in dialog"""
        self.picking_replicate = True
        self.replicate_p1 = None
        self.canvas.snapping_enabled = True                
        self.status.showMessage("Replicate: Click First Point...")

    def on_edit_merge(self):
        if not self.model: return
        
        count = self.model.merge_nodes(tolerance=0.005)                
        
        if count > 0:
            self.canvas.draw_model(self.model)
            self.status.showMessage(f"Merge Complete: {count} joints removed.")
            QMessageBox.information(self, "Merge", f"Successfully merged {count} duplicate joints.")
        else:
            self.status.showMessage("Merge Complete: No duplicates found.")
            QMessageBox.information(self, "Merge", "No duplicate joints found within tolerance.")
            
    def on_assign_insertion_point(self):
        if not hasattr(self, 'insertion_dlg') or not self.insertion_dlg.isVisible():
            from app.dialogs.assign_insertion_point_dialog import AssignInsertionPointDialog
            self.insertion_dlg = AssignInsertionPointDialog(self)
            self.insertion_dlg.show()
        else: self.insertion_dlg.raise_()

    def on_assign_end_offsets(self):
        if not hasattr(self, 'end_offset_dlg') or not self.end_offset_dlg.isVisible():
            from app.dialogs.assign_end_offset_dialog import AssignEndOffsetDialog
            self.end_offset_dlg = AssignEndOffsetDialog(self)
            self.end_offset_dlg.show()
        else: 
            self.end_offset_dlg.raise_()

    def on_assign_frame_point_load(self):
        """Opens the Point Load Assignment Dialog"""
                                                                          
        if not hasattr(self, 'point_load_dlg') or not self.point_load_dlg.isVisible():
            self.point_load_dlg = AssignFramePointLoadDialog(self)
            self.point_load_dlg.show()
        else:
            self.point_load_dlg.raise_()    

    def on_graphics_options(self):
        """Opens the new Graphics Dialog."""
                                                      
        dlg = GraphicsOptionsDialog(self, self.graphics_settings)
        dlg.show()

    def update_graphics_settings(self, new_settings):
        """
        Called by the Dialog's Apply/OK button.
        Updates the master dict and triggers a canvas refresh.
        """

        import json, os
        prefs_path = os.path.join(os.path.expanduser("~"), ".opencivil_prefs.json")
        try:
            with open(prefs_path, 'w') as f:
                json.dump({"msaa_level": new_settings.get("msaa_level", 2)}, f)
        except:
            pass

        msaa_samples = {0: 0, 1: 4, 2: 8, 3: 16}
        level = new_settings.get("msaa_level", 2)
        self.graphics_settings["msaa_level"] = level
                                   
        self.graphics_settings.update(new_settings)
        
        self.canvas.display_config = self.graphics_settings
        
        bg_tuple = self.graphics_settings["background_color"]
        c = QColor()
        c.setRgbF(bg_tuple[0], bg_tuple[1], bg_tuple[2], bg_tuple[3])
        self.canvas.setBackgroundColor(c)

        if self.model:
            self.canvas.draw_model(self.model, self.selected_ids, self.selected_node_ids)
            
        self.status.showMessage("Graphics settings updated.")

    def on_define_load_cases(self):
        if not self.model: return
                                                                
        self.model.create_default_cases()
        
        dialog = LoadCaseManagerDialog(self.model, self)
        dialog.exec()

    def on_run_analysis_dialog(self):
        """Opens the setup dialog."""
        if not self.model: return

        dlg = AnalysisDialog(self.model, self)
                                                             
        dlg.signal_run_analysis.connect(self.start_analysis_sequence)
        dlg.exec()

    def start_analysis_sequence(self, case_name):

        current_path = getattr(self.model, 'file_path', None)

        if not current_path:
            QMessageBox.warning(self, "Save Required", "Please save the model file before running analysis.")
            self.on_save_model()
            
            current_path = getattr(self.model, 'file_path', None)
            if not current_path:
                return                      

        print(f"Main: Starting analysis for case '{case_name}'...")
        """
        1. Ensure File is Saved
        2. Lock Interface
        3. Determine Paths based on Filename
        4. Run Solver Thread
        """
                                          
        if not hasattr(self.model, 'file_path') or not self.model.file_path:
            QMessageBox.warning(self, "Save Required", "Please save the model file before running analysis.")
            self.on_save_model()
                                                   
            if not self.model.file_path:
                return

        print(f"Main: Starting analysis for case '{case_name}'...")
        
        self.set_interface_state(False)
        self.status.showMessage(f"Running Analysis: {case_name}... Please Wait.")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        
        self.solver_input_path = self.model.file_path
        
        base_name = os.path.splitext(self.solver_input_path)[0]
        self.solver_output_path = f"{base_name}_results.json"
        
        try:
            self.model.save_to_file(self.solver_input_path)
            print(f"Model saved to {self.solver_input_path}")
        except Exception as e:
            self.finish_analysis_sequence(False, f"Could not save input file: {e}")
            return

        case_obj = self.model.load_cases.get(case_name)
        c_type = case_obj.case_type if case_obj else "Linear Static"

        self.worker = SolverWorker(
            self.solver_input_path, 
            self.solver_output_path, 
            case_type=c_type, 
            case_name=case_name 
        )
        self.worker.signal_finished.connect(self.finish_analysis_sequence)
        self.worker.start()
    def finish_analysis_sequence(self, success, message):
        """Called when the Solver Thread finishes."""
        QApplication.restoreOverrideCursor()
        
        if success:
            self.status.showMessage("Analysis Complete.")
            self.load_analysis_results()                                                 
        else:
                                                        
            self.set_interface_state(True) 
            QMessageBox.critical(self, "Analysis Failed", message)

    def load_analysis_results(self):
        """Reads the specific result file generated for this model."""
        import json
        
        if not hasattr(self, 'solver_output_path') or not self.solver_output_path:
            QMessageBox.warning(self, "Error", "Result path is undefined.")
            return

        res_path = self.solver_output_path
        
        if not os.path.exists(res_path):
            QMessageBox.warning(self, "Error", f"Result file not found at:\n{res_path}")
            return

        try:
            with open(res_path, 'r') as f:
                data = json.load(f)
            
            if data.get("status") == "FAILED":
                err_info = data.get("error", {})
                msg = f"Analysis Failed: {err_info.get('title', 'Unknown Error')}\n{err_info.get('desc', '')}"
                QMessageBox.critical(self, "Analysis Failed", msg)
                self.unlock_model() 
                return

            self.model.results = data 
            if "displacements" in data:
                                                                               
                self.model.results["_base_displacements"] = data["displacements"].copy()
            self.model.has_results = True
            self.canvas.view_deflected = False 
            self.canvas.invalidate_deflection_cache()
            
            self.canvas.anim_factor = 1.0
            
            self.canvas.cache_scale_used = None

            if hasattr(self.canvas, 'animation_manager'):
                self.canvas.animation_manager.invalidate_prerender()
            
            if hasattr(self.canvas, 'invalidate_deflection_cache'):
                self.canvas.invalidate_deflection_cache()

            self.btn_deform.setEnabled(True)
            
            self.lock_model()
            self.canvas.draw_model(self.model, self.selected_ids, self.selected_node_ids)
            
            QMessageBox.information(self, "Success", "Analysis Complete. Results Loaded.\nRight-click any joint to view deformations.")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load results:\n{e}")
            self.unlock_model()

    def lock_model(self):
        self.is_locked = True
        self.set_interface_state(False)
        
        self.btn_lock.setText("🔒")
        self.btn_lock.setToolTip("Analysis Results Active. Click to Unlock and Edit.")

    def unlock_model(self):
                                                       
        if hasattr(self.model, 'has_results') and self.model.has_results:
            reply = QMessageBox.question(
                self, "Discard Results?", 
                "Unlocking the model will delete current analysis results.\nDo you want to continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        self.btn_deform.setEnabled(False)
        self.canvas.view_deflected = False  

        self.view_shadow = True
        self.shadow_color = (0.7, 0.7, 0.7, 0.3)

        self.is_locked = False
        self.model.has_results = False
        self.model.results = None

        if hasattr(self, "canvas") and self.canvas.animation_manager:
            self.canvas.animation_manager.stop_animation()

        self.canvas.view_deflected = False
        self.canvas.anim_factor = 0.0
        self.canvas.invalidate_animation_cache()

        if hasattr(self, "deformed_shape_dialog") and self.deformed_shape_dialog:
            self.deformed_shape_dialog.force_exit_animation_mode()

        self.canvas._force_draw_model(self.model)

        self.canvas.view_deflected = False
        self.canvas.anim_factor = 0.0
        self.canvas.invalidate_animation_cache()

        self.canvas._force_draw_model(self.model)

        self.set_interface_state(True)
        
        self.btn_lock.setText("🔓")
        self.btn_lock.setToolTip("Model is editable.")
                                          
        self.status.showMessage("Results discarded. Model unlocked for editing.")
        
        self.canvas.draw_model(self.model)

    def show_node_results(self, node_id):
        """Displays the small popup box with deformations."""
        if not self.model.results: return
        
        disp = self.model.results.get("displacements", {}).get(str(node_id))
        
        if not disp:
            QMessageBox.warning(self, "No Data", f"No results found for Node {node_id}")
            return
            
        ux, uy, uz, rx, ry, rz = disp
        
        msg = f"""
        <b>JOINT {node_id} RESULTS</b>
        <hr>
        <b>Translations [m]:</b><br>
        Ux: {ux:.6f}<br>
        Uy: {uy:.6f}<br>
        Uz: {uz:.6f}<br>
        <br>
        <b>Rotations [rad]:</b><br>
        Rx: {rx:.6f}<br>
        Ry: {ry:.6f}<br>
        Rz: {rz:.6f}
        """
        
        box = QMessageBox(self)
        box.setWindowTitle(f"Joint {node_id} Displacements")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(msg)
        box.exec()

    def _get_node_under_mouse(self):
        """Helper to find the node ID under the mouse cursor."""
                                                                         
        if len(self.selected_node_ids) == 1:
            return self.selected_node_ids[0]
        
        return None

    def on_lock_clicked(self):
        """Handles the toolbar lock button click."""
        if getattr(self, 'is_locked', False):
                                                                     
            self.unlock_model()
        else:
                                                                  
            self.status.showMessage("Model is already editable. Run Analysis to lock.")

    def update_window_title(self):
        """Updates window title to show currently active filename."""
        base_title = "OPENCIVIL Analysis Engine"
        
        if self.model and getattr(self.model, 'file_path', None):
                                                                            
            short_name = os.path.basename(self.model.file_path)
            self.setWindowTitle(f"{base_title} - [{short_name}]")
        else:
            self.setWindowTitle(base_title)
    
    def add_command(self, command):
        """
        Pushes a command to the stack. 
        This automatically runs redo() once, applying the change.
        """
        if self.model is None: return
        
        if getattr(self, 'is_locked', False):
            self.status.showMessage("⚠️ Cannot modify model while locked. Unlock first.")
            return

        self.undo_stack.push(command)

    def on_view_deformed_shape(self):
        """Opens the Deformed Shape Control Dialog."""
                           
        if not self.model or not self.model.has_results:
            QMessageBox.warning(self, "No Results", "Please run the analysis first.")
            return

        current_spd = 1.0
        if hasattr(self.canvas, 'animation_manager'):
            current_spd = self.canvas.animation_manager.speed_factor

        dlg = DeformedShapeDialog(
            parent=self, 
            current_scale=self.canvas.deflection_scale, 
            is_active=self.canvas.view_deflected,
            show_shadow=self.canvas.view_shadow,
            shadow_color=self.canvas.shadow_color,
            is_animating=self.canvas.animation_manager.is_running,
            current_speed=current_spd                                 
        )
        dlg.exec()

    def apply_deformed_shape(self, is_visible, scale_factor, show_shadow, shadow_color):
        """Callback from the Dialog to update the canvas."""
                                                
        self.canvas.view_deflected = is_visible
        
        if self.canvas.deflection_scale != scale_factor:
            self.canvas.deflection_scale = scale_factor
                                                                           
            if hasattr(self.canvas, 'animation_manager'):
                self.canvas.animation_manager.invalidate_prerender()
        
        self.canvas.view_shadow = show_shadow
        self.canvas.shadow_color = shadow_color
        
        self.canvas.draw_model(self.model, self.selected_ids, self.selected_node_ids)
        
        state_msg = "ON" if is_visible else "OFF"
        self.status.showMessage(f"Deformed Shape: {state_msg} (Scale: {scale_factor}x)")

    def toggle_animation(self, start, play_sound):
        """Called by DeformedShapeDialog."""
        if start:
                                                      
            progress = QProgressDialog("Pre-rendering animation frames...\nPlease wait...", 
                                      None, 0, 100, self)
            progress.setWindowTitle("Loading Animation")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)                    
            progress.setValue(0)
            
            def update_progress(percent):
                progress.setValue(percent)
                QApplication.processEvents()                      
            
            self.canvas.animation_manager.start_animation(update_progress)
            
            progress.close()
            
            if play_sound and self.sound_effect.source().isValid():
                self.sound_effect.play()
                
            self.status.showMessage("Animation Running...")
        else:
                                
            self.canvas.animation_manager.stop_animation()
            
            self.canvas.anim_factor = 1.0
            self.canvas.invalidate_animation_cache()

            self.canvas._force_draw_model(
                self.model,
                self.selected_ids,
                self.selected_node_ids
            )
            
            if self.sound_effect.isPlaying():
                self.sound_effect.stop()
                
            self.status.showMessage("Animation Stopped.")

    def set_animation_speed(self, speed_factor):
        """Called by Dialog Slider to change animation speed live."""
        if hasattr(self.canvas, 'animation_manager'):
            self.canvas.animation_manager.set_speed(speed_factor)

    def on_define_mass_source(self):
        if not self.model: return
        dialog = MassSourceManagerDialog(self.model, self)
        dialog.exec()

    def on_show_modal_results(self):
                                                 
        if not self.model or not self.model.results:
            QMessageBox.warning(self, "No Results", "Please run an Analysis first.")  
            return

        from app.dialogs.modal_results_dialog import ModalResultsDialog 
        dlg = ModalResultsDialog(self.model.results, self)
        dlg.exec()

    def switch_modal_view(self, mode_key):
        """
        Updates the global "displacements" to match the selected Mode Shape.
        Includes SMART AUTO-SCALING and CACHE CLEARING.
        """
        if not self.model or not self.model.results: return
        
        target_data = {}

        if mode_key == "MAIN_RESULT":
                                                                             
            if "_base_displacements" in self.model.results:
                target_data = self.model.results["_base_displacements"]
                self.status.showMessage("Displaying: Main Analysis Results (RSA/Static)")
            else:
                return 
        else:
                             
            shapes = self.model.results.get("mode_shapes", {})
            if mode_key in shapes:
                target_data = shapes[mode_key]
                self.status.showMessage(f"Displaying: {mode_key}")
            else:
                return

        self.model.results["displacements"] = target_data
        
        max_disp = 0.0
        for vec in target_data.values():
                                                
            d = (vec[0]**2 + vec[1]**2 + vec[2]**2)**0.5
            if d > max_disp: max_disp = d
            
        if max_disp > 1e-9: 
            auto_scale = 2.0 / max_disp
        else:
            auto_scale = 1.0

        self.canvas.deflection_scale = auto_scale
        
        if not self.canvas.view_deflected:
            self.canvas.view_deflected = True
            
        self.canvas.invalidate_deflection_cache()
        
        if hasattr(self.canvas, 'animation_manager'):
            self.canvas.animation_manager.invalidate_prerender()
            
        self.canvas.draw_model(self.model)
        
        self.status.showMessage(f"{self.status.currentMessage()} (Auto-Scale: {auto_scale:.1f}x)")
        
    def closeEvent(self, event):
        """Intercepts the window close request to check for unsaved changes."""
        
        if not self.model:
            event.accept()
            return

        if not self.undo_stack.isClean():
            reply = QMessageBox.question(
                self, 
                "Unsaved Changes",
                "You have unsaved changes in your model.\nDo you want to save them before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save
            )

            if reply == QMessageBox.StandardButton.Save:
                                                                                            
                if self.on_save_model():
                    event.accept()
                else:
                    event.ignore() 
                    
            elif reply == QMessageBox.StandardButton.Discard:
                event.accept()                       
                
            else:         
                event.ignore()                        
        else:
                                                
            event.accept()

    def on_define_response_spectrum(self):
        if not self.model: return
        
        from app.dialogs.response_spectrum_manager import ResponseSpectrumManagerDialog
        
        dlg = ResponseSpectrumManagerDialog(self.model, self)
        dlg.exec()
        
        self.status.showMessage(f"Response Spectrum Definitions Updated.")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'user_widget'):
            self.user_widget.reposition()

def main():
    if sys.platform == 'win32':
        myappid = 'metu.civil.OPENCIVIL.v03'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    app = QApplication(sys.argv)

    from PyQt6.QtGui import QSurfaceFormat
    import json, os

    prefs_path = os.path.join(os.path.expanduser("~"), ".opencivil_prefs.json")
    msaa_map = {0: 0, 1: 4, 2: 8, 3: 16}
    msaa_level = 2  
    if os.path.exists(prefs_path):
        try:
            with open(prefs_path) as f:
                prefs = json.load(f)
                msaa_level = prefs.get("msaa_level", 2)
        except:
            pass

    fmt = QSurfaceFormat()
    fmt.setSamples(msaa_map[msaa_level])
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)
    
    video_path = os.path.join(root_dir, "graphic", "Animation.gif")
    
    if not os.path.exists(video_path):
        print("Video not found, skipping splash.")
        window = MainWindow()

        auth_manager = GoogleAuthManager()
        if not auth_manager.login(parent=None):
            sys.exit(0)

        window.auth_manager = auth_manager
        window.showMaximized()

        def attach_no_splash():
            window.user_widget = UserProfileWidget(auth_manager, parent=window)
            window.user_widget.reposition()
            window.user_widget.show()
            window.user_widget.raise_()

        QTimer.singleShot(150, attach_no_splash)
        sys.exit(app.exec())

    splash = VideoSplash(video_path)
    window = MainWindow()
    
    def on_splash_finished():
        splash.close()

        auth_manager = GoogleAuthManager()
        if not auth_manager.login(parent=None):
            app.quit()
            return

        window.auth_manager = auth_manager

        window.showMaximized()
        window.activateWindow()

        def attach_user_widget():
            window.user_widget = UserProfileWidget(auth_manager, parent=window)
            window.user_widget.reposition()
            window.user_widget.show()
            window.user_widget.raise_()

            def on_logout():
                if window.model and not window.undo_stack.isClean():
                    reply = QMessageBox.question(
                        window,
                        "Unsaved Changes",
                        "You have unsaved changes in your model.\nDo you want to save before logging out?",
                        QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                        QMessageBox.StandardButton.Save
                    )
                    if reply == QMessageBox.StandardButton.Save:
                        if not window.on_save_model():
                            return 
                    elif reply == QMessageBox.StandardButton.Cancel:
                        return  

                if hasattr(window, 'canvas'):

                    if hasattr(window.canvas, 'animation_manager'):
                        window.canvas.animation_manager.stop_animation()
                    for item in window.canvas.items[:]:
                        try:
                            window.canvas.removeItem(item)
                        except Exception:
                            pass
                    window.canvas.node_items.clear()
                    window.canvas.element_items.clear()
                    window.canvas.static_items.clear()
                    window.canvas.current_model = None
                    window.canvas.selected_element_ids = []
                    window.canvas.selected_node_ids = []
                    window.canvas.view_deflected = False
                    window.canvas.invalidate_deflection_cache()
                window.model = None
                window.undo_stack.clear()
                window.selected_ids = []
                window.selected_node_ids = []
                window.set_interface_state(False)
                window.setWindowTitle("OPENCIVIL Analysis Engine")
                window.status.showMessage("Welcome. Please create or open a model.")

                if hasattr(window, 'user_widget'):
                    window.user_widget.deleteLater()

                window.hide()

                if auth_manager.login(parent=None):
                    window.showMaximized()
                    window.activateWindow()
                    QTimer.singleShot(100, attach_user_widget)
                else:
                    app.quit()

            window.user_widget.logout_requested.connect(on_logout)

        QTimer.singleShot(150, attach_user_widget)               
        
        if len(sys.argv) > 1:
            file_path = sys.argv[1]
            if os.path.exists(file_path) and file_path.endswith('.mf'):
                                                
                try:
                    if window.model is None:
                        window.model = StructuralModel("Loaded Project")
                    
                    window.model.load_from_file(file_path)
                    window.undo_stack.clear()
                    window.model.file_path = file_path
                    
                    if window.model.graphics_settings:
                        window.graphics_settings.update(window.model.graphics_settings)
                        window.update_graphics_settings(window.graphics_settings)
                    
                    if hasattr(window.model, 'saved_unit_system'):
                        window.combo_units.blockSignals(True)
                        window.combo_units.setCurrentText(window.model.saved_unit_system)
                        window.combo_units.blockSignals(False)
                        window.on_units_changed(0)
                    
                    window.canvas.draw_model(window.model)
                    window.status.showMessage(f"Loaded: {file_path}")
                    window.canvas.set_standard_view("3D")
                    window.set_interface_state(True)
                    window.update_window_title()
                except Exception as e:
                    QMessageBox.critical(window, "Load Error", f"Failed to open file.\n{e}")
    
    splash.finished.connect(on_splash_finished)

    splash.show()
    splash.start()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
