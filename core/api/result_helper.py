"""
result_helper.py  —  OpenCivil Parametric API: Results Layer
Full parity with AnalysisResultsDialog, NodeResultsDialog, and FBDViewerDialog.
No PyQt required. Terminal tables + matplotlib plots.
"""

import json
import os

from .engine import get_active_model
from .gui_hooks.nvm_engine import compute_end_forces, compute_nvm_data

def _load_results(path=None):
    model = get_active_model()
    res_path = path or getattr(model, 'active_results_path', None)
    if not res_path or not os.path.exists(res_path):
        raise FileNotFoundError("Results not found. Did you run solve() first?")
    with open(res_path) as f:
        data = json.load(f)
    if data.get("status") != "SUCCESS":
        raise RuntimeError(f"Solver failed: {data.get('error')}")
    return data

def _load_modal_results():
    model = get_active_model()
    res_path = getattr(model, 'active_modal_results_path', None)
    if not res_path or not os.path.exists(res_path):
        raise FileNotFoundError("Modal results not found. Did you run solve_modal() first?")
    with open(res_path) as f:
        data = json.load(f)
    if data.get("status") != "SUCCESS":
        raise RuntimeError(f"Modal solver failed: {data.get('error')}")
    return data

def _load_matrices():
    """Finds and loads the _matrices.json for the active solve case."""
    model   = get_active_model()
    res_path = getattr(model, 'active_results_path', None)
    if not res_path:
        raise FileNotFoundError("No active results path. Run solve() first.")
                                                                  
    mat_path = res_path.replace("_results.json", "_matrices.json")
    if not os.path.exists(mat_path):
        raise FileNotFoundError(f"Matrices file not found: {mat_path}")
    with open(mat_path) as f:
        return json.load(f)

def _divider(width=65, char="─"):
    return char * width

def _fmt(val, threshold=1e-9):
    """Smart numeric formatter matching GUI behaviour."""
    if isinstance(val, (int, str)):
        return str(val)
    if abs(val) < threshold:
        return "0.0"
    if abs(val) < 1e-3:
        return f"{val:.4e}"
    return f"{val:.6f}"

def show_displacements():
    """Prints displacement table for ALL nodes (linear static)."""
    data  = _load_results()
    disps = data.get("displacements", {})

    print("\n" + _divider(85, "═"))
    print(f"{'NODE DISPLACEMENTS':^85}")
    print(_divider(85, "═"))
    print(f"{'Node':<8} {'UX':>12} {'UY':>12} {'UZ':>12} {'RX':>12} {'RY':>12} {'RZ':>12}")
    print(_divider(85))

    for nid in sorted(disps.keys(), key=lambda x: int(x) if x.isdigit() else x):
        v = disps[nid]
        print(f"{nid:<8} {_fmt(v[0]):>12} {_fmt(v[1]):>12} {_fmt(v[2]):>12} "
              f"{_fmt(v[3]):>12} {_fmt(v[4]):>12} {_fmt(v[5]):>12}")

    print(_divider(85, "═") + "\n")

def show_node_displacements(node_id):
    """Prints all 6 DOF displacements for a single node (linear static)."""
    data    = _load_results()
    base    = data.get("_base_displacements", data.get("displacements", {}))
    nid     = str(node_id)
    vector  = base.get(nid)

    if vector is None:
        print(f"  ⚠  Node {node_id} not found in results.")
        return

    labels = ["Trans X", "Trans Y", "Trans Z", "Rot X  ", "Rot Y  ", "Rot Z  "]
    units  = ["m", "m", "m", "rad", "rad", "rad"]

    print(f"\n{'─'*40}")
    print(f"  Joint {node_id} — Linear Static Displacements")
    print(f"{'─'*40}")
    for lbl, u, val in zip(labels, units, vector):
        print(f"  {lbl} [{u}]:  {_fmt(val)}")
    print(f"{'─'*40}\n")

