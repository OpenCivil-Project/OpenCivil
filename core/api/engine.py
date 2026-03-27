import os
from core.model import StructuralModel
from core.solver.linear_static.main_engine import run_linear_static_analysis

_active_model = None

def wipe():
    """Clears the current model from memory (Essential for scripting)."""
    global _active_model
    _active_model = None
    print(" -> Model wiped from memory.")

def project(name, base_dir):
    """Creates a new OpenCivil project and sets it as the active model."""
    global _active_model
    
    _active_model = StructuralModel(name=name)
    
    proj_dir = os.path.normpath(os.path.join(base_dir, name))
    os.makedirs(proj_dir, exist_ok=True)
    
    model_path = os.path.join(proj_dir, f"{name}.mf")
    results_path = os.path.join(proj_dir, f"{name}_results.json")
    
    _active_model.active_project_dir = proj_dir
    _active_model.active_model_path = model_path
    _active_model.active_results_path = results_path
    
    _active_model.save_to_file(model_path)
    print(f" -> Project '{name}' ready at: {proj_dir}")

def open_model(filepath):
    """Loads an existing .mf file into the active model."""
    global _active_model
    
    filepath = os.path.normpath(filepath)
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Error: File not found: {filepath}")
        
    proj_name = os.path.splitext(os.path.basename(filepath))[0]
    _active_model = StructuralModel(name=proj_name)
    _active_model.load_from_file(filepath)
    
    proj_dir = os.path.dirname(os.path.abspath(filepath))
    _active_model.active_project_dir = proj_dir
    _active_model.active_model_path = filepath
    _active_model.active_results_path = os.path.join(proj_dir, f"{proj_name}_results.json")
    
    print(f" -> Loaded '{_active_model.name}' | Nodes: {len(_active_model.nodes)}, Elements: {len(_active_model.elements)}")

def save():
    """Saves the active model to its file path."""
    global _active_model
    if _active_model is None or not hasattr(_active_model, 'active_model_path'):
        raise RuntimeError("No active project to save. Run 'project()' first.")
    
    _active_model.save_to_file(_active_model.active_model_path)
    print(f" -> Saved to: {_active_model.active_model_path}")

def solve():
    """Saves the active model and runs the linear static solver."""
    global _active_model
    if _active_model is None or not hasattr(_active_model, 'active_model_path'):
        raise RuntimeError("No active project to solve. Run 'project()' first.")
        
    _active_model.save_to_file(_active_model.active_model_path)
    print(f" -> Saved. Solving Project: {_active_model.active_project_dir}")
    
    run_linear_static_analysis(_active_model.active_model_path, _active_model.active_results_path)
    print("\n\u2705 SUCCESS! Check your folder for results and matrices.")

def get_active_model():
    """Internal helper function used by other API files to get the current model."""
    global _active_model
    if _active_model is None:
        raise RuntimeError("No active model! Call 'project()' or 'open_model()' first.")
    return _active_model
