from .engine import get_active_model

def node(x, y, z):
    """
    Adds a node to the active model and returns its ID.
    Returning the ID is a game-changer for parametric loops!
    """
    model = get_active_model()
    n = model.add_node(x, y, z)
                                                                                                                  
    return n.id 

def frame(i_node_id, j_node_id, sec_name):
    """Adds a frame element connecting two existing node IDs."""
    model = get_active_model()
    
    try:
        n1 = model.nodes[i_node_id]
        n2 = model.nodes[j_node_id]
        sec = model.sections[sec_name]
    except KeyError as e:
        raise ValueError(f"Geometry error: Could not find {e}. Ensure nodes and sections are defined first.")

    el = model.add_element(n1, n2, sec)
    return el.id

def support(node_id, u_x, u_y, u_z, r_x, r_y, r_z):
    """
    Assigns support restraints to a node.
    Takes True/False (or 1/0) for the 6 degrees of freedom.
    """
    model = get_active_model()
    restraints = [bool(u_x), bool(u_y), bool(u_z), bool(r_x), bool(r_y), bool(r_z)]
    model.nodes[node_id].restraints = restraints
    print(f" -> API: Node {node_id} supports set to {restraints}")

def release(frame_id, end, m33=False, m22=False, t=False, v2=False, v3=False, p=False):
    """
    Assigns end releases to a frame. 
    By default, everything is False (fixed). Users only set what they want to release!
    """
    model = get_active_model()
    
    rels = [p, v2, v3, t, m22, m33] 
    
    if end.lower() == 'i':
        model.elements[frame_id].releases_i = rels
    elif end.lower() == 'j':
        model.elements[frame_id].releases_j = rels
    else:
        raise ValueError("End must be 'i' or 'j'.")
        
    print(f" -> API: Frame {frame_id} end '{end}' releases set.")

def modify_frame(frame_id, cardinal=None, offset_i=None, offset_j=None, beta=None):
    """Modifies frame properties like cardinal point, offsets, or beta angle."""
    model = get_active_model()
    el = model.elements[frame_id]
    
    if cardinal is not None: el.cardinal_point = int(cardinal)
    if offset_i is not None: el.end_offset_i = float(offset_i)
    if offset_j is not None: el.end_offset_j = float(offset_j)
    if beta is not None:     el.beta_angle = float(beta)
