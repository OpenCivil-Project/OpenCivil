from .engine import get_active_model
from core.model import LoadCase

def add_response_spectrum(name, ss, s1, tl=6.0, r=8.0, d=3.0, i=1.0, site_class="ZB", direction="Horizontal", damping=0.05, interp="Linear"):
    """
    Defines a TSC-2018 Response Spectrum function and adds it to the active model.
    """
    model = get_active_model()
    
    if not hasattr(model, 'functions'):
        model.functions = {}
        
    model.functions[name] = {
        "type": "TSC-2018",
        "name": name,
        "Ss": float(ss),
        "S1": float(s1),
        "TL": float(tl),
        "R": float(r),
        "D": float(d),
        "I": float(i),
        "SiteClass": site_class,
        "Direction": direction,
        "Interpolation": interp, 
        "Damping": float(damping)
    }
    print(f" -> API: Added Response Spectrum Function '{name}' ({site_class}, Dir: {direction})")

def add_rsa_case(name, modal_comb="CQC", dir_comb="SRSS", modal_damping=0.05, loads=None):
    """
    Defines a Response Spectrum Analysis load case.
    
    Parameters
    ----------
    name          : str
    modal_comb    : str (Default: "CQC")
    dir_comb      : str (Default: "SRSS")
    modal_damping : float (Default: 0.05)
    loads         : list of tuples -> [(Direction, Function_Name, Scale_Factor)]
                    e.g., [("U1", "FUNC1", 9.81), ("U2", "FUNC2", 9.81)]
    """
    model = get_active_model()
    
    case = LoadCase(name, "Response Spectrum")
    case.modal_comb = modal_comb
    case.dir_comb = dir_comb
    case.modal_damping = float(modal_damping)
    case.rsa_loads = loads if loads else []
    
    model.load_cases[name] = case
    print(f" -> API: Added RSA Load Case '{name}' (Comb: {modal_comb}/{dir_comb})")