def show_reactions():
    """Prints support reactions for all restrained nodes."""
    data  = _load_results()
    reacs = data.get("reactions", {})

    print("\n" + _divider(85, "═"))
    print(f"{'SUPPORT REACTIONS':^85}")
    print(_divider(85, "═"))
    print(f"{'Node':<8} {'FX':>12} {'FY':>12} {'FZ':>12} {'MX':>12} {'MY':>12} {'MZ':>12}")
    print(_divider(85))

    for nid in sorted(reacs.keys(), key=lambda x: int(x) if x.isdigit() else x):
        v = reacs[nid]
                                   
        if all(abs(x) < 1e-6 for x in v):
            continue
        print(f"{nid:<8} {_fmt(v[0]):>12} {_fmt(v[1]):>12} {_fmt(v[2]):>12} "
              f"{_fmt(v[3]):>12} {_fmt(v[4]):>12} {_fmt(v[5]):>12}")

    print(_divider(85, "═") + "\n")

def show_base_reactions():
    """Prints the global base reaction resultant."""
    data = _load_results()
    br   = data.get("base_reaction")
    if not br:
        print("  ⚠  No base reaction data in results.")
        return

    print(f"\n{'─'*45}")
    print(f"  GLOBAL BASE REACTIONS")
    print(f"{'─'*45}")
    for key in ["Fx", "Fy", "Fz", "Mx", "My", "Mz"]:
        print(f"  {key:>4}:  {_fmt(br[key])}")
    print(f"{'─'*45}\n")

def show_periods():
    """Prints modal periods and frequencies table."""
    data = _load_modal_results()

    print("\n" + _divider(65, "═"))
    print(f"{'MODAL PERIODS & FREQUENCIES':^65}")
    print(_divider(65, "═"))
    print(f"{'Mode':<8} {'Period (s)':>12} {'Freq (Hz)':>12} {'ω (rad/s)':>12}")
    print(_divider(65))

    for row in data['tables']['periods']:
        print(f"{row['mode']:<8} {row['T']:>12.4f} {row['f']:>12.4f} {row.get('omega', 0.0):>12.4f}")

    print(_divider(65, "═") + "\n")

def show_mass_participation():
    """Prints mass participation ratios table."""
    data = _load_modal_results()

    print("\n" + _divider(80, "═"))
    print(f"{'MASS PARTICIPATION RATIOS':^80}")
    print(_divider(80, "═"))
    print(f"{'Mode':<6} {'UX':>8} {'ΣUX':>8} {'UY':>8} {'ΣUY':>8} {'UZ':>8} {'ΣUZ':>8} {'RX':>8} {'RY':>8} {'RZ':>8}")
    print(_divider(80))

    for row in data['tables']['participation_mass']:
        print(f"{row['mode']:<6} "
              f"{row['Ux']:>8.4f} {row['SumUx']:>8.4f} "
              f"{row['Uy']:>8.4f} {row['SumUy']:>8.4f} "
              f"{row['Uz']:>8.4f} {row['SumUz']:>8.4f} "
              f"{row.get('Rx', 0):>8.4f} "
              f"{row.get('Ry', 0):>8.4f} "
              f"{row.get('Rz', 0):>8.4f}")

    print(_divider(80, "═") + "\n")

def show_node_shape(node_id, mode: int):
    """Prints normalized mode shape DOFs for a single node at a given mode number."""
    data   = _load_modal_results()
    shapes = data.get("mode_shapes", {})
    key    = f"Mode {mode}"

    if key not in shapes:
        print(f"  ⚠  {key} not found in modal results.")
        return

    nid    = str(node_id)
    vector = shapes[key].get(nid)

    if vector is None:
        print(f"  ⚠  Node {node_id} not found in {key}.")
        return

    labels = ["U1", "U2", "U3", "R1", "R2", "R3"]
    print(f"\n{'─'*40}")
    print(f"  Joint {node_id} — Mode {mode} Shape (Normalized)")
    print(f"{'─'*40}")
    for lbl, val in zip(labels, vector):
        print(f"  {lbl}:  {_fmt(val)}")
    print(f"{'─'*40}\n")

