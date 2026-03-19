from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QGroupBox, QRadioButton, 
                             QMessageBox, QGridLayout, QCheckBox)
from PyQt6.QtCore import Qt
from core.units import unit_registry
from app.commands import CmdAssignEndOffsets                   

class AssignEndOffsetDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.model = main_window.model
        
        self.setWindowTitle("Assign Frame End Length Offsets")
        self.resize(350, 300)
        
        layout = QVBoxLayout(self)

        grp_mode = QGroupBox("Options for End Offset Along Length")
        mode_layout = QVBoxLayout()
        
        self.radio_auto = QRadioButton("Automatic from Connectivity")
        self.radio_auto.setEnabled(False)                   
        self.radio_auto.setToolTip("Requires calculating column depths (Coming Soon)")
        
        self.radio_user = QRadioButton("User Defined Lengths")
        self.radio_user.setChecked(True)          
        self.radio_user.toggled.connect(self.toggle_inputs)

        mode_layout.addWidget(self.radio_auto)
        mode_layout.addWidget(self.radio_user)
        grp_mode.setLayout(mode_layout)
        layout.addWidget(grp_mode)

        grp_param = QGroupBox("Parameters")
        param_layout = QGridLayout()
        
        lbl_i = QLabel("End-I Length:")
        lbl_j = QLabel("End-J Length:")
        lbl_factor = QLabel("Rigid Zone Factor:")
        
        self.input_off_i = QLineEdit("0.0")
        self.input_off_j = QLineEdit("0.0")
        self.input_factor = QLineEdit("0.0") 
        
        unit_len = unit_registry.length_unit_name
        
        param_layout.addWidget(lbl_i, 0, 0)
        param_layout.addWidget(self.input_off_i, 0, 1)
        param_layout.addWidget(QLabel(unit_len), 0, 2)

        param_layout.addWidget(lbl_j, 1, 0)
        param_layout.addWidget(self.input_off_j, 1, 1)
        param_layout.addWidget(QLabel(unit_len), 1, 2)

        self.chk_diff_j = QCheckBox("Assign different End-J value")
        param_layout.addWidget(self.chk_diff_j, 2, 0, 1, 3)
        self.chk_diff_j.toggled.connect(self.toggle_j_input)
        self.input_off_i.textChanged.connect(self.mirror_j)
        self.input_off_j.setEnabled(False)
        
        param_layout.addWidget(lbl_factor, 3, 0)
        param_layout.addWidget(self.input_factor, 3, 1)
        
        grp_param.setLayout(param_layout)
        layout.addWidget(grp_param)

        btn_layout = QHBoxLayout()
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.clicked.connect(self.apply_changes)
        
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        
        self.btn_reset = QPushButton("Reset Defaults")
        self.btn_reset.clicked.connect(self.reset_defaults)

        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)

    def toggle_inputs(self):
        """Enables/Disables inputs based on radio selection"""
        is_user = self.radio_user.isChecked()
        self.input_off_i.setEnabled(is_user)
        self.input_factor.setEnabled(True)
        self.chk_diff_j.setEnabled(is_user)
        self.input_off_j.setEnabled(is_user and self.chk_diff_j.isChecked())

    def toggle_j_input(self, checked):
        self.input_off_j.setEnabled(checked)
        if not checked:
            self.input_off_j.setText(self.input_off_i.text())

    def mirror_j(self, text):
        if not self.chk_diff_j.isChecked():
            self.input_off_j.setText(text)

    def reset_defaults(self):
        self.input_off_i.setText("0.0")
        self.input_off_j.setText("0.0")
        self.input_factor.setText("0.0")
        self.radio_user.setChecked(True)
        self.chk_diff_j.setChecked(False)
        self.input_off_j.setEnabled(False)

    def apply_changes(self):
        selected_ids = self.main_window.selected_ids
        if not selected_ids:
            QMessageBox.warning(self, "Selection", "No frames selected.")
            return
            
        try:
                          
            scale = 1.0 / unit_registry.length_scale 
            
            off_i = float(self.input_off_i.text()) * scale
            off_j = float(self.input_off_j.text()) * scale
            factor = float(self.input_factor.text())
            
            if not (0.0 <= factor <= 1.0):
                raise ValueError("Rigid Factor must be between 0 and 1")

            cmd = CmdAssignEndOffsets(
                self.model, 
                self.main_window, 
                list(selected_ids), 
                off_i, 
                off_j, 
                factor
            )
            self.main_window.add_command(cmd)
            
            self.main_window.status.showMessage(f"Assigned End Offsets to {len(selected_ids)} frames.")
            
        except ValueError as e:
            QMessageBox.warning(self, "Input Error", str(e))
