import sys
import os
import time
import numpy as np
import json
from scipy.sparse import lil_matrix
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
from linear_static.element_forces import ForceExtractor
from linear_static.element_library import get_geometric_stiffness_matrix
from linear_static.error_definitions import SolverException

def _write_error(out_path, error_code, extra=""):
    ex = SolverException(error_code, extra)
    try:
        with open(out_path, 'w') as f:
            json.dump({"status": "FAILED", "error": ex.get_details()}, f, indent=4)
    except:
        pass
    return True

def run_buckling_analysis(input_json_path, output_json_path, results_path, matrices_path, case_name="BUCKLING"):
    print("="*60)
    print(f"OPENCIVIL BUCKLING ENGINE | V0.4")
    print(f"Target: {os.path.basename(input_json_path)}")
    print("="*60)
    
    start_time = time.time()
    
    try:
        print("[1/6] Initializing Data Manager...")
        dm = DataManager(input_json_path)
        
        dm.process_all(case_name=case_name)
    except Exception as e:
        print(f"FATAL: Data Load Error: {e}")
        return _write_error(output_json_path, "E102", str(e))

    try:
        print("[2/6] Re-Assembling Global Elastic Stiffness (K_E)...")
        assembler = GlobalAssembler(dm)
        K_full, _ = assembler.assemble_system()
        
        buckling_case_def = next((c for c in dm.raw.get('load_cases', []) if c['name'] == case_name), None)
        req_modes = buckling_case_def.get("num_modes", 6) if buckling_case_def else 6
        
    except Exception as e:
        print(f"FATAL: K_E Matrix Assembly Error: {e}")
        return _write_error(output_json_path, "E000", f"Matrix Assembly Error: {e}")

    try:
        print("[3/6] Assembling Geometric Stiffness (K_G)...")
        
        extractor = ForceExtractor(input_json_path, results_path, matrices_path)
        KG_full = lil_matrix((dm.total_dofs, dm.total_dofs))
        
        elements_in_compression = 0

        for el in dm.elements:
            eid = str(el['id'])
            L = el['L_clear']
            
            forces = extractor.get_element_forces(el['id'])
            if forces is None:
                continue
            
            print(f"Element {el['id']}: forces[0]={forces[0]:.4f}, forces[6]={forces[6]:.4f}")

            N_axial = (forces[6] - forces[0]) / 2.0
            
            if N_axial < -1e-5:
                elements_in_compression += 1
            
            kg_local = get_geometric_stiffness_matrix(N_axial, L)
            
            mat = extractor.matrices_data[eid]
            t = np.array(mat['t'])
            kg_global = t.T @ kg_local @ t
            
            idx_i, idx_j = el['node_indices']
            start_i = idx_i * 6
            start_j = idx_j * 6
            
            KG_full[start_i:start_i+6, start_i:start_i+6] += kg_global[0:6, 0:6]
            KG_full[start_i:start_i+6, start_j:start_j+6] += kg_global[0:6, 6:12]
            KG_full[start_j:start_j+6, start_i:start_i+6] += kg_global[6:12, 0:6]
            KG_full[start_j:start_j+6, start_j:start_j+6] += kg_global[6:12, 6:12]

        print(f"      Extracted forces from previous static run.")
        print(f"      Elements in compression: {elements_in_compression}/{len(dm.elements)}")
        
    except Exception as e:
        print(f"FATAL: K_G Assembly Error: {e}")
        return _write_error(output_json_path, "E000", f"K_G Assembly Error: {e}")

    print("[4/6] Applying Boundary Conditions...")
    
    is_free = np.ones(dm.total_dofs, dtype=bool)
    for node in dm.nodes:
        start_idx = node['idx'] * 6
        restraints = node['restraints']                           
        for i in range(6):
            if restraints[i]:           
                is_free[start_idx + i] = False
    
    num_free_dofs = np.sum(is_free)
    
    if num_free_dofs == 0:
        return _write_error(output_json_path, "E301", "Structure is fully constrained. No free DOFs.")

    K_free = K_full.tocsc()[is_free, :][:, is_free]
    KG_free = KG_full.tocsc()[is_free, :][:, is_free]

    try:
        print(f"[5/6] Solving Buckling Eigenvalues...")
        
        if num_free_dofs < 100:
                                                                            
            import scipy.linalg as la
            print(f"      Using Dense Solver (Small Model: {num_free_dofs} DOFs)")
            
            K_dense = K_free.toarray()
            KG_dense = KG_free.toarray()
            
            eigenvalues, eigenvectors = la.eig(K_dense, KG_dense)
            
            valid_modes = []
            for i in range(len(eigenvalues)):
                lam = eigenvalues[i].real
                                                                                       
                if np.isfinite(lam) and lam > 1e-6 and abs(eigenvalues[i].imag) < 1e-6:
                    valid_modes.append((lam, eigenvectors[:, i].real))
            
            valid_modes.sort(key=lambda x: x[0])
            valid_modes = valid_modes[:req_modes]
            
        else:
                                                             
            safe_num_modes = min(req_modes, max(1, num_free_dofs - 2))
            if safe_num_modes < req_modes:
                print(f"Warning: Model only has {num_free_dofs} free DOFs. Clamped to {safe_num_modes} modes.")
                req_modes = safe_num_modes

            print(f"      Using Sparse Solver (Shift-Invert ARPACK)")
            eigenvalues, eigenvectors = eigsh(A=K_free, M=KG_free, k=req_modes, sigma=1.0, which='LM')
            
            valid_modes = []
            for i in range(len(eigenvalues)):
                lam = eigenvalues[i]
                if lam > 1e-6:                                                              
                    valid_modes.append((lam, eigenvectors[:, i]))

            valid_modes.sort(key=lambda x: x[0]) 

        print(f"      Converged. Found {len(valid_modes)} buckling modes.")

    except Exception as e:
        err_str = str(e)
        print(f"FATAL: Eigen Solver Error: {err_str}")
        return _write_error(output_json_path, "E303", f"Solver Error: {err_str}")

    print("[6/6] Formatting Results...")
    
    results = {
        "status": "SUCCESS",
        "info": {"type": "Buckling Analysis"},
        "mode_shapes": {},
        "tables": {
            "buckling_factors": []
        }
    }

    for i, (lam, phi_free) in enumerate(valid_modes):
        
        max_val = np.max(np.abs(phi_free))
        if max_val > 0:
            phi_free = phi_free / max_val
            
        results["tables"]["buckling_factors"].append({
            "mode": i + 1,
            "lambda": float(lam)
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
        
        print(f"      Mode {i+1}: Buckling Factor (Lambda) = {lam:.4f}")

    try:
        with open(output_json_path, 'w') as f:
            json.dump(results, f, indent=4)
        print("="*60)
        print(f"Total Time: {time.time() - start_time:.4f}s")
        print("="*60)
        return True
    except Exception as e:
        print(f"FATAL: Write Error: {e}")
        return _write_error(output_json_path, "E401", str(e))

if __name__ == "__main__":
    test_in = os.path.join(current_dir, "test.mf")
    test_out = os.path.join(current_dir, "test_buckling_results.json")
    test_res = os.path.join(current_dir, "results.json")
    test_mat = os.path.join(current_dir, "cli_matrices.json")
    
    if os.path.exists(test_in):
        run_buckling_analysis(test_in, test_out, test_res, test_mat)