def show_member_forces(frame_id):
    """
    Prints the 12 local end forces for a frame element.
    I-end: [P, V2, V3, T, M2, M3]  J-end: [P, V2, V3, T, M2, M3]
    """
    model    = get_active_model()
    results  = _load_results()
    matrices = _load_matrices()

    forces = compute_end_forces(frame_id, model, results, matrices)

    labels = ["P (Axial)", "V2 (Shear)", "V3 (Shear)", "T (Torsion)", "M2 (Moment)", "M3 (Moment)"]

    print(f"\n{'─'*50}")
    print(f"  Frame {frame_id} — Local End Forces")
    print(f"{'─'*50}")
    print(f"  {'DOF':<18} {'I-End':>12} {'J-End':>12}")
    print(f"  {'─'*42}")
    for i, lbl in enumerate(labels):
        print(f"  {lbl:<18} {_fmt(forces[i]):>12} {_fmt(forces[i+6]):>12}")
    print(f"{'─'*50}\n")

def show_nvm_table(frame_id, stations=11):
    """
    Prints NVM values at evenly spaced stations along a frame element.
    `stations` controls how many rows to print (default 11 = every 10%).
    """
    model    = get_active_model()
    results  = _load_results()
    matrices = _load_matrices()

    nvm  = compute_nvm_data(frame_id, model, results, matrices)
    L    = nvm['L']
    idxs = [round(i * 100 / (stations - 1)) for i in range(stations)]

    print(f"\n{'─'*90}")
    print(f"  Frame {frame_id} — NVM Table  (L = {L:.4f} m)")
    print(f"{'─'*90}")
    print(f"  {'x (m)':<10} {'x/L':>6} {'P':>12} {'V2':>12} {'V3':>12} {'M2':>14} {'M3':>14}")
    print(f"  {'─'*84}")

    for idx in idxs:
        x = nvm['stations'][idx]
        print(f"  {x:<10.4f} {x/L:>6.2f} "
              f"{_fmt(nvm['P'][idx]):>12} "
              f"{_fmt(nvm['V2'][idx]):>12} "
              f"{_fmt(nvm['V3'][idx]):>12} "
              f"{_fmt(nvm['M2'][idx]):>14} "
              f"{_fmt(nvm['M3'][idx]):>14}")

    print(f"{'─'*90}\n")

def plot_nvm(frame_id, deflection='relative', save_path=None):
    """
    Plots NVM diagrams for a frame element — both major AND minor axis
    side by side in one figure, matching the GUI FBDViewerDialog layout.

    Parameters
    ----------
    frame_id   : int
    deflection : 'relative' (default) or 'absolute'
    save_path  : if given, saves PNG instead of showing the window
    """
    try:
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
    except ImportError:
        print("  ⚠  matplotlib not installed. Run: pip install matplotlib")
        return

    model    = get_active_model()
    results  = _load_results()
    matrices = _load_matrices()

    nvm = compute_nvm_data(frame_id, model, results, matrices)
    x   = nvm['stations']
    L   = nvm['L']
    zero = [0.0] * len(x)

    use_rel = deflection == 'relative'
    defl_major = nvm['Defl_2_Rel'] if use_rel else nvm['Defl_2_Abs']
    defl_minor = nvm['Defl_3_Rel'] if use_rel else nvm['Defl_3_Abs']
    defl_label = f"Deflection ({'Rel' if use_rel else 'Abs'}) [m]"

    fig = plt.figure(figsize=(14, 11))
    fig.suptitle(
        f"Frame {frame_id} — NVM Diagrams   (L = {L:.3f} m)",
        fontsize=13, fontweight='bold', y=0.98
    )
    gs = gridspec.GridSpec(4, 2, hspace=0.45, wspace=0.35)

    col_titles = ["Major Axis  (P, V2, M3)", "Minor Axis  (P, V3, M2)"]
    rows = [
                                                            
        (nvm['P'],      nvm['P'],      "P — Axial",   "#2c3e50"),
        (nvm['V2'],     nvm['V3'],     "Shear",        "#e74c3c"),
        (nvm['M3'],     nvm['M2'],     "Moment",       "#2980b9"),
        (defl_major,    defl_minor,    defl_label,     "#27ae60"),
    ]

    def _draw(ax, y_data, ylabel, color, show_xlabel=False, col_title=None):
        ax.plot(x, y_data, color=color, linewidth=1.8)
        ax.fill_between(x, y_data, zero, alpha=0.15, color=color)
        ax.axhline(0, color='black', linewidth=0.6, linestyle='--')
        ax.set_ylabel(ylabel, fontsize=8)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=7)
        if show_xlabel:
            ax.set_xlabel("x (m)", fontsize=8)
        if col_title:
            ax.set_title(col_title, fontsize=9, fontweight='bold', color='#333')

        y_arr = list(y_data)
        ymax, ymin = max(y_arr), min(y_arr)
        imax, imin = y_arr.index(ymax), y_arr.index(ymin)
        if abs(ymax) > 1e-9:
            ax.annotate(f"{ymax:.3f}", xy=(x[imax], ymax), fontsize=6.5, color=color,
                        textcoords="offset points", xytext=(3, 4))
        if abs(ymin) > 1e-9 and imin != imax:
            ax.annotate(f"{ymin:.3f}", xy=(x[imin], ymin), fontsize=6.5, color=color,
                        textcoords="offset points", xytext=(3, -10))

    for row_idx, (major_d, minor_d, ylabel, color) in enumerate(rows):
        is_last = row_idx == 3
        ax_major = fig.add_subplot(gs[row_idx, 0])
        ax_minor = fig.add_subplot(gs[row_idx, 1])

        _draw(ax_major, major_d, ylabel, color,
              show_xlabel=is_last,
              col_title=col_titles[0] if row_idx == 0 else None)
        _draw(ax_minor, minor_d, ylabel, color,
              show_xlabel=is_last,
              col_title=col_titles[1] if row_idx == 0 else None)

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f" -> NVM plot saved to: {save_path}")
    else:
        plt.show()

