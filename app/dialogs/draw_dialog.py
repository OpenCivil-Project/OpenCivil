from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QComboBox, 
                             QFormLayout, QPushButton, QGroupBox, QHBoxLayout)
from PyQt6.QtCore import Qt, pyqtSignal

class DrawFrameDialog(QDialog):
                                               
    signal_dialog_closed = pyqtSignal()

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Draw Frame Object")
        
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint) 
        self.setMinimumWidth(280)
        
        main_layout = QVBoxLayout(self)
        
        prop_group = QGroupBox("Line Object Parameters")
        form_layout = QFormLayout()
        
        self.section_combo = QComboBox()
        self.refresh_sections()
        form_layout.addRow("Section Property:", self.section_combo)
        
        self.release_combo = QComboBox()
        self.release_combo.addItems(["Continuous", "Pinned"])
        form_layout.addRow("Moment Releases:", self.release_combo)
        
        prop_group.setLayout(form_layout)
        main_layout.addWidget(prop_group)
        
        inst_group = QGroupBox("Drawing Controls")
        inst_layout = QVBoxLayout()
        
        lbl = QLabel("• <b>Left Click:</b> Draw segment<br>"
                     "• <b>Right Click:</b> Stop chain<br>"
                     "• <b>Esc:</b> Exit draw mode")
        lbl.setStyleSheet("color: #555; font-size: 12px;")
        inst_layout.addWidget(lbl)
        inst_group.setLayout(inst_layout)
        main_layout.addWidget(inst_group)
        
        btn_layout = QHBoxLayout()
        btn_layout.addStretch() 
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)
        
        main_layout.addLayout(btn_layout)

    def refresh_sections(self):
        current = self.section_combo.currentText()
        self.section_combo.clear()
        if not self.model.sections:
            self.section_combo.addItem("Default")
        else:
            self.section_combo.addItems(list(self.model.sections.keys()))
        idx = self.section_combo.findText(current)
        if idx >= 0: self.section_combo.setCurrentIndex(idx)

    def get_selected_section(self):
        name = self.section_combo.currentText()
        if name in self.model.sections:
            return self.model.sections[name]
        return None

    def get_release_arrays(self):
        release_type = self.release_combo.currentText()
        if release_type == "Pinned":
                                            
            rel_i = [False, False, False, False, True, True]
            rel_j = [False, False, False, False, True, True]
        else:
                         
            rel_i = [False, False, False, False, False, False]
            rel_j = [False, False, False, False, False, False]
        return rel_i, rel_j

    def closeEvent(self, event):
        self.signal_dialog_closed.emit()
        super().closeEvent(event)
