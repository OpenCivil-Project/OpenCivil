from .engine import wipe, project, open_model, save, solve, get_active_model

from .properties import (
    add_material, 
    add_rectangular_section, 
    add_circular_section, 
    add_i_section, 
    add_general_section,
    add_mass_source,
)

from .geometry import node, frame, support, release, modify_frame

from .loading import pattern, joint_load, dist_load, point_load

from .dynamic import add_response_spectrum, add_rsa_case

from .result_helper import (
    show_displacements,
    show_node_displacements,
    show_reactions,
    show_base_reactions,
    show_periods,
    show_mass_participation,
    show_node_shape,
    show_member_forces,
    show_nvm_table,
    plot_nvm,
                                
    show_rsa_summary,
    show_rsa_detailed
)

import subprocess
import os

def launch_gui():
    """
    Takes the currently active model and launches the PyQt6 OpenCivil application,
    loading the parametric model automatically.
    """
    model = get_active_model()
    
    if not hasattr(model, 'active_model_path') or not os.path.exists(model.active_model_path):
        print(" -> Error: Model file not found. Make sure to run oc.project() and oc.solve() first.")
        return
        
    print(f" -> API: Launching OPENCIVIL v0.4 GUI for '{model.name}'...")
    
    subprocess.Popen(["opencivil_gui", model.active_model_path])
