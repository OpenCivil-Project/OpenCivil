import numpy as np
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QLineEdit, QComboBox, QGroupBox, 
                             QCheckBox, QGridLayout, QMessageBox)
from PyQt6.QtCore import Qt
from core.units import unit_registry
from app.commands import CmdAssignInsertion                   

class AssignInsertionPointDialog(QDialog):
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.model = main_window.model
        
        self.setWindowTitle("Assign Frame Insertion Point")
        self.resize(400, 450)
        self.setModal(False)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        
        layout = QVBoxLayout(self)

        grp_card = QGroupBox("Cardinal Point")
        card_layout = QVBoxLayout()
        
        h_card = QHBoxLayout()
        h_card.addWidget(QLabel("Cardinal Point:"))
        self.combo_cardinal = QComboBox()
        self.combo_cardinal.addItems([
            "1 (Bottom Left)", "2 (Bottom Center)", "3 (Bottom Right)",
            "4 (Middle Left)", "5 (Middle Center)", "6 (Middle Right)",
            "7 (Top Left)",    "8 (Top Center)",    "9 (Top Right)",
            "10 (Centroid)",   "11 (Shear Center)"
        ])
        self.combo_cardinal.setCurrentIndex(9)                
        h_card.addWidget(self.combo_cardinal)
        card_layout.addLayout(h_card)
        
        self.chk_mirror2 = QCheckBox("Mirror about Local 2 Axis")
        self.chk_mirror3 = QCheckBox("Mirror about Local 3 Axis")
        self.chk_mirror2.setEnabled(False) 
        self.chk_mirror3.setEnabled(False)
        
        card_layout.addWidget(self.chk_mirror2)
        card_layout.addWidget(self.chk_mirror3)
        
        grp_card.setLayout(card_layout)
        layout.addWidget(grp_card)

        grp_off = QGroupBox("Frame Joint Offsets to Cardinal Point")
        off_layout = QVBoxLayout()
        
        h_sys = QHBoxLayout()
        h_sys.addWidget(QLabel("Coordinate System:"))
        self.combo_sys = QComboBox()
        self.combo_sys.addItems(["Local", "Global"])
        self.combo_sys.setCurrentText("Local")
        
        self.combo_sys.currentIndexChanged.connect(self.update_labels)
        
        h_sys.addWidget(self.combo_sys)
        off_layout.addLayout(h_sys)
        
        grid = QGridLayout()
        grid.addWidget(QLabel("End-I"), 0, 1)
        grid.addWidget(QLabel("End-J"), 0, 2)
        
        self.inputs_i = []
        self.inputs_j = []
        self.row_labels = [] 
        
        labels_txt = ["Local 1 (Axial)", "Local 2", "Local 3"]
        
        for i, txt in enumerate(labels_txt):
            lbl = QLabel(txt + ":")
            self.row_labels.append(lbl)
            grid.addWidget(lbl, i+1, 0)
            
            le_i = QLineEdit("0.0")
            le_i.textChanged.connect(self.mirror_j)
            grid.addWidget(le_i, i+1, 1)
            self.inputs_i.append(le_i)
            
            le_j = QLineEdit("0.0")
            le_j.setEnabled(False)
            grid.addWidget(le_j, i+1, 2)
            self.inputs_j.append(le_j)
            
            u_lbl = unit_registry.current_unit_label.split(",")[1].strip()
            grid.addWidget(QLabel(u_lbl), i+1, 3)

        self.chk_diff_j = QCheckBox("Assign different End-J values")
        off_layout.addWidget(self.chk_diff_j)
        self.chk_diff_j.toggled.connect(self.toggle_j_inputs)

        off_layout.addLayout(grid)
        grp_off.setLayout(off_layout)
        layout.addWidget(grp_off)

        grp_trans = QGroupBox("Stiffness Transformation")
        trans_layout = QVBoxLayout()
        self.chk_no_transform = QCheckBox("Do Not Transform Frame Stiffness")
        trans_layout.addWidget(self.chk_no_transform)
        grp_trans.setLayout(trans_layout)
        layout.addWidget(grp_trans)

        btn_layout = QHBoxLayout()
        self.btn_reset = QPushButton("Reset Form")
        self.btn_reset.clicked.connect(self.reset_form)
        self.btn_apply = QPushButton("Apply")
        self.btn_apply.clicked.connect(self.apply_changes)
        self.btn_close = QPushButton("Close")
        self.btn_close.clicked.connect(self.close)
        
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)
        btn_layout.addWidget(self.btn_close)
        
        layout.addLayout(btn_layout)

    def update_labels(self):
        """Updates labels between Local 1,2,3 and Global X,Y,Z"""
        mode = self.combo_sys.currentText()
        if mode == "Local":
            self.row_labels[0].setText("Local 1 (Axial):")
            self.row_labels[1].setText("Local 2:")
            self.row_labels[2].setText("Local 3:")
        else:
            self.row_labels[0].setText("Global X:")
            self.row_labels[1].setText("Global Y:")
            self.row_labels[2].setText("Global Z:")

    def toggle_j_inputs(self, checked):
        for le_i, le_j in zip(self.inputs_i, self.inputs_j):
            le_j.setEnabled(checked)
            if not checked:
                le_j.setText(le_i.text())

    def mirror_j(self):
        if not self.chk_diff_j.isChecked():
            for le_i, le_j in zip(self.inputs_i, self.inputs_j):
                le_j.setText(le_i.text())

    def reset_form(self):
        self.combo_cardinal.setCurrentIndex(9)
        for le in self.inputs_i: le.setText("0.0")
        for le in self.inputs_j: le.setText("0.0")
        self.chk_no_transform.setChecked(False)
        self.combo_sys.setCurrentText("Local")
        self.chk_diff_j.setChecked(False)
        for le_j in self.inputs_j: le_j.setEnabled(False)

    def apply_changes(self):
        selected_frames = self.main_window.selected_ids
        if not selected_frames:
            QMessageBox.warning(self, "Selection Error", "Please select at least one Frame Element.")
            return

        try:
                             
            card_id = self.combo_cardinal.currentIndex() + 1
            scale = 1.0 / unit_registry.length_scale
            coord_sys = self.combo_sys.currentText() 
            
            raw_i = np.array([
                float(self.inputs_i[0].text()) * scale,
                float(self.inputs_i[1].text()) * scale,
                float(self.inputs_i[2].text()) * scale
            ])
            
            raw_j = np.array([
                float(self.inputs_j[0].text()) * scale,
                float(self.inputs_j[1].text()) * scale,
                float(self.inputs_j[2].text()) * scale
            ])
            
            cmd = CmdAssignInsertion(
                self.model, 
                self.main_window, 
                list(selected_frames), 
                card_id, 
                raw_i, 
                raw_j, 
                coord_sys
            )
            self.main_window.add_command(cmd)
            
            self.main_window.status.showMessage(f"Updated Insertion Points for {len(selected_frames)} Frames.")
                                                                                                          
        except ValueError:
            QMessageBox.warning(self, "Input Error", "Please enter valid numeric values.")
