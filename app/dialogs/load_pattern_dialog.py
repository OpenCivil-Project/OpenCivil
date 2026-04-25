from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTableWidget, QTableWidgetItem, QPushButton, 
                             QLineEdit, QComboBox, QMessageBox, QHeaderView,
                             QAbstractItemView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

class LoadPatternDialog(QDialog):
    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.model = model
        self.setWindowTitle("Define Load Patterns")
        self.resize(650, 400)                                     
        
        self.style_primary_btn = ""
        self.style_danger_btn = ""
        
        layout = QVBoxLayout(self)

        input_layout = QHBoxLayout()
        
        v_name = QVBoxLayout()
        v_name.addWidget(QLabel("Load Pattern Name:"))
        self.input_name = QLineEdit("LIVE")
        self.input_name.setPlaceholderText("Name")
        self.input_name.setStyleSheet("padding: 4px;")
        v_name.addWidget(self.input_name)
        input_layout.addLayout(v_name)
        
        v_type = QVBoxLayout()
        v_type.addWidget(QLabel("Type:"))
        self.input_type = QComboBox()
        self.input_type.addItems(["DEAD", "LIVE", "SUPERDEAD", "WIND", "QUAKE", "SNOW"])
        self.input_type.currentTextChanged.connect(self.auto_set_multiplier)
        self.input_type.setStyleSheet("padding: 4px;")
        v_type.addWidget(self.input_type)
        input_layout.addLayout(v_type)
        
        v_mult = QVBoxLayout()
        v_mult.addWidget(QLabel("Self Wt Mult:"))
        self.input_sw = QLineEdit("0.0") 
        self.input_sw.setFixedWidth(80)
        self.input_sw.setStyleSheet("padding: 4px;")
        v_mult.addWidget(self.input_sw)
        input_layout.addLayout(v_mult)

        v_btns = QVBoxLayout()
        v_btns.addSpacing(18)                                              
        
        h_action_btns = QHBoxLayout()
        
        btn_add = QPushButton("Add New")
        btn_add.setStyleSheet(self.style_primary_btn)
        btn_add.clicked.connect(self.add_pattern)
        
        self.btn_modify = QPushButton("Modify")
        self.btn_modify.setStyleSheet(self.style_danger_btn)                            
        self.btn_modify.clicked.connect(self.modify_pattern)
        
        h_action_btns.addWidget(btn_add)
        h_action_btns.addWidget(self.btn_modify)
        v_btns.addLayout(h_action_btns)
        
        input_layout.addLayout(v_btns)
        
        layout.addLayout(input_layout)
        layout.addSpacing(10)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Load Pattern Name", "Type", "Self Wt. Multiplier"])
        
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        self.table.setStyleSheet("""
            QTableWidget {
                selection-background-color: #e8e8e8;
                selection-color: black;
                gridline-color: #d0d0d0;
            }
            QHeaderView::section {
                background-color: #f0f0f0;
                padding: 4px;
                border: 1px solid #d0d0d0;
            }
        """)
        
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        
        btn_delete = QPushButton("Delete Pattern")
        btn_delete.setStyleSheet(self.style_danger_btn)                        
        btn_delete.clicked.connect(self.delete_pattern)
        
        btn_ok = QPushButton("OK")
        btn_ok.setStyleSheet(self.style_danger_btn)        
        btn_ok.setFixedWidth(100)
        btn_ok.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        layout.addLayout(btn_layout)

        self.refresh_table()

    def auto_set_multiplier(self, type_text):
        if type_text == "DEAD":
            self.input_sw.setText("1.0")
        else:
            self.input_sw.setText("0.0")

    def on_selection_changed(self):
        row = self.table.currentRow()
        if row < 0: return

        name = self.table.item(row, 0).text()
        p_type = self.table.item(row, 1).text()
        mult = self.table.item(row, 2).text()

        self.input_name.setText(name)
        self.input_type.blockSignals(True)
        self.input_type.setCurrentText(p_type)
        self.input_type.blockSignals(False)
        self.input_sw.setText(mult)

    def refresh_table(self):
        self.table.setRowCount(0)
        for name, lp in self.model.load_patterns.items():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(lp.name))
            self.table.setItem(row, 1, QTableWidgetItem(lp.pattern_type))
            self.table.setItem(row, 2, QTableWidgetItem(str(lp.self_weight_multiplier)))

    def add_pattern(self):
        name = self.input_name.text().strip().upper()
        if not name:
            QMessageBox.warning(self, "Error", "Name cannot be empty.")
            return
        if name in self.model.load_patterns:
            QMessageBox.warning(self, "Error", f"Pattern '{name}' already exists.\nUse 'Modify' to update it.")
            return
            
        try:
            mult = float(self.input_sw.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Self Weight Multiplier must be a number.")
            return
            
        self.model.add_load_pattern(name, self.input_type.currentText(), mult)
        self.refresh_table()

    def modify_pattern(self):
        name = self.input_name.text().strip().upper()
        if not name: return

        if name not in self.model.load_patterns:
             QMessageBox.warning(self, "Error", f"Pattern '{name}' does not exist.\nUse 'Add New' to create it.")
             return

        try:
            mult = float(self.input_sw.text())
        except ValueError:
            QMessageBox.warning(self, "Error", "Self Weight Multiplier must be a number.")
            return

        lp = self.model.load_patterns[name]
        lp.pattern_type = self.input_type.currentText()
        lp.self_weight_multiplier = mult
        
        self.refresh_table()
        
        items = self.table.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.table.setCurrentItem(items[0])

    def delete_pattern(self):
        current_row = self.table.currentRow()
        if current_row < 0: return
        name = self.table.item(current_row, 0).text()
        del self.model.load_patterns[name]
        self.refresh_table()
        self.input_name.clear()
