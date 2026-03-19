import sys
import os
import time
import numpy as np

current_dir = os.path.dirname(os.path.abspath(__file__))
solver_dir  = os.path.dirname(current_dir)                          

if current_dir not in sys.path:
    sys.path.append(current_dir)
if solver_dir not in sys.path:
    sys.path.append(solver_dir)                                     

from error_definitions import SolverException
from solid_data_manager import SolidDataManager
from solid_mesher import SolidMesher, patch_data_manager
from solid_assembler import SolidAssembler

def run_mesh_only(mf_path, case_name="DEAD", mesh_size=0.15):
    """
    Runs only steps 1 and 2 of the pipeline (Data Manager + Mesher).
    No assembly, no solving — just produces a meshed dm for preview.

    Args:
        mf_path   : path to .mf model file
        case_name : load case name (needed by DataManager)
        mesh_size : target edge length for Gmsh tet mesh (metres)

    Returns:
        (success, dm)
        success : bool
        dm      : SolidDataManager with .nodes and .elements populated, or None on failure
    """
    print("=" * 60)
    print("OPENCIVIL — SOLID MESH PREVIEW")
    print(f"Target : {os.path.basename(mf_path)}")
    print(f"Case   : {case_name}   Mesh size: {mesh_size}m")
    print("=" * 60)

    print("[1/2] Initializing Data Manager...")
    try:
        dm = SolidDataManager(mf_path)
        dm.process_all(case_name=case_name)
        patch_data_manager(dm)
        print(f"      {len(dm.raw['nodes'])} frame nodes, "
              f"{len(dm.raw.get('elements', []))} frame elements.")
    except (FileNotFoundError, ValueError) as e:
        _fail(str(e))
        return False, None
    except Exception as e:
        _fail(f"Data Manager error: {e}")
        return False, None

    print("[2/2] Meshing frame elements → Tet10 solid...")
    try:
        mesher = SolidMesher(dm, mesh_size=mesh_size)
        mesher.mesh_all()
        print(f"      {len(dm.nodes)} solid nodes, "
              f"{len(dm.elements)} Tet10 elements, "
              f"{dm.total_dofs} DOFs.")
    except Exception as e:
        _fail(f"Mesher error: {e}")
        return False, None

    print("=" * 60)
    print("MESH PREVIEW READY")
    print("=" * 60)

    return True, dm

def run_solid_analysis(mf_path, case_name="DEAD",
                       mesh_size=0.15,
                       existing_dm=None,
                       launch_viewer=False):
    """
    Full solid FEM pipeline.

    Args:
        mf_path       : path to .mf model file
        case_name     : load case name to run (default "DEAD")
        mesh_size     : target edge length for the Gmsh tet mesh (metres)
        existing_dm   : if provided (already meshed SolidDataManager),
                        steps 1+2 are skipped entirely — no re-meshing.
                        Pass the dm returned by run_mesh_only().
        launch_viewer : if True, opens SolidResultsViewer window after solve

    Returns:
        (success, dm, stress_results)
        success        : bool
        dm             : SolidDataManager (has .nodes, .elements)
        stress_results : list of dicts {id, stress, von_mises}  or [] on failure
    """

    print("=" * 60)
    print("OPENCIVIL — SOLID FEM ENGINE")
    print(f"Target : {os.path.basename(mf_path)}")
    print(f"Case   : {case_name}   Mesh size: {mesh_size}m")
    if existing_dm is not None:
        print("  (Reusing existing mesh — skipping steps 1 & 2)")
    print("=" * 60)

    start = time.time()

    if existing_dm is not None:
        dm = existing_dm
        print("[1/5] Data Manager  — skipped (reusing existing mesh)")
        print("[2/5] Mesher        — skipped (reusing existing mesh)")
    else:
        print("[1/5] Initializing Data Manager...")
        try:
            dm = SolidDataManager(mf_path)
            dm.process_all(case_name=case_name)
            patch_data_manager(dm)
            print(f"      {len(dm.raw['nodes'])} frame nodes, "
                  f"{len(dm.raw.get('elements', []))} frame elements.")
        except (FileNotFoundError, ValueError) as e:
            _fail(str(e))
            return False, None, []
        except Exception as e:
            _fail(f"Data Manager error: {e}")
            return False, None, []

        print("[2/5] Meshing frame elements → Tet10 solid...")
        try:
            mesher = SolidMesher(dm, mesh_size=mesh_size)
            mesher.mesh_all()
            print(f"      {len(dm.nodes)} solid nodes, "
                  f"{len(dm.elements)} Tet10 elements, "
                  f"{dm.total_dofs} DOFs.")
        except Exception as e:
            _fail(f"Mesher error: {e}")
            return False, None, []

    print("[3/5] Assembling global stiffness matrix...")
    try:
        asm  = SolidAssembler(dm)
        K, P = asm.assemble_system()

        sparsity = 1.0 - K.nnz / (dm.total_dofs ** 2)
        print(f"      Non-zeros: {K.nnz}  |  Sparsity: {sparsity*100:.1f}%")
    except Exception as e:
        import traceback
        traceback.print_exc()
        _fail(f"Assembler error: {e}")
        return False, None, []

    print("[4/5] Solving...")
    try:
        U, R = asm.solve()

        max_u = float(np.max(np.abs(U)))
        print(f"      Solution converged. Max displacement: {max_u:.4e} m")

        if max_u > 1e6:
            print("  ⚠️  Warning: huge displacements detected — check units or BCs.")

    except SolverException as se:
        _fail(se.get_message())
        return False, None, []
    except Exception as e:
        _fail(f"Solver error: {e}")
        return False, None, []

    print("[5/5] Computing element stresses...")
    try:
        stress_results = asm.compute_element_stresses(U)

        vm_vals = [val for s in stress_results for val in s['von_mises']]
        print(f"      Von Mises — min: {min(vm_vals):.4e} Pa  "
              f"max: {max(vm_vals):.4e} Pa")
    except Exception as e:
        _fail(f"Stress recovery error: {e}")
        return False, dm, []

    elapsed = time.time() - start
    print("=" * 60)
    print(f"SOLID ANALYSIS COMPLETE — {elapsed:.2f}s")
    print("=" * 60)

    if launch_viewer:
        _launch_viewer(dm, stress_results, U)

    return True, dm, stress_results, U

def _launch_viewer(dm, stress_results, U_full):
    """Launches SolidResultsViewer in a PyQt6 window."""
    try:
        from PyQt6.QtWidgets import QApplication
        from solid_results_viewer import SolidResultsViewer

        app = QApplication.instance() or QApplication(sys.argv)
        viewer = SolidResultsViewer(dm, stress_results, U_full=U_full)
        viewer.show()

        if not QApplication.instance():
            sys.exit(app.exec())
        else:
            app.exec()

    except ImportError as e:
        print(f"  Viewer unavailable (missing dependency): {e}")
    except Exception as e:
        print(f"  Viewer error: {e}")

def _fail(msg):
    print("\n" + "!" * 60)
    print(f"SOLID ANALYSIS FAILED: {msg}")
    print("!" * 60 + "\n")

if __name__ == "__main__":
    mf = sys.argv[1] if len(sys.argv) > 1 else "test.mf"

    success, dm, results = run_solid_analysis(
        mf_path       = mf,
        case_name     = "DEAD",
        mesh_size     = 0.15,
        launch_viewer = True
    )

    if not success:
        sys.exit(1)
