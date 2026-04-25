
from core.properties import (Material, RectangularSection, ISection, GeneralSection,
                             CircularSection, PipeSection, TubeSection, TrapezoidalSection)

from .engine import get_active_model

def add_material(name, E, nu, rho, mat_type):
    """Defines a new material and adds it to the active model."""
    model = get_active_model()
    
    new_mat = Material(name, E=E, nu=nu, density=rho, mat_type=mat_type)
    model.add_material(new_mat)
    print(f" -> API: Added Material '{name}'")

def add_rectangular_section(name, mat_name, b, h):
    """Adds a rectangular section to the active model."""
    model = get_active_model()
    if mat_name not in model.materials:
        raise ValueError(f"Material '{mat_name}' not found. Define it first.")
    
    mat = model.materials[mat_name]
    sec = RectangularSection(name, mat, b=b, h=h)
    model.add_section(sec)
    print(f" -> API: Added Rectangular Section '{name}'")

def add_circular_section(name, mat_name, d):
    """Adds a solid circular section to the active model."""
    model = get_active_model()
    mat = model.materials[mat_name]
    sec = CircularSection(name, mat, d=d)
    model.add_section(sec)
    print(f" -> API: Added Circular Section '{name}'")

def add_i_section(name, mat_name, h, w_t, t_t, w_b, t_b, t_w):
    """Adds an I-Section to the active model."""
    model = get_active_model()
    mat = model.materials[mat_name]
    sec = ISection(name, mat, h, w_t, t_t, w_b, t_b, t_w)
    model.add_section(sec)
    print(f" -> API: Added I-Section '{name}'")

def add_general_section(name, mat_name, A, J, I33, I22, Asy, Asz):
    """Adds a general section using explicitly defined properties."""
    model = get_active_model()
    mat = model.materials[mat_name]
    props_dict = {'A': A, 'J': J, 'I33': I33, 'I22': I22, 'Asy': Asy, 'Asz': Asz}
    sec = GeneralSection(name, mat, props_dict)
    model.add_section(sec)
    print(f" -> API: Added General Section '{name}'")

def add_mass_source(name="Default", include_self_mass=True, patterns=None):
    """
    Defines a Mass Source and sets it as active for modal analysis.
    Mirrors the GUI 'Mass Source Data' dialog.

    Parameters
    ----------
    name              : str   — mass source name (default "Default")
    include_self_mass : bool  — include element self mass (default True)
    patterns          : dict  — {pattern_name: multiplier} for load-pattern-based mass
                                e.g. {"DEAD": 1.0, "LIVE": 0.25}
                                ⚠ WARNING: if a pattern has sw_mult > 0 AND
                                include_self_mass=True, self-weight is double counted!

    Examples
    --------
    # Self mass only (most common for steel structures)
    oc.add_mass_source("MSS1", include_self_mass=True)

    # Load pattern only (common for concrete with superimposed loads)
    oc.add_mass_source("MSS1", include_self_mass=False,
                       patterns={"DEAD": 1.0, "LIVE": 0.25})

    # Both (be careful of double counting if DEAD has sw_mult > 0)
    oc.add_mass_source("MSS1", include_self_mass=True,
                       patterns={"LIVE": 0.25})
    """
    from core.model import MassSource
    model = get_active_model()

    ms = MassSource(name)
    ms.include_self_mass = include_self_mass
    ms.load_patterns = []

    if patterns:
        ms.include_patterns = True
        for pat_name, mult in patterns.items():
            if pat_name not in model.load_patterns:
                raise ValueError(f"Load pattern '{pat_name}' not found. Define it first with oc.pattern().")
            ms.load_patterns.append((pat_name, float(mult)))
    else:
        ms.include_patterns = False

    if not hasattr(model, 'mass_sources'):
        model.mass_sources = {}

    model.mass_sources[name] = ms
    model.active_mass_source = name

    pat_info = f", patterns={patterns}" if patterns else ""
    print(f" -> API: Mass Source '{name}' | self_mass={include_self_mass}{pat_info}")
