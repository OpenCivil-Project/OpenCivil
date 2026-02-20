import sys
import os
import time
import numpy as np
import json
from scipy.sparse.linalg import eigsh

current_dir = os.path.dirname(os.path.abspath(__file__))                        
solver_dir = os.path.dirname(current_dir)                                 
linear_static_dir = os.path.join(solver_dir, 'linear_static')

if current_dir not in sys.path:
    sys.path.append(current_dir)

if solver_dir not in sys.path:
    sys.path.append(solver_dir)
if linear_static_dir not in sys.path:
    sys.path.append(linear_static_dir)

from linear_static.data_manager import DataManager
from linear_static.assembler import GlobalAssembler
from linear_static.error_definitions import SolverException
from mass_assembler import GlobalMassAssembler


def _write_error(out_path, error_code, extra=""):
    """Writes the error to JSON and returns True so the UI loads the error dialog."""
    ex = SolverException(error_code, extra)
    try:
        with open(out_path, 'w') as f:
            json.dump({"status": "FAILED", "error": ex.get_details()}, f, indent=4)
    except:
        pass
    return True


def run_modal_analysis(input_json_path, output_json_path):
    print("="*60)
    print(f"METUFIRE MODAL ENGINE | V0.3 (Shift-Invert)")
    print(f"Target: {os.path.basename(input_json_path)}")
    print("="*60)
    
    start_time = time.time()
    
    try:
        print("[1/6] Initializing Data Manager...")
        dm = DataManager(input_json_path)
        target_case = "MODAL"
        dm.process_all(case_name=target_case)
    except Exception as e:
        print(f"FATAL: Data Load Error: {e}")
        return _write_error(output_json_path, "E102", str(e))

    try:
        print("[2/6] Assembling System Matrices (K & M)...")
        
        assembler = GlobalAssembler(dm)
                                                                                                 
        res = assembler.assemble_system()
        K_full = res[0]                    
        
        modal_case_def = next((c for c in dm.raw['load_cases'] if c['name'] == "MODAL"), None)
        ms_name = modal_case_def.get("mass_source", "Default") if modal_case_def else "Default"
        
        mass_assembler = GlobalMassAssembler(dm)
        M_full = mass_assembler.build_mass_matrix(ms_name)

        if M_full.nnz == 0 or M_full.diagonal().sum() < 1e-9:
            return _write_error(output_json_path, "E105", f"Mass Source '{ms_name}' resulted in zero mass.")

        results = {
            "status": "SUCCESS",
            "info": {"type": "Modal Analysis"},
            "mode_shapes": {},
            "tables": { ... }
        }
        
    except Exception as e:
        print(f"FATAL: Matrix Assembly Error: {e}")
        return _write_error(output_json_path, "E000", f"Matrix Assembly Error: {e}")

    print("[3/6] Applying Boundary Conditions...")
    
    is_free = np.ones(dm.total_dofs, dtype=bool)
    for node in dm.nodes:
        start_idx = node['idx'] * 6
        restraints = node['restraints']                           
        for i in range(6):
            if restraints[i]:           
                is_free[start_idx + i] = False
    
    free_dof_indices = np.where(is_free)[0]
    num_free_dofs = len(free_dof_indices)
    
    print(f"      Total DOFs: {dm.total_dofs}")
    print(f"      Free  DOFs: {num_free_dofs}")
    
    if num_free_dofs == 0:
        print("Error: Structure is fully constrained.")
        return _write_error(output_json_path, "E301", "Structure is fully constrained. No free DOFs.")

    K_free = K_full.tocsc()[is_free, :][:, is_free]
    M_free = M_full.tocsc()[is_free, :][:, is_free]

    print(f"DEBUG: M_free sum = {M_free.sum():.6f}")
    print(f"DEBUG: M_free diagonal sum = {M_free.diagonal().sum():.6f}")

    try:
        req_modes = modal_case_def.get("num_modes", 12) if modal_case_def else 12
        
        safe_limit = max(1, num_free_dofs - 2) if num_free_dofs < 20 else num_free_dofs - 2
        
        if req_modes > safe_limit:
            print(f"      Warning: Requested {req_modes} modes, but system limited to {num_free_dofs} DOFs.")
            print(f"      Reducing request to {safe_limit} modes.")
            req_modes = safe_limit

        if req_modes < 1:
            print("Error: Cannot solve for 0 modes.")
            return _write_error(output_json_path, "E303", "Cannot solve for 0 modes. Free DOFs too low.")

        print(f"[4/6] Solving Eigenvalues (Shift-Invert @ -0.1)...")
        
        sigma_shift = -0.1
        
        vals, vecs = eigsh(K_free, M=M_free, k=req_modes, sigma=sigma_shift)
        
        print(f"      Converged. Found {len(vals)} modes.")

    except Exception as e:
        print(f"FATAL: Eigen Solver Error: {e}")
        if "ARPACK" in str(e):
             print("      (Hint: The model might be extremely unstable or disconnected.)")
        return _write_error(output_json_path, "E303", str(e))

    print("[5/6] Calculating Modal Participation...")
    
    results = {
        "status": "SUCCESS",
        "info": {"type": "Modal Analysis"},
        "mode_shapes": {},
        "tables": {
            "periods": [],
            "participation_mass": []
        }
    }

    print("      Extracting Assembled Joint Masses...")
    assembled_mass = {}
    M_diag = M_full.diagonal()                                        
    
    for node in dm.nodes:
        nid = str(node['id'])
        idx = node['idx'] * 6
        m_vals = M_diag[idx : idx+6].tolist()
        assembled_mass[nid] = m_vals
        
    results["assembled_mass"] = assembled_mass

    diag_M = M_full.diagonal()
    
    mask_x = np.zeros(dm.total_dofs, dtype=bool); mask_x[0::6] = True
    mask_y = np.zeros(dm.total_dofs, dtype=bool); mask_y[1::6] = True
    mask_z = np.zeros(dm.total_dofs, dtype=bool); mask_z[2::6] = True
    
    total_mass_x = np.sum(diag_M[mask_x & is_free])
    total_mass_y = np.sum(diag_M[mask_y & is_free])
    total_mass_z = np.sum(diag_M[mask_z & is_free])                                      

    print(f"DEBUG: total_mass_x = {total_mass_x:.6f} kg")
    print(f"DEBUG: total_mass_x in kN-s²/m = {total_mass_x / 1000:.6f}")
    print(f"DEBUG: Sum of all assembled masses X = {sum(assembled_mass[nid][0] for nid in assembled_mass):.6f}")

    results["total_mass"] = {
        "x": float(total_mass_x),
        "y": float(total_mass_y),
        "z": float(total_mass_z)
    }
    
    sum_ratio_x = 0.0
    sum_ratio_y = 0.0
    sum_ratio_z = 0.0                                 

    r_x = np.zeros(dm.total_dofs); r_x[0::6] = 1.0
    r_y = np.zeros(dm.total_dofs); r_y[1::6] = 1.0
    r_z = np.zeros(dm.total_dofs); r_z[2::6] = 1.0                               
    
    r_x_free = r_x[is_free]
    r_y_free = r_y[is_free]
    r_z_free = r_z[is_free]                                

    for i in range(len(vals)):
        w2 = vals[i]
        phi_free = vecs[:, i]              

        phi_raw = vecs[:, i] 

        Mn_raw = (phi_raw.T @ M_free @ phi_raw)
        
        if Mn_raw > 0:
            scale_factor = 1.0 / np.sqrt(Mn_raw)
        else:
            scale_factor = 1.0
            
        phi_free = phi_raw * scale_factor
        
        Mn = (phi_free.T @ M_free @ phi_free)
        
        if w2 < 1e-6:
             omega = 0.0
             freq = 0.0
             period = 999.99           
                                                              
        else:
             omega = np.sqrt(w2)
             freq = omega / (2 * np.pi)
             period = 1.0 / freq
        
        results["tables"]["periods"].append({
            "mode": i + 1,
            "T": float(period),
            "f": float(freq),
            "omega": float(omega),
            "eigen": float(w2)
        })

        Mn = (phi_free.T @ M_free @ phi_free)
        
        if Mn == 0: Mn = 1.0                                

        L_x = phi_free.T @ M_free @ r_x_free
        L_y = phi_free.T @ M_free @ r_y_free
        L_z = phi_free.T @ M_free @ r_z_free                                         

        if i == 3 or i == 6:                             
            print(f"  DEBUG Mode {i+1}: L_x={L_x:.6f}, Mn={Mn:.6f}, Gamma={L_x/np.sqrt(total_mass_x * Mn):.6f}")

        if i == 3:          
            print(f"    phi_free shape: {phi_free.shape}")
            print(f"    M_free shape: {M_free.shape}")
            print(f"    r_x_free shape: {r_x_free.shape}")
            print(f"    Sum of r_x_free: {np.sum(r_x_free)}")
            print(f"    M @ r_x sum: {np.sum(M_free @ r_x_free)}")

        em_x = (L_x**2) / Mn 
        em_y = (L_y**2) / Mn 
        em_z = (L_z**2) / Mn                                          
        
        ratio_x = em_x / total_mass_x if total_mass_x > 0 else 0
        ratio_y = em_y / total_mass_y if total_mass_y > 0 else 0
        ratio_z = em_z / total_mass_z if total_mass_z > 0 else 0                                 
        
        sum_ratio_x += ratio_x
        sum_ratio_y += ratio_y
        sum_ratio_z += ratio_z                            
        
        gamma_x = float(L_x / np.sqrt(total_mass_x * Mn))
        gamma_y = float(L_y / np.sqrt(total_mass_y * Mn))
        gamma_z = float(L_z / np.sqrt(total_mass_z * Mn))                                 

        results["tables"]["participation_mass"].append({
            "mode": i + 1,
            "Ux": float(ratio_x), "SumUx": float(sum_ratio_x),
            "Uy": float(ratio_y), "SumUy": float(sum_ratio_y),
            "Uz": float(ratio_z), "SumUz": float(sum_ratio_z),                           
            "Gamma_x": gamma_x, "Gamma_y": gamma_y, "Gamma_z": gamma_z                            
        })
        
        phi_full = np.zeros(dm.total_dofs)
        phi_full[is_free] = phi_free
        
        shape_data = {}
        for node in dm.nodes:
            nid = str(node['id'])
            idx = node['idx'] * 6
            node_dofs = phi_full[idx : idx+6].tolist()
            shape_data[nid] = node_dofs
            
        results["mode_shapes"][f"Mode {i+1}"] = shape_data

    try:
        print("[6/6] Writing Results...")
        with open(output_json_path, 'w') as f:
            json.dump(results, f, indent=4)
        print("Done.")
        return True
    except Exception as e:
        print(f"FATAL: Write Error: {e}")
        return _write_error(output_json_path, "E401", str(e))

if __name__ == "__main__":
    test_in = os.path.join(current_dir, "test3.mf")
    test_out = os.path.join(current_dir, "test3_results.json")
    if os.path.exists(test_in):
        run_modal_analysis(test_in, test_out)
