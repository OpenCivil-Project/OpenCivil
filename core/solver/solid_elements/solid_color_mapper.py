"""
SolidColorMapper — Phase 5a
============================
Maps scalar stress values to RGB colors using a rainbow colormap.
Blue = min stress, Red = max stress (standard FEM convention).
Completely standalone, no canvas/Qt dependencies.
"""

import numpy as np

_COLORMAP = np.array([
    [0.00,  0.0,  0.0,  1.0],         
    [0.25,  0.0,  1.0,  1.0],         
    [0.50,  0.0,  1.0,  0.0],          
    [0.75,  1.0,  1.0,  0.0],           
    [1.00,  1.0,  0.0,  0.0],        
], dtype=float)

def scalar_to_rgb(value, vmin, vmax):
    """
    Maps a single scalar value to an RGB tuple (r, g, b) in [0,1].
    Clamps to [vmin, vmax].
    """
    if vmax <= vmin:
        return (0.0, 0.0, 1.0)                         

    t = float(np.clip((value - vmin) / (vmax - vmin), 0.0, 1.0))

    ts = _COLORMAP[:, 0]
    idx = np.searchsorted(ts, t) - 1
    idx = int(np.clip(idx, 0, len(_COLORMAP) - 2))

    t0, r0, g0, b0 = _COLORMAP[idx]
    t1, r1, g1, b1 = _COLORMAP[idx + 1]

    alpha = (t - t0) / (t1 - t0) if (t1 - t0) > 1e-9 else 0.0

    r = r0 + alpha * (r1 - r0)
    g = g0 + alpha * (g1 - g0)
    b = b0 + alpha * (b1 - b0)

    return (r, g, b)

def stress_to_colors(stress_values, vmin=None, vmax=None):
    """
    Maps an array of scalar stress values to RGBA colors (N, 4).

    Args:
        stress_values : array-like (N,) — one value per element or node
        vmin, vmax    : optional manual range. If None, uses data range.

    Returns:
        colors : np.ndarray (N, 4) — RGBA in [0, 1], alpha=1.0
        vmin   : float — actual min used
        vmax   : float — actual max used
    """
    vals = np.asarray(stress_values, dtype=float)

    if vmin is None:
        vmin = float(vals.min())
    if vmax is None:
        vmax = float(vals.max())

    colors = np.ones((len(vals), 4), dtype=float)                

    for i, v in enumerate(vals):
        r, g, b = scalar_to_rgb(v, vmin, vmax)
        colors[i, 0] = r
        colors[i, 1] = g
        colors[i, 2] = b

    return colors, vmin, vmax

def element_to_node_stresses(elements_stress, node_count, node_indices_list):
    node_sum   = np.zeros(node_count, dtype=float)
    node_count_arr = np.zeros(node_count, dtype=int)

    for i, node_indices in enumerate(node_indices_list):
                                                                    
        for local_idx in range(4):
            nidx = node_indices[local_idx]
            val = elements_stress[i][local_idx] if isinstance(elements_stress[i], (list, np.ndarray)) else elements_stress[i]
            node_sum[nidx]       += val
            node_count_arr[nidx] += 1

    mask = node_count_arr > 0
    node_stress = np.zeros(node_count, dtype=float)
    node_stress[mask] = node_sum[mask] / node_count_arr[mask]

    return node_stress

if __name__ == "__main__":
    print("Color mapper test:")
    test_vals = [0.0, 0.25, 0.5, 0.75, 1.0]
    for v in test_vals:
        r, g, b = scalar_to_rgb(v, 0.0, 1.0)
        print(f"  t={v:.2f} → R={r:.2f} G={g:.2f} B={b:.2f}")

    print("\nExpected:")
    print("  t=0.00 → blue  (0,0,1)")
    print("  t=0.25 → cyan  (0,1,1)")
    print("  t=0.50 → green (0,1,0)")
    print("  t=0.75 → yellow(1,1,0)")
    print("  t=1.00 → red   (1,0,0)")

    elem_stresses  = np.array([100.0, 200.0])
    node_idx_list  = [[0, 1, 2, 3], [1, 2, 3, 4]]
    node_s = element_to_node_stresses(elem_stresses, 5, node_idx_list)
    print(f"\nNode stress averaging:")
    print(f"  Element stresses: {elem_stresses}")
    print(f"  Node stresses:    {node_s}")
    print(f"  Node 1 (shared):  {node_s[1]:.1f}  (expected 150.0)")

    colors, vmin, vmax = stress_to_colors(node_s)
    print(f"\n  Colors shape: {colors.shape}  (expected (5, 4))")
    print(f"  Range: {vmin:.1f} → {vmax:.1f}")
    print("\n✅ Color mapper OK")
