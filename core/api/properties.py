
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
