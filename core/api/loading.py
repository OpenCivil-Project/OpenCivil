
from .engine import get_active_model

def pattern(name, pattern_type="DEAD", sw_mult=0.0):
    """
    Defines a load pattern.
    Default type is 'DEAD' and default self-weight multiplier is 0.0.
    """
    model = get_active_model()
    model.add_load_pattern(name, pattern_type, float(sw_mult))
    print(f" -> API: Added Load Pattern '{name}' (SW Mult: {sw_mult})")

def joint_load(node_id, pattern_name, fx=0.0, fy=0.0, fz=0.0, mx=0.0, my=0.0, mz=0.0):
    """
    Applies a point load or moment to a specific node.
    Users only need to specify the non-zero components!
    """
    model = get_active_model()
    
    model.assign_joint_load(node_id, pattern_name, fx=fx, fy=fy, fz=fz, mx=mx, my=my, mz=mz)
    
    applied = ", ".join(f"{k}={v}" for k, v in zip(["fx", "fy", "fz", "mx", "my", "mz"], [fx, fy, fz, mx, my, mz]) if v != 0.0)
    print(f" -> API: Nodal load on Node {node_id} [{pattern_name}]: {applied or '(zero)'}")

def dist_load(frame_id, pattern_name, wx=0.0, wy=0.0, wz=0.0, coord_system="Global"):
    """
    Applies a uniformly distributed load to a frame element.
    """
    model = get_active_model()
    model.assign_member_load(frame_id, pattern_name, wx, wy, wz, coord_system=coord_system)
    print(f" -> API: Dist load on Beam {frame_id} [{pattern_name}]: wx={wx}, wy={wy}, wz={wz} ({coord_system})")

def point_load(frame_id, pattern_name, force, rel_dist, direction="z"):
    """
    Applies a point load at a specific relative distance (0.0 to 1.0) along a frame.
    """
    model = get_active_model()
    
    model.assign_member_point_load(frame_id, pattern_name, force, rel_dist, True, "Global", direction, "Force")
    print(f" -> API: Added {force}kN point load on Beam {frame_id} at rel_dist {rel_dist} (dir: {direction})")