def show_rsa_summary():
    """Prints the RSA global summary including base shear and base reactions."""
    data = _load_results()
    
    if "rsa_info" not in data:
        print("  ⚠  Active results are not from an RSA case.")
        return

    info = data["rsa_info"]
    print("\n" + _divider(65, "═"))
    print(f"{'RESPONSE SPECTRUM SUMMARY':^65}")
    print(_divider(65, "═"))
    print(f"  Method       : {info.get('type', 'Response Spectrum')}")
    print(f"  Combination  : {info.get('method', 'Unknown')}")
    
    bsc = data.get("base_shear_coeff")
    if bsc is not None:
        print(f"  Base Shear Coeff : {bsc:.5f} W")
        
    br = data.get("base_reaction")
    if br:
        print(_divider(65))
        print(f"  Global Base Reactions (Combined):")
        print(f"   Fx: {_fmt(br.get('Fx', 0))} | Fy: {_fmt(br.get('Fy', 0))} | Fz: {_fmt(br.get('Fz', 0))}")
        print(f"   Mx: {_fmt(br.get('Mx', 0))} | My: {_fmt(br.get('My', 0))} | Mz: {_fmt(br.get('Mz', 0))}")
    print(_divider(65, "═") + "\n")

def show_rsa_detailed():
    """Prints the mode-by-mode detailed RSA table (Acceleration, Velocity, Mass Ratio)."""
    data = _load_results()
    
    rsa_dict = data.get("rsa_detailed")
    if not rsa_dict:
        print("  ⚠  No detailed RSA data found in the current results.")
        return

    for direction, table_rows in rsa_dict.items():
        print("\n" + _divider(100, "═"))
        print(f"{f'RSA DETAILED MODAL RESPONSES (Direction: {direction})':^100}")
        print(_divider(100, "═"))
        print(f"{'Mode':<6} {'Period (s)':>12} {'Damping':>10} {'SaR (g)':>12} {'SaR (m/s²)':>14} {'Sd (m)':>14} {'Mass Ratio':>12}")
        print(_divider(100))

        table_rows = sorted(table_rows, key=lambda x: x["mode"])
        
        for row in table_rows:
            print(f"{row['mode']:<6} "
                  f"{row['T']:>12.4f} "
                  f"{row.get('Damping', 0.05):>10.3f} "
                  f"{row['SaR_g']:>12.5f} "
                  f"{row['SaR_ms2']:>14.5f} "
                  f"{row['Sd']:>14.5e} "
                  f"{row['Ratio']:>12.5f}")

        print(_divider(100, "═") + "\n")
