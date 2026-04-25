                                    
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QCheckBox, 
                             QPushButton, QGroupBox, QRadioButton, QButtonGroup,
                             QScrollArea, QWidget, QLabel)

class ViewOptionsDialog(QDialog):
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Set Display Options")
        self.resize(500, 450)                             
        
        self.main_window = parent
        self.settings = current_settings or {}
        
        main_layout = QVBoxLayout(self)
        content_layout = QHBoxLayout()
        
        left_layout = QVBoxLayout()
        
        gen_group = QGroupBox("General")
        gen_vbox = QVBoxLayout()
        
        self.cb_extrude = QCheckBox("Extrude Frames")
        self.cb_extrude.setChecked(self.settings.get('extrude', True))
        
        self.cb_areas = QCheckBox("Show Shells/Areas")
        self.cb_areas.setToolTip("Show Floors and Walls")
        self.cb_areas.setChecked(self.settings.get('areas', True))
        
        gen_vbox.addWidget(self.cb_extrude)
        gen_vbox.addWidget(self.cb_areas)
        gen_group.setLayout(gen_vbox)
        
        joint_group = QGroupBox("Joints")
        joint_vbox = QVBoxLayout()
        
        self.cb_nodes = QCheckBox("Show Joints (Invisible)")
        self.cb_nodes.setChecked(self.settings.get('joints', True))
        
        self.cb_supports = QCheckBox("Show Supports")
        self.cb_supports.setChecked(self.settings.get('supports', True))
        
        self.cb_constraints = QCheckBox("Show Diaphragms")
        self.cb_constraints.setToolTip("Show Master Nodes and Spiderwebs")
        self.cb_constraints.setStyleSheet("color: green;")
        self.cb_constraints.setChecked(self.settings.get('constraints', True))

        joint_vbox.addWidget(self.cb_nodes)
        joint_vbox.addWidget(self.cb_supports)
        joint_vbox.addWidget(self.cb_constraints)
        joint_group.setLayout(joint_vbox)
        
        left_layout.addWidget(gen_group)
        left_layout.addWidget(joint_group)
        left_layout.addStretch()

        right_layout = QVBoxLayout()
        
        frame_group = QGroupBox("Frames / Cables")
        frame_vbox = QVBoxLayout()
        
        self.cb_releases = QCheckBox("Releases (Partial Fixity)")
        self.cb_releases.setChecked(self.settings.get('releases', True))
        
        self.chk_axes = QCheckBox("Local Axes")
        self.chk_axes.setStyleSheet("color: blue;")
        self.chk_axes.setChecked(self.settings.get('axes', False))

        frame_vbox.addWidget(self.chk_axes)
        frame_vbox.addWidget(self.cb_releases)
        frame_group.setLayout(frame_vbox)
        
        loads_group = QGroupBox("Loads")
        loads_vbox = QVBoxLayout()
        
        self.cb_show_loads = QCheckBox("Show Loads")
        self.cb_show_loads.setChecked(self.settings.get('loads', True))
        self.cb_show_loads.toggled.connect(self.toggle_load_options)
        loads_vbox.addWidget(self.cb_show_loads)
        
        loads_vbox.addWidget(QLabel("Load Type:"))
        self.rb_nodal = QRadioButton("Nodal Only")
        self.rb_frame = QRadioButton("Frame Only")
        self.rb_both = QRadioButton("Both")
        self.rb_both.setChecked(True)           
        
        self.load_type_group = QButtonGroup()
        self.load_type_group.addButton(self.rb_nodal)
        self.load_type_group.addButton(self.rb_frame)
        self.load_type_group.addButton(self.rb_both)
        
        loads_vbox.addWidget(self.rb_nodal)
        loads_vbox.addWidget(self.rb_frame)
        loads_vbox.addWidget(self.rb_both)
        
        loads_vbox.addWidget(QLabel("Visible Patterns:"))
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(120)
        
        scroll_widget = QWidget()
        self.pattern_layout = QVBoxLayout(scroll_widget)
        self.pattern_checkboxes = {}
        
        if self.main_window and self.main_window.model:
            saved_patterns = self.settings.get('visible_patterns', None)
            for pattern_name in self.main_window.model.load_patterns.keys():
                cb = QCheckBox(pattern_name)
                                                                                                
                if saved_patterns is None:
                    cb.setChecked(True)
                else:
                    cb.setChecked(pattern_name in saved_patterns)
                
                self.pattern_checkboxes[pattern_name] = cb
                self.pattern_layout.addWidget(cb)
        
        scroll.setWidget(scroll_widget)
        loads_vbox.addWidget(scroll)
        
        loads_group.setLayout(loads_vbox)
        
        right_layout.addWidget(frame_group)
        right_layout.addWidget(loads_group)
        right_layout.addStretch()

        content_layout.addLayout(left_layout, 1)
        content_layout.addLayout(right_layout, 1)
        main_layout.addLayout(content_layout)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_ok = QPushButton("OK")
        btn_ok.clicked.connect(self.on_ok)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_apply = QPushButton("Apply")
        btn_apply.clicked.connect(self.on_apply)
        
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_apply)
        main_layout.addLayout(btn_layout)
        
        self.toggle_load_options(self.cb_show_loads.isChecked())

    def toggle_load_options(self, enabled):
        """Enable/disable load filter options based on master toggle"""
        self.rb_nodal.setEnabled(enabled)
        self.rb_frame.setEnabled(enabled)
        self.rb_both.setEnabled(enabled)
        for cb in self.pattern_checkboxes.values():
            cb.setEnabled(enabled)

    def get_data(self):
                                
        if self.rb_nodal.isChecked():
            load_type = "nodal"
        elif self.rb_frame.isChecked():
            load_type = "frame"
        else:
            load_type = "both"
        
        visible_patterns = [
            name for name, cb in self.pattern_checkboxes.items() 
            if cb.isChecked()
        ]
        
        if not visible_patterns:
            visible_patterns = ['__NONE__']
        
        return {
            'extrude': self.cb_extrude.isChecked(),
            'areas': self.cb_areas.isChecked(),
            'joints': self.cb_nodes.isChecked(),
            'supports': self.cb_supports.isChecked(),
            'constraints': self.cb_constraints.isChecked(),
            'releases': self.cb_releases.isChecked(),
            'loads': self.cb_show_loads.isChecked(),
            'axes': self.chk_axes.isChecked(),
                         
            'load_type': load_type,
            'visible_patterns': visible_patterns
        }

    def on_apply(self):
        if self.parent(): 
            self.parent().apply_view_options(self.get_data())

    def on_ok(self):
        if self.parent(): 
            self.parent().apply_view_options(self.get_data())
        self.accept()
