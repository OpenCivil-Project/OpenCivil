
from .engine import wipe, project, open_model, save, solve

from .properties import (
    add_material, 
    add_rectangular_section, 
    add_circular_section, 
    add_i_section, 
    add_general_section
)

from .geometry import node, frame, support, release, modify_frame

from .loading import pattern, joint_load, dist_load, point_load

import subprocess
import os

def launch_gui():
    """
    Takes the currently active model and launches the PyQt6 OpenCivil application,
    loading the parametric model automatically.
    """
    from .engine import get_active_model
    model = get_active_model()
    
    if not hasattr(model, 'active_model_path') or not os.path.exists(model.active_model_path):
        print(" -> Error: Model file not found. Make sure to run oc.project() and oc.solve() first.")
        return
        
    print(f" -> API: Launching OPENCIVIL v0.4 GUI for '{model.name}'...")
    
    subprocess.Popen(["opencivil_gui", model.active_model_path])
