import json
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem, 
                             QHeaderView, QTabWidget, QPushButton, QHBoxLayout, QLabel)
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtCore import Qt

from core.units import unit_registry 

class ModalResultsDialog(QDialog):
    def __init__(self, results_data, parent=None):
        super().__init__(parent)
        self.results = results_data
        self.setWindowTitle("Analysis Results")
        self.resize(1100, 600)                              
        
        sf = unit_registry.force_scale
        sl = unit_registry.length_scale
        sm = sf / sl if sl != 0 else 1.0
        s_mom = sf * sl

        u_force = unit_registry.force_unit_name
        u_len = unit_registry.length_unit_name
        u_mass = f"{u_force}-s²/{u_len}"
        u_mass_rot = f"{u_force}-{u_len}-s²"
        
        u_acc = f"{u_len}/s²"

        layout = QVBoxLayout(self)
        
        lbl_title = QLabel(f"Analysis Report (Units: {unit_registry.current_unit_label})")
        lbl_title.setStyleSheet("font-size: 14pt; font-weight: bold; color: #333;")
        layout.addWidget(lbl_title)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        if "base_reaction" in self.results:
            br = self.results["base_reaction"]
            br_list = [{
                "Case": "Global Sum",
                "Fx": br["Fx"] * sf, "Fy": br["Fy"] * sf, "Fz": br["Fz"] * sf,
                "Mx": br["Mx"] * s_mom, "My": br["My"] * s_mom, "Mz": br["Mz"] * s_mom
            }]
            headers = ["Load Case", f"Global FX ({u_force})", f"Global FY ({u_force})", f"Global FZ ({u_force})", 
                       f"Global MX ({u_force}-{u_len})", f"Global MY ({u_force}-{u_len})", f"Global MZ ({u_force}-{u_len})"]
            self.tab_base_reac = self.create_table(headers, br_list, ["Case", "Fx", "Fy", "Fz", "Mx", "My", "Mz"])
            self.tabs.addTab(self.tab_base_reac, "Base Reactions")

        if "rsa_detailed" in self.results:
            rsa_dict = self.results["rsa_detailed"]
            
            rsa_headers = [
                "Mode", "Period (s)", "DampRatio", 
                f"U1 S_a ({u_acc})", f"U2 S_a ({u_acc})", f"U3 S_a ({u_acc})",
                f"U1 S_d ({u_len})", f"U2 S_d ({u_len})", f"U3 S_d ({u_len})"
            ]
            
            rsa_data_formatted = []

            for direction, table_rows in rsa_dict.items():
                for row in table_rows:
                                   
                    u1_acc, u2_acc, u3_acc = 0.0, 0.0, 0.0
                    u1_amp, u2_amp, u3_amp = 0.0, 0.0, 0.0
                    
                    acc_val = row["SaR_ms2"] * sl
                    amp_val = row["Sd"] * sl
                    
                    if direction == "X":
                        u1_acc = acc_val; u1_amp = amp_val
                    elif direction == "Y":
                        u2_acc = acc_val; u2_amp = amp_val
                    elif direction == "Z":
                        u3_acc = acc_val; u3_amp = amp_val

                    rsa_data_formatted.append({
                        "mode": row["mode"],
                        "T": row["T"],
                        "zeta": row.get("Damping", 0.05),
                        "U1a": u1_acc, "U2a": u2_acc, "U3a": u3_acc,
                        "U1d": u1_amp, "U2d": u2_amp, "U3d": u3_amp
                    })
            
            rsa_data_formatted.sort(key=lambda x: x["mode"])
                
            self.tab_rsa_info = self.create_table(
                rsa_headers, rsa_data_formatted,
                ["mode", "T", "zeta", "U1a", "U2a", "U3a", "U1d", "U2d", "U3d"]
            )
            self.tabs.addTab(self.tab_rsa_info, "RSA Modal Info")

        if "assembled_mass" in self.results:
            mass_data = []
            for nid, masses in self.results["assembled_mass"].items():
                mass_data.append({
                    "Node": nid,
                    "U1": masses[0] * sm, "U2": masses[1] * sm, "U3": masses[2] * sm,
                    "R1": masses[3] * s_mom, "R2": masses[4] * s_mom, "R3": masses[5] * s_mom
                })
            mass_data.sort(key=lambda x: int(x["Node"]) if x["Node"].isdigit() else x["Node"])
            
            sum_u1 = sum(d["U1"] for d in mass_data)
            sum_u2 = sum(d["U2"] for d in mass_data)
            sum_u3 = sum(d["U3"] for d in mass_data)
            mass_data.append({"Node": "SUM", "U1": sum_u1, "U2": sum_u2, "U3": sum_u3, "R1": "-", "R2": "-", "R3": "-"})
            
            m_headers = ["Joint", f"Mass X ({u_mass})", f"Mass Y ({u_mass})", f"Mass Z ({u_mass})", 
                         f"Mass Rx ({u_mass_rot})", f"Mass Ry ({u_mass_rot})", f"Mass Rz ({u_mass_rot})"]
            
            self.tab_mass = self.create_table(m_headers, mass_data, ["Node", "U1", "U2", "U3", "R1", "R2", "R3"])
            self.tabs.addTab(self.tab_mass, "Assembled Joint Masses")

        if "rsa_summary" in self.results:
            self.tab_summary = self.create_summary_table(self.results["rsa_summary"])
            self.tabs.addTab(self.tab_summary, "RSA Summary")

        if "tables" in self.results and "periods" in self.results["tables"]:
            self.tab_periods = self.create_table(
                ["Mode", "Period (sec)", "Frequency (Hz)", "Circ. Freq (rad/s)", "Eigenvalue"],
                self.results["tables"]["periods"],
                ["mode", "T", "f", "omega", "eigen"]
            )
            self.tabs.addTab(self.tab_periods, "Modal Periods")

            self.tab_ratios = self.create_table(
                ["Mode", "Ux Ratio", "Sum Ux", "Uy Ratio", "Sum Uy", "Uz Ratio", "Sum Uz"],
                self.results["tables"]["participation_mass"],
                ["mode", "Ux", "SumUx", "Uy", "SumUy", "Uz", "SumUz"]
            )
            self.tabs.addTab(self.tab_ratios, "Mass Participation")

        h_btns = QHBoxLayout()
        h_btns.addStretch()
        btn_close = QPushButton("Close")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        h_btns.addWidget(btn_close)
        layout.addLayout(h_btns)

    def create_table(self, headers, data_list, keys):
        table = QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setStyleSheet("QHeaderView::section { background-color: #f0f0f0; padding: 4px; border: 1px solid #d0d0d0; }")

        table.setRowCount(len(data_list))
        
        for row, entry in enumerate(data_list):
            for col, key in enumerate(keys):
                val = entry.get(key, 0)
                
                if col == 0:
                    txt = str(val)
                    item = QTableWidgetItem(txt)
                    item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                    item.setForeground(QColor("#0078D7"))
                else:
                                        
                    if isinstance(val, float):
                        if abs(val) < 1e-9 and val != 0: txt = f"{val:.4e}"
                        elif abs(val) < 0.001 and val != 0: txt = f"{val:.6f}"
                        else: txt = f"{val:.6f}"
                    else:
                        txt = str(val)
                    item = QTableWidgetItem(txt)
                
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, col, item)
                
        return table
    
    def create_summary_table(self, data_list):
        table = QTableWidget()
        headers = ["Parameter", "Value", "Description"]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setRowCount(len(data_list))
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        for row, entry in enumerate(data_list):
            table.setItem(row, 0, QTableWidgetItem(str(entry.get("label", ""))))
            val_item = QTableWidgetItem(f"{entry.get('value', 0)}")
            val_item.setForeground(QColor("#0078D7"))
            table.setItem(row, 1, val_item)
            table.setItem(row, 2, QTableWidgetItem(str(entry.get("desc", ""))))
        return table
