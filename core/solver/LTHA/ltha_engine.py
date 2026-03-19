import os
import sys
import json
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from newmark_sdof import newmark_elastic_sdof

def run_ltha_analysis(modal_results_path, model_data, output_path, case_name="LTHA"):
    """
    Linear Time History Analysis via Modal Superposition.

    Steps:
        1. Load modal results (mode shapes, periods, participation factors).
        2. Read ltha_loads from case — list of (direction, func_name, scale).
           Accelerogram values come from model.th_functions[func_name]["values"].
        3. For each load direction:
              For each mode: scale accel by Gamma_n * scale, run Newmark SDOF -> q_n(t).
              Superpose: U(t) += phi_n * q_n(t)  (accumulates across directions).
        4. Extract peak displacements per node.
        5. Write results JSON — accel_history is now a dict {"X": [...], "Y": [...], ...}

    Args:
        modal_results_path (str):  Path to the modal results JSON.
        model_data         (dict): Model __dict__ from StructuralModel.
        output_path        (str):  Where to write the LTHA results JSON.
        case_name          (str):  Name of the LTHA load case.

    Returns:
        bool: True on success, False on failure.
    """
    print("=" * 60)
    print("METUFIRE LTHA ENGINE | V0.2 (Multi-Direction Modal Superposition)")
    print("=" * 60)

    if not os.path.exists(modal_results_path):
        _write_error(output_path, "Modal results not found. Run MODAL analysis first.")
        return False

    with open(modal_results_path, 'r') as f:
        modal_data = json.load(f)

    if modal_data.get("status") != "SUCCESS":
        _write_error(output_path, "Modal analysis did not succeed.")
        return False

    periods_table = modal_data["tables"]["periods"]                                          
    mass_ratios   = modal_data["tables"]["participation_mass"]                                           
    mode_shapes   = modal_data["mode_shapes"]                                                  

    print(f"[1/4] Loaded {len(periods_table)} modes from modal results.")

    load_cases  = model_data.get("load_cases", {})
    case_obj    = load_cases.get(case_name)
    th_functions = getattr(model_data, "th_functions", None) or model_data.get("th_functions", {})

    zeta = 0.05
    if case_obj is not None:
        zeta = getattr(case_obj, "damping", 0.05)

    ltha_loads_raw = getattr(case_obj, "ltha_loads", []) if case_obj else []

    if not ltha_loads_raw:
        _write_error(output_path, "No ground motion loads defined. Add at least one function in the LTHA case.")
        return False

    resolved_loads = []                                             
    for direction, func_name, scale in ltha_loads_raw:
        func_data = th_functions.get(func_name)
        if not func_data:
            _write_error(output_path, f"Function '{func_name}' not found in model. Define it under Functions > Time History.")
            return False

        values = func_data.get("values", [])
        if not values:
                                                                  
            file_path = func_data.get("file_path", "")
            header_skip = func_data.get("header_skip", 0)
            accel_col   = func_data.get("accel_col", 0)
            if file_path and os.path.exists(file_path):
                values = _read_values_from_file(file_path, header_skip, accel_col)
            if not values:
                _write_error(output_path, f"Function '{func_name}' has no data. Check the file path.")
                return False

        dt = func_data.get("dt", 0.01)
        resolved_loads.append((direction, np.array(values, dtype=float), dt, float(scale)))
        print(f"[2/4] Function '{func_name}' ({direction}): {len(values)} steps, "
              f"dt={dt:.4f}s, duration={len(values)*dt:.1f}s, "
              f"PGA={np.max(np.abs(values)):.4f} m/s², scale={scale}")

    n_steps = max(len(a) for _, a, _, _ in resolved_loads)
                                                                            
    dt_ref = resolved_loads[0][2]
    if len(resolved_loads) > 1:
        for d, _, dt_i, _ in resolved_loads[1:]:
            if abs(dt_i - dt_ref) > 1e-6:
                print(f"   WARNING: Direction {d} has dt={dt_i} vs reference dt={dt_ref}. "
                      f"Animation will use dt={dt_ref}.")

    print(f"   n_steps={n_steps}, dt_ref={dt_ref:.4f}s, zeta={zeta*100:.0f}%")

    directions_str = " + ".join(d for d, _, _, _ in resolved_loads)
    print(f"[3/4] Running modal superposition ({len(periods_table)} modes, "
          f"directions={directions_str}, zeta={zeta*100:.0f}%)...")

    node_ids = list(mode_shapes["Mode 1"].keys())

    U_history = {nid: np.zeros((n_steps, 6)) for nid in node_ids}

    for direction, accel_raw, dt, scale in resolved_loads:
                                         
        if len(accel_raw) < n_steps:
            accel_padded = np.zeros(n_steps)
            accel_padded[:len(accel_raw)] = accel_raw
        else:
            accel_padded = accel_raw[:n_steps]

        accel_scaled = scale * accel_padded

        for i, mode_info in enumerate(periods_table):
            T     = mode_info["T"]
            omega = mode_info["omega"]

            if T < 1e-6 or omega < 1e-6:
                continue                         

            pm = mass_ratios[i]
            if   direction == "X": Gamma = pm.get("Gamma_x", 0.0)
            elif direction == "Y": Gamma = pm.get("Gamma_y", 0.0)
            else:                   Gamma = pm.get("Gamma_z", 0.0)

            accel_eff = Gamma * accel_scaled

            q_n, _, _ = newmark_elastic_sdof(accel_eff, dt, T, zeta, m=1.0)

            if i == 0:               
                print(f"\n--- DEBUG MODE 1 ---")
                print(f"  pm dict = {pm}")
                print(f"  T = {T:.4f} s")
                print(f"  Gamma = {Gamma:.6f}")
                print(f"  max(accel_eff) = {np.max(np.abs(accel_eff)):.6f} m/s2")
                print(f"  max(q_n) = {np.max(np.abs(q_n)):.6f} m")
                print(f"--------------------\n")

            mode_key   = f"Mode {i+1}"
            shape_data = mode_shapes.get(mode_key, {})

            for nid in node_ids:
                if nid not in shape_data:
                    continue
                phi = np.array(shape_data[nid])               
                U_history[nid] += np.outer(q_n, phi)

        print(f"   Direction {direction}: all modes processed ✓")

    print("[4/4] Extracting peak responses and writing results...")

    peak_displacements = {}
    for nid, hist in U_history.items():
        peak = np.max(np.abs(hist), axis=0)
        peak_displacements[nid] = peak.tolist()

    history_path = output_path.replace("_results.json", "_LTHA_history.npz")
    np.savez_compressed(history_path, **{"node_" + str(nid): hist for nid, hist in U_history.items()})
    print(f"   Time history saved: {history_path}")

    base_reaction = {"Fx": 0.0, "Fy": 0.0, "Fz": 0.0,
                     "Mx": 0.0, "My": 0.0, "Mz": 0.0}

    accel_history_dict = {}
    for direction, accel_raw, dt, scale in resolved_loads:
        if len(accel_raw) < n_steps:
            padded = np.zeros(n_steps)
            padded[:len(accel_raw)] = accel_raw
            accel_history_dict[direction] = padded.tolist()
        else:
            accel_history_dict[direction] = accel_raw[:n_steps].tolist()

    output_data = {
        "status": "SUCCESS",
        "info": {
            "type":       "Linear Time History Analysis",
            "case":       case_name,
            "directions": [d for d, _, _, _ in resolved_loads],
            "damping":    zeta,
            "n_modes":    len(periods_table),
            "n_steps":    n_steps,
            "dt":         dt_ref
        },
        "displacements":  peak_displacements,
        "base_reaction":  base_reaction,
        "history_path":   history_path,
        "accel_history":  accel_history_dict                                       
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=4)

    print("LTHA Complete.")
    return True

