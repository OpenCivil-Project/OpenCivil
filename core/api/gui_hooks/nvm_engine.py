"""
nvm_engine.py  —  Pure math layer for member force / NVM computation.
No PyQt. No GUI. Borrowed logic from FBDViewerDialog in spy_dialogs.py.
Both spy_dialogs (GUI) and result_helper (API) can call this.
"""

import numpy as np

def compute_end_forces(element_id, model, results: dict, matrices: dict):
    """
    Computes the 12-DOF local end force vector for a frame element.
    Returns a numpy array of shape (12,) in base SI units, or None on failure.

    Formula: f_local = k @ (T @ u_global) + fef
    """
    eid = str(element_id)

    if eid not in matrices:
        raise KeyError(f"Element {element_id} not found in matrices data.")
    if int(element_id) not in model.elements:
        raise KeyError(f"Element {element_id} not found in model.")

    k   = np.array(matrices[eid]['k'])
    t   = np.array(matrices[eid]['t'])
    fef = np.array(matrices[eid]['fef'])

    el = model.elements[int(element_id)]
    n1_id = str(el.node_i.id)
    n2_id = str(el.node_j.id)

    base_dict = results.get("_base_displacements", results.get("displacements", {}))
    u1 = base_dict.get(n1_id, [0.0] * 6)
    u2 = base_dict.get(n2_id, [0.0] * 6)

    u_global = np.array(u1 + u2)
    return k @ (t @ u_global) + fef

def compute_nvm_data(element_id, model, results: dict, matrices: dict):
    """
    Computes NVM + deflection along 101 stations of a frame element.

    Returns a dict with keys:
        stations  — (101,) array, positions from 0 to L in metres
        P         — Axial force
        V2, V3    — Shear (major / minor axis)
        M2, M3    — Moment (major / minor axis)
        Defl_2_Rel, Defl_3_Rel  — Relative deflection
        Defl_2_Abs, Defl_3_Abs  — Absolute deflection
        L         — element length (m)
    """
    eid = str(element_id)
    forces_base = compute_end_forces(element_id, model, results, matrices)

    el = model.elements[int(element_id)]
    L  = el.length()

    t_matrix = np.array(matrices[eid]['t'])
    R_3x3    = t_matrix[0:3, 0:3]

    n1_id = str(el.node_i.id)
    n2_id = str(el.node_j.id)
    base_dict = results.get("_base_displacements", results.get("displacements", {}))
    u_global  = np.array(base_dict.get(n1_id, [0.0]*6) + base_dict.get(n2_id, [0.0]*6))
    u_local   = t_matrix @ u_global
    u1_l, v1, w1, thx1, thy1, thz1 = u_local[0:6]
    u2_l, v2, w2, thx2, thy2, thz2 = u_local[6:12]

    Fx1, Fy1, Fz1, Mx1, My1, Mz1 = forces_base[0:6]

    w_loc = np.zeros(3)
    point_loads = []

    active_case_name = results.get("info", {}).get("case_name", "")

    if active_case_name in model.load_cases:
        active_case = model.load_cases[active_case_name]
        for pat_name, scale_factor in active_case.loads:
            if pat_name in model.load_patterns:
                pat = model.load_patterns[pat_name]
                if pat.self_weight_multiplier > 0:
                    area    = getattr(el.section, 'A', 0)
                    density = getattr(el.section.material, 'density', 0)
                    w_sw_mag    = area * density * pat.self_weight_multiplier * scale_factor
                    w_sw_global = np.array([0.0, 0.0, -w_sw_mag])
                    w_loc += R_3x3 @ w_sw_global

    for load in model.loads:
        if getattr(load, 'element_id', None) == int(element_id):
            is_local = getattr(load, 'coord_system', 'Global').lower() == 'local'

            if hasattr(load, 'wx'):                               
                w_vec = np.array([load.wx, load.wy, load.wz])
                if not is_local:
                    w_vec = R_3x3 @ w_vec
                w_loc += w_vec

            elif hasattr(load, 'force'):                                 
                a = load.dist * L if getattr(load, 'is_relative', False) else load.dist
                dir_map = {'X': 0, 'Y': 1, 'Z': 2, '1': 0, '2': 1, '3': 2}
                idx = dir_map.get(str(getattr(load, 'direction', 'Z')).upper(), 2)
                vec = np.zeros(3)
                vec[idx] = load.force
                if not is_local:
                    vec = R_3x3 @ vec
                l_type = getattr(load, 'load_type', 'Force').lower()
                if l_type == 'moment':
                    point_loads.append({'a': a, 'F': np.zeros(3), 'M': vec})
                else:
                    point_loads.append({'a': a, 'F': vec, 'M': np.zeros(3)})

    stations   = np.linspace(0, L, 101)
    P          = np.zeros(101)
    V2         = np.zeros(101);  M3         = np.zeros(101)
    V3         = np.zeros(101);  M2         = np.zeros(101)
    Defl_2_Rel = np.zeros(101);  Defl_3_Rel = np.zeros(101)
    Defl_2_Abs = np.zeros(101);  Defl_3_Abs = np.zeros(101)

    E   = getattr(el.section.material, 'E', 1.0)
    I33 = getattr(el.section, 'I33', 1.0)
    I22 = getattr(el.section, 'I22', 1.0)

    for i, x in enumerate(stations):
        xi = x / L if L > 0 else 0.0

        P[i]  = -Fx1 - w_loc[0] * x
        V2[i] = -(Fy1 + w_loc[1] * x)
        V3[i] = -(Fz1 + w_loc[2] * x)
        M3[i] =  Mz1 + Fy1 * x + w_loc[1] * (x**2) / 2.0
        M2[i] =  My1 + Fz1 * x + w_loc[2] * (x**2) / 2.0

        for pl in point_loads:
            a = pl['a']
            if x > a:
                dx = x - a
                P[i]  -= pl['F'][0]
                V2[i] -= pl['F'][1]
                V3[i] -= pl['F'][2]
                M3[i] += pl['F'][1] * dx - pl['M'][2]
                M2[i] += pl['F'][2] * dx - pl['M'][1]

        N1 = 1 - 3*xi**2 + 2*xi**3
        N2 = x * (1 - 2*xi + xi**2)
        N3 = 3*xi**2 - 2*xi**3
        N4 = x * (xi**2 - xi)

        d2_abs = N1*v1 + N2*thz1  + N3*v2 + N4*thz2
        d3_abs = N1*w1 + N2*(-thy1) + N3*w2 + N4*(-thy2)

        chord_2 = v1 + (v2 - v1) * xi
        chord_3 = w1 + (w2 - w1) * xi

        bubble_2 = (w_loc[1] * (x**2) * ((L - x)**2)) / (24 * E * I33) if I33 > 0 else 0.0
        bubble_3 = (w_loc[2] * (x**2) * ((L - x)**2)) / (24 * E * I22) if I22 > 0 else 0.0

        Defl_2_Rel[i] = (d2_abs - chord_2) + bubble_2
        Defl_3_Rel[i] = (d3_abs - chord_3) + bubble_3
        Defl_2_Abs[i] = d2_abs + bubble_2
        Defl_3_Abs[i] = d3_abs + bubble_3

    return {
        'stations':   stations,
        'P':          P,
        'V2':         V2,   'V3': V3,
        'M2':         M2,   'M3': M3,
        'Defl_2_Rel': Defl_2_Rel, 'Defl_3_Rel': Defl_3_Rel,
        'Defl_2_Abs': Defl_2_Abs, 'Defl_3_Abs': Defl_3_Abs,
        'L':          L,
    }
