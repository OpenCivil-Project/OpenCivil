import sys
import os
import traceback
import json
import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path: sys.path.append(root_dir)
from core.solver.linear_static.main_engine import run_linear_static_analysis
from core.solver.modal.modal_engine import run_modal_analysis
from core.solver.RSA.rsa_engine import RSAEngine
from core.model import StructuralModel 

class SolverWorker(QThread):
    signal_finished = pyqtSignal(bool, str)

    def __init__(self, input_path, output_path, case_type="Linear Static", case_name="DEAD"):
        super().__init__()
        self.input_path = input_path
        self.output_path = output_path
        self.case_type = case_type
        self.case_name = case_name 

    def run(self):
        try:
            print(f"Worker: Starting {self.case_type} Engine on {self.input_path} (Case: {self.case_name})...")
            success = False
            
            if self.case_type == "Modal":
                success = run_modal_analysis(self.input_path, self.output_path)

            elif self.case_type == "Response Spectrum":
                               
                temp_model = StructuralModel("Temp")
                try:
                    temp_model.load_from_file(self.input_path)
                except Exception as e:
                    raise Exception(f"Failed to load model data for RSA: {e}")

                engine = RSAEngine(self.output_path, temp_model.__dict__)
                
                case_obj = temp_model.load_cases.get(self.case_name)
                
                shear_results = [] 
                disp_results = []
                rsa_detailed_tables = {} 
                summary_items = []

                fx_results = []
                fy_results = []
                fz_results = []

                if hasattr(case_obj, 'rsa_loads') and case_obj.rsa_loads:
                    print(f"Worker: Found {len(case_obj.rsa_loads)} load components.")
                    modal_comb = getattr(case_obj, 'modal_comb', 'SRSS')
                    
                    for u_dir, func, scale in case_obj.rsa_loads:
                        direction = "X"
                        if u_dir == "U2": direction = "Y"
                        elif u_dir == "U3": direction = "Z"
                        
                        damp_val = getattr(case_obj, 'modal_damping', 0.05)
                        
                        res_dict = engine.run(
                            function_name=func, 
                            direction=direction, 
                            modal_comb=modal_comb, 
                            damping_ratio=damp_val  
                        )

                        if res_dict:
                                                        
                            shear_results.append(res_dict["base_shear_coeff"])
                            
                            disp_results.append(res_dict["displacements"])
                            
                            if "detailed_table" in res_dict:
                                rsa_detailed_tables[direction] = res_dict["detailed_table"]

                            if "base_reaction" in res_dict:
                                fx_results.append(res_dict["base_reaction"]["Fx"])
                                fy_results.append(res_dict["base_reaction"]["Fy"])
                                fz_results.append(res_dict["base_reaction"]["Fz"])
                            else:
                                fx_results.append(0.0); fy_results.append(0.0); fz_results.append(0.0)

                            summary_items.append({
                                "label": f"Base Shear Coeff ({direction})",
                                "value": res_dict["base_shear_coeff"],
                                "desc": f"V / W_total ({direction})"
                            })

                    method = getattr(case_obj, 'dir_comb', 'SRSS')
                    final_base_shear = 0.0
                    final_displacements = {}
                    
                    final_Fx, final_Fy, final_Fz = 0.0, 0.0, 0.0
                    
                    if shear_results:
                                                 
                        if method == "SRSS":
                            final_base_shear = np.sqrt(sum(v**2 for v in shear_results))
                                                   
                            final_Fx = np.sqrt(sum(v**2 for v in fx_results))
                            final_Fy = np.sqrt(sum(v**2 for v in fy_results))
                            final_Fz = np.sqrt(sum(v**2 for v in fz_results))
                        else:           
                            final_base_shear = sum(abs(v) for v in shear_results)
                                                  
                            final_Fx = sum(abs(v) for v in fx_results)
                            final_Fy = sum(abs(v) for v in fy_results)
                            final_Fz = sum(abs(v) for v in fz_results)
                        
                        if disp_results:
                            ref_disps = disp_results[0]
                            for nid in ref_disps.keys():
                                combined_dofs = np.zeros(6)
                                for run_idx, d_dict in enumerate(disp_results):
                                    if nid in d_dict:
                                        vals = np.array(d_dict[nid])
                                        if method == "SRSS":
                                            combined_dofs += vals**2
                                        else:
                                            combined_dofs += np.abs(vals)
                                            
                                if method == "SRSS":
                                    combined_dofs = np.sqrt(combined_dofs)
                                    
                                final_displacements[nid] = combined_dofs.tolist()

                        try:
                            with open(self.output_path, 'r') as f:
                                full_data = json.load(f)
                        except:
                            full_data = {}

                        full_data["status"] = "SUCCESS"
                        full_data["rsa_info"] = {"type": "Response Spectrum Combined", "method": method}
                        full_data["base_shear_coeff"] = final_base_shear
                        full_data["displacements"] = final_displacements
                        
                        full_data["base_reaction"] = {
                            "Fx": final_Fx,
                            "Fy": final_Fy,
                            "Fz": final_Fz,
                            "Mx": 0.0, "My": 0.0, "Mz": 0.0                                                       
                        }
                        
                        full_data["rsa_detailed"] = rsa_detailed_tables
                        full_data["rsa_summary"] = summary_items
                        
                        with open(self.output_path, 'w') as f:
                            json.dump(full_data, f, indent=4)
                            
                        success = True
                    else:
                        success = False
                else:
                    print("Error: No RSA loads defined.")
                    success = False

            else:
                success = run_linear_static_analysis(self.input_path, self.output_path, self.case_name)
            
            if success:
                self.signal_finished.emit(True, "Analysis Completed Successfully.")
            else:
                self.signal_finished.emit(False, "Solver Engine returned failure status.")
                
        except Exception as e:
            err_msg = "".join(traceback.format_exception(None, e, e.__traceback__))
            print(f"Worker Error:\n{err_msg}")
            self.signal_finished.emit(False, f"Solver Crashed:\n{str(e)}")