def _read_values_from_file(file_path, header_skip, accel_col):
    """
    Fallback reader if th_functions cache is empty.
    Mirrors the logic in TimeHistoryFunctionDialog._read_file.
    """
    import csv
    values = []
    try:
        with open(file_path, 'r') as f:
            sample = f.read(2048)
            f.seek(0)
            delimiter = '\t' if '\t' in sample else ','
            reader = csv.reader(f, delimiter=delimiter)
            for row_i, row in enumerate(reader):
                if row_i < header_skip:
                    continue
                if not row or len(row) <= accel_col:
                    continue
                try:
                    values.append(float(row[accel_col]))
                except ValueError:
                    continue
    except Exception:
        pass
    return values

def _load_ground_motion(csv_path, dt):
    """
    Legacy CSV loader — kept intact for any external callers.
    Acceleration is read from the column named 'acceleration_m_s2' (index 2 fallback).
    """
    import csv

    accels = []
    accel_col_idx = None

    with open(csv_path, 'r') as f:
        sample = f.read(1024)
        f.seek(0)
        delimiter = '\t' if '\t' in sample else ','
        reader = csv.reader(f, delimiter=delimiter)

        for row in reader:
            if not row:
                continue

            if accel_col_idx is None:
                for i, cell in enumerate(row):
                    if 'acceleration_m_s2' in cell.lower():
                        accel_col_idx = i
                        break
                if accel_col_idx is None:
                    accel_col_idx = 2
                continue

            if len(row) <= accel_col_idx:
                continue

            try:
                accels.append(float(row[accel_col_idx]))
            except ValueError:
                continue

    if len(accels) < 10:
        raise ValueError(f"Ground motion file has too few data rows: {csv_path}")

    return np.array(accels)

def _write_error(output_path, message):
    with open(output_path, 'w') as f:
        json.dump({"status": "FAILED",
                   "error": {"title": "LTHA Error", "desc": message}}, f, indent=4)
    print(f"LTHA ERROR: {message}")
