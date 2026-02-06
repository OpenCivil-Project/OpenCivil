import sys
import os
import json
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__)) 
solver_dir = os.path.dirname(os.path.dirname(current_dir)) 

if current_dir not in sys.path: sys.path.append(current_dir)
if solver_dir not in sys.path: sys.path.append(solver_dir)

from tsc2018_generator import TSC2018SpectrumGenerator

class RSAEngine:
    def __init__(self, modal_results_path, model_data):
        self.modal_path = modal_results_path
        self.model_data = model_data
        self.generator = TSC2018SpectrumGenerator()
        
    @staticmethod
    def _cqc_rho(omega_i, omega_j, zeta):
        """
        CQC cross-correlation coefficient.
        """
        if omega_i == 0 or omega_j == 0:
            return 1.0 if (omega_i == omega_j) else 0.0
        r = omega_i / omega_j
        num = 8.0 * zeta**2 * (1.0 + r) * r**1.5
        den = (1.0 - r**2)**2 + 4.0 * zeta**2 * r * (1.0 + r)**2
        return num / den if den != 0.0 else 1.0
    
    def run(self, function_name="FUNC1", direction="X", modal_comb="SRSS", damping_ratio=None):
        print(f"--- RSA ENGINE STARTED ({direction}-Direction, Modal Comb: {modal_comb}) ---")
        
        if not os.path.exists(self.modal_path):
            raise Exception("Modal Results not found.\n\n>> Please set 'MODAL' to 'Run' in the Analysis Dialog first!")
            
        with open(self.modal_path, 'r') as f:
            modal_data = json.load(f)
            
        if "tables" not in modal_data or "periods" not in modal_data["tables"]:
            raise Exception("Modal Data is missing from the result file...")

        periods = modal_data["tables"]["periods"]
        mass_ratios = modal_data["tables"]["participation_mass"]
        mode_shapes = modal_data.get("mode_shapes", {}) 
        
        funcs = self.model_data.get("functions", {})
        if function_name not in funcs:
            print(f"Error: Function '{function_name}' not defined.")
            return None
        func_params = funcs[function_name]
        print(f"Using Function: {function_name} (R={func_params['R']}, I={func_params['I']})")

        spectrum_direction = func_params.get("Direction", "Horizontal")
        interp_method = func_params.get("Interpolation", "Linear") 
        
        if damping_ratio is not None:
            zeta = float(damping_ratio)
            print(f"      -> Using Load Case Damping: {zeta*100}%")
        else:
            zeta = func_params.get("Damping", 0.05)
            print(f"      -> Using Function Default Damping: {zeta*100}%")

        per_mode_shear = []          
        per_mode_omega = []          
        per_mode_u     = {}          

        if mode_shapes:
            first_mode = list(mode_shapes.values())[0]
            for nid in first_mode.keys():
                per_mode_u[nid] = []


        if zeta == 0.05:
            eta = 1.0
        else:

            source_damp_percent = 5.0
            target_damp_percent = zeta * 100.0
            
            denom = 2.31 - 0.41 * np.log(source_damp_percent)
            
            num = 2.31 - 0.41 * np.log(target_damp_percent)
            
            eta = num / denom
            print(f"      -> Applied Damping Correction (Newmark & Hall): {eta:.5f}")

        print("\nMode | Period (s) |  SaR (g)  | Mass Ratio | Base Shear Coeff")
        print("-" * 65)

        g = 9.81
        
        spec_T, spec_Sa, params = self.generator.generate_spectrum_curve(
            ss=func_params['Ss'], s1=func_params['S1'], site_class=func_params['SiteClass'], 
            R=func_params['R'], D=func_params['D'], I=func_params['I'], 
            tl=func_params['TL'], direction=spectrum_direction, t_max=10.0                   
        )

        detailed_table = []

        for i, mode_info in enumerate(periods):
            T = mode_info["T"]
            omega = mode_info["omega"]
            
            sar_g_raw = np.interp(T, spec_T, spec_Sa)
            sar_g = sar_g_raw * eta  

            if direction == "X": 
                ratio = mass_ratios[i]["Ux"]
                gamma = mass_ratios[i].get("Gamma_x", 0.0)
            elif direction == "Y": 
                ratio = mass_ratios[i]["Uy"]
                gamma = mass_ratios[i].get("Gamma_y", 0.0)
            else:
                ratio = mass_ratios[i]["Uz"]
                gamma = mass_ratios[i].get("Gamma_z", 0.0)

            if omega > 0:
                accel_ms2 = sar_g * g
                sd = accel_ms2 / (omega**2)
            else:
                accel_ms2 = 0.0
                sd = 0.0

            base_shear_coeff = sar_g * ratio
            
            per_mode_shear.append(base_shear_coeff)
            per_mode_omega.append(omega)

            print(f"{i+1:4} | {T:10.4f} | {sar_g:9.4f} | {ratio:10.4f} | {base_shear_coeff:10.5f}")

            detailed_table.append({
                "mode": i + 1,
                "T": T,
                "Damping": zeta,
                "SaR_g": sar_g,                          
                "SaR_ms2": accel_ms2,                        
                "Sd": sd,                                         
                "Ratio": ratio,
                "V_coeff": base_shear_coeff
            })

            if omega > 0 and mode_shapes:
                scale_factor = gamma * sd
                
                mode_key = f"Mode {i+1}"
                if mode_key in mode_shapes:
                    shape_data = mode_shapes[mode_key]
                    for nid, dofs in shape_data.items():
                        if nid in per_mode_u:
                            per_mode_u[nid].append(np.array(dofs) * scale_factor)
                else:
                    for nid in per_mode_u:
                        per_mode_u[nid].append(np.zeros(6))
            else:
                for nid in per_mode_u:
                    per_mode_u[nid].append(np.zeros(6))

        n_modes = len(per_mode_shear)
        
        if modal_comb == "CQC" and n_modes > 0:
            shear_total = 0.0
            for i in range(n_modes):
                for j in range(n_modes):
                    rho = self._cqc_rho(per_mode_omega[i], per_mode_omega[j], zeta)
                    shear_total += per_mode_shear[i] * rho * per_mode_shear[j]
            final_base_shear = np.sqrt(abs(shear_total))

            final_displacements = {}
            for nid, vecs in per_mode_u.items():
                if len(vecs) != n_modes: continue
                dof_total = np.zeros(6)
                for i in range(n_modes):
                    for j in range(n_modes):
                        rho = self._cqc_rho(per_mode_omega[i], per_mode_omega[j], zeta)
                        dof_total += vecs[i] * vecs[j] * rho
                final_displacements[nid] = np.sqrt(np.abs(dof_total)).tolist()

        else:
            final_base_shear = np.sqrt(sum(v**2 for v in per_mode_shear))
            final_displacements = {}
            for nid, vecs in per_mode_u.items():
                sq_sum = np.zeros(6)
                for v in vecs:
                    sq_sum += v**2
                final_displacements[nid] = np.sqrt(sq_sum).tolist()

        total_mass = 0.0
        if "total_mass" in modal_data:
            if direction == "X": total_mass = modal_data["total_mass"]["x"]
            elif direction == "Y": total_mass = modal_data["total_mass"]["y"]
            elif direction == "Z": total_mass = modal_data["total_mass"]["z"]
            
        total_weight = total_mass * g
        base_shear_force = final_base_shear * total_weight

        return {
            "status": "SUCCESS",
            "base_shear_coeff": final_base_shear, 
            "base_reaction": {
                "Fx": base_shear_force if direction == "X" else 0.0,
                "Fy": base_shear_force if direction == "Y" else 0.0,
                "Fz": base_shear_force if direction == "Z" else 0.0,
                "Mx": 0.0, "My": 0.0, "Mz": 0.0
            },
            "displacements": final_displacements,
            "detailed_table": detailed_table,
            "spectrum_direction": spectrum_direction,
            "analysis_direction": direction                            
        }
