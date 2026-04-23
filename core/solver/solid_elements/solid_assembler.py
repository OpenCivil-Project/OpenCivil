"""
SolidAssembler — OpenCivil
===========================
Assembles the global K and P for the Tet4 solid mesh,
then delegates solving to the existing LinearSolver from solver_kernel.py.

No duplicated solve logic — reuses the frame solver kernel directly.

Usage:
    asm = SolidAssembler(dm)
    K, P = asm.assemble_system()
    U, R = asm.solve()
    stress_results = asm.compute_element_stresses(U)
"""

import numpy as np
from scipy.sparse import lil_matrix
import sys, os
import numpy as np
from scipy.sparse import lil_matrix
from scipy.sparse.linalg import spsolve
from error_definitions import SolverException 

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from solid_element_library import get_tet10_stiffness_matrix
                                                                                       
class SolidAssembler:
    def __init__(self, solid_data_manager):
        self.dm = solid_data_manager
        self.K  = lil_matrix((self.dm.total_dofs, self.dm.total_dofs))
        self.P  = np.zeros(self.dm.total_dofs)
        self._solver = None                                                  

    def assemble_system(self):
        """Builds global K and P. Returns (K_csc, P)."""
        print("SolidAssembler: building stiffness matrix "
              f"({len(self.dm.elements)} elements, "
              f"{self.dm.total_dofs} DOFs)...")

        self._build_stiffness()
        self._build_rigid_links()

        print("SolidAssembler: building load vector...")
        self.P += self.dm.build_load_vector()

        K_csc = self.K.tocsc()
        print(f"SolidAssembler: done. Non-zeros: {K_csc.nnz}")
        return K_csc, self.P

    def solve(self):
        """
        Applies BCs and solves.  Supports two submodeling modes:

        Displacement-based (legacy):
            self.dm.prescribed_displacements is set.
            Cut-node rigid-link masters are pinned at the global U values.
            Requires K_fs * U_s correction to the RHS.

        Force-based (new):
            self.dm.cut_node_forces is set.
            Cut-node rigid-link masters stay FREE; their cut forces are
            injected directly into P.  No K_fs correction needed for those DOFs.
            Real supports inside the selection still use disp=0 BCs.
        """
        print("SolidAssembler: Applying Boundary Conditions and Partitioning...")

        is_free = np.ones(self.dm.total_dofs, dtype=bool)
        U_full  = np.zeros(self.dm.total_dofs)

        # ── Detect operating mode ─────────────────────────────────────────────
        is_force_based = hasattr(self.dm, 'cut_node_forces')
        cut_nodes      = getattr(self.dm, 'cut_nodes', set())          # force-BC nodes
        if is_force_based:
            print("  Mode: Force-Based Submodeling")

        # ── 1. Standard solid node restraints (mesh-level pins) ───────────────
        for node in self.dm.nodes:
            start_idx  = node['idx'] * 3
            restraints = node['restraints']
            for i in range(3):
                if restraints[i]:
                    is_free[start_idx + i] = False

        # ── Helper: find raw frame node closest to a set of coords ────────────
        def _find_raw_node(master_coords):
            for raw_n in self.dm.raw['nodes']:
                if (abs(raw_n['x'] - master_coords[0]) < 1e-5 and
                        abs(raw_n['y'] - master_coords[1]) < 1e-5 and
                        abs(raw_n['z'] - master_coords[2]) < 1e-5):
                    return raw_n
            return None

        # ── Helper: prescribed displacement lookup (legacy disp-based mode) ───
        old_id_to_idx = {}
        if hasattr(self.dm, 'prescribed_displacements'):
            user_ids = sorted(n['id'] for n in self.dm.raw['nodes'])
            old_id_to_idx = {uid: i for i, uid in enumerate(user_ids)}

        def _get_prescribed(raw_n):
            if not hasattr(self.dm, 'prescribed_displacements') or raw_n is None:
                return [0.0] * 6
            old_idx = old_id_to_idx.get(raw_n['id'])
            if old_idx is not None and old_idx in self.dm.prescribed_displacements:
                return self.dm.prescribed_displacements[old_idx]
            return [0.0] * 6

        # ── 2. Rigid-link master DOF constraints ──────────────────────────────
        if hasattr(self.dm, 'rigid_links'):
            for rl in self.dm.rigid_links:
                m_start    = rl['master_dof_start']
                restraints = rl['restraints']
                raw_n      = _find_raw_node(rl['master_coords'])
                node_id    = raw_n['id'] if raw_n else None

                # Force-based cut node → leave master DOFs FREE.
                # Forces will be injected into P in step 3 below.
                if is_force_based and node_id in cut_nodes:
                    continue

                # Everything else: displacement BC (either prescribed or zero)
                prescribed_disp = _get_prescribed(raw_n)
                for i in range(6):
                    if restraints[i]:
                        is_free[m_start + i] = False
                        U_full[m_start + i]  = prescribed_disp[i]

        # ── 3. Inject cut forces into P (force-based mode only) ───────────────
        if is_force_based and hasattr(self.dm, 'rigid_links'):
            cut_forces = self.dm.cut_node_forces or {}
            for rl in self.dm.rigid_links:
                raw_n = _find_raw_node(rl['master_coords'])
                if raw_n and raw_n['id'] in cut_forces:
                    F   = cut_forces[raw_n['id']]
                    m   = rl['master_dof_start']
                    self.P[m : m + 6] += F
                    print(f"  [Force BC] Node {raw_n['id']} master DOF {m}: "
                          f"F=[{F[0]:.2f}, {F[1]:.2f}, {F[2]:.2f}] "
                          f"M=[{F[3]:.2f}, {F[4]:.2f}, {F[5]:.2f}]")

        # ── 4. Partition: K_ff * U_f = P_f - K_fs * U_s ──────────────────────
        K_csc   = self.K.tocsc()
        is_supp = ~is_free

        K_ff = K_csc[is_free,  :][:, is_free ]
        K_fs = K_csc[is_free,  :][:, is_supp ]
        P_f  = self.P[is_free]
        U_s  = U_full[is_supp]
        P_eff = P_f - K_fs.dot(U_s)   # zero correction for force-based cut nodes (U_s=0 there)

        if K_ff.shape[0] == 0:
            print("Warning: Structure is fully constrained (0 free DOFs).")
            return U_full, self.P

        print(f"SolidAssembler: Solving system with {K_ff.shape[0]} equations...")
        try:
            U_f = spsolve(K_ff, P_eff)
        except (RuntimeError, ValueError) as e:
            raise Exception(f"Math Error during spsolve: {str(e)}")

        # ── 5. Reconstruct & reactions ────────────────────────────────────────
        U_full[is_free] = U_f

        print("SolidAssembler: Computing Reactions...")
        Reactions = self.K.dot(U_full) - self.P

        return U_full, Reactions
    
    def _build_stiffness(self):
        for el in self.dm.elements:
            mat   = el['material']
                                         
            K_e, _ = get_tet10_stiffness_matrix(mat['E'], mat['nu'], el['coords'])

            dofs = []
            for n_idx in el['node_indices']:                                
                s = n_idx * 3
                dofs += [s, s+1, s+2]
            dofs = np.array(dofs)

            for r in range(30):
                for c in range(30):
                    self.K[dofs[r], dofs[c]] += K_e[r, c]

    def compute_element_stresses(self, U_full):
        results = []
        a = (5.0 + 3.0*np.sqrt(5.0)) / 20.0
        b = (5.0 - np.sqrt(5.0)) / 20.0
                                                           
        gauss_L = [
            (a, b, b), (b, a, b), (b, b, a), (b, b, b)
        ]

        for el in self.dm.elements:
            mat    = el['material']
            C      = _build_C(mat['E'], mat['nu'])
            coords = el['coords']

            dofs = []
            for n_idx in el['node_indices']:
                s = n_idx * 3
                dofs += [s, s+1, s+2]
            u_e = U_full[dofs]

            elem_stresses = []
            elem_vms = []

            for L1, L2, L3 in gauss_L:
                B = _build_B_tet10_node(coords, L1, L2, L3)
                stress = C @ B @ u_e
                
                sxx, syy, szz, sxy, syz, sxz = stress
                vm = np.sqrt(0.5 * ((sxx-syy)**2 + (syy-szz)**2 + (szz-sxx)**2 
                                    + 6*(sxy**2 + syz**2 + sxz**2)))
                
                elem_stresses.append(stress.tolist())
                elem_vms.append(float(vm))

            results.append({
                'id':        el['id'],
                'stress':    elem_stresses,                    
                'von_mises': elem_vms,                         
            })
        return results
    
    def _build_rigid_links(self):
        if not hasattr(self.dm, 'rigid_links') or not self.dm.rigid_links: return
        print(f"SolidAssembler: building {len(self.dm.rigid_links)} rigid links (MPCs)...")
        
        k_p = 1e14                             
        
        for rl in self.dm.rigid_links:
            m_coords = rl['master_coords']
            m_dof = rl['master_dof_start']
            
            for s_idx in rl['slave_indices']:
                s_coords = self.dm.nodes[s_idx]['coords']
                s_dof = s_idx * 3
                
                dx = s_coords[0] - m_coords[0]
                dy = s_coords[1] - m_coords[1]
                dz = s_coords[2] - m_coords[2]
                
                C = np.array([
                    [1, 0, 0,  -1, 0, 0,   0,  dz, -dy],
                    [0, 1, 0,   0,-1, 0, -dz,   0,  dx],
                    [0, 0, 1,   0, 0,-1,  dy, -dx,   0]
                ], dtype=float)
                
                K_pen = k_p * (C.T @ C)
                
                dofs = [s_dof, s_dof+1, s_dof+2, 
                        m_dof, m_dof+1, m_dof+2, m_dof+3, m_dof+4, m_dof+5]
                
                for r in range(9):
                    for c in range(9):
                        self.K[dofs[r], dofs[c]] += K_pen[r, c]

def _build_B_tet10_node(coords, L1, L2, L3):
    """6x30 strain-displacement matrix evaluated at specific natural coords."""
    L4 = 1.0 - L1 - L2 - L3
    dN_dL = np.zeros((3, 10))
    
    dN_dL[0, 0] = 4*L1 - 1; dN_dL[1, 0] = 0;        dN_dL[2, 0] = 0
    dN_dL[0, 1] = 0;        dN_dL[1, 1] = 4*L2 - 1; dN_dL[2, 1] = 0
    dN_dL[0, 2] = 0;        dN_dL[1, 2] = 0;        dN_dL[2, 2] = 4*L3 - 1
    dN_dL[0, 3] = -(4*L4 - 1); dN_dL[1, 3] = -(4*L4 - 1); dN_dL[2, 3] = -(4*L4 - 1)
    
    dN_dL[0, 4] = 4*L2;  dN_dL[1, 4] = 4*L1;  dN_dL[2, 4] = 0
    dN_dL[0, 5] = 0;     dN_dL[1, 5] = 4*L3;  dN_dL[2, 5] = 4*L2
    dN_dL[0, 6] = 4*L3;  dN_dL[1, 6] = 0;     dN_dL[2, 6] = 4*L1
    
    dN_dL[0, 7] = 4*(L4 - L1); dN_dL[1, 7] = -4*L1;       dN_dL[2, 7] = -4*L1
    dN_dL[0, 8] = -4*L2;       dN_dL[1, 8] = 4*(L4 - L2); dN_dL[2, 8] = -4*L2
    dN_dL[0, 9] = -4*L3;       dN_dL[1, 9] = -4*L3;       dN_dL[2, 9] = 4*(L4 - L3)

    J = dN_dL @ coords
    J_inv = np.linalg.inv(J)
    dN_dx = J_inv @ dN_dL
    
    B = np.zeros((6, 30))
    for i in range(10):
        col = i * 3
        B[0, col  ] = dN_dx[0, i]
        B[1, col+1] = dN_dx[1, i]
        B[2, col+2] = dN_dx[2, i]
        
        B[3, col  ] = dN_dx[1, i]; B[3, col+1] = dN_dx[0, i]
        B[4, col+1] = dN_dx[2, i]; B[4, col+2] = dN_dx[1, i]
        B[5, col  ] = dN_dx[2, i]; B[5, col+2] = dN_dx[0, i]
        
    return B

def _build_C(E, nu):
    """6×6 isotropic constitutive matrix."""
    lam = E * nu / ((1 + nu) * (1 - 2*nu))
    mu  = E / (2 * (1 + nu))
    return np.array([
        [lam+2*mu, lam,      lam,      0,  0,  0],
        [lam,      lam+2*mu, lam,      0,  0,  0],
        [lam,      lam,      lam+2*mu, 0,  0,  0],
        [0,        0,        0,        mu, 0,  0],
        [0,        0,        0,        0,  mu, 0],
        [0,        0,        0,        0,  0,  mu],
    ])

if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from solid_data_manager import SolidDataManager
    from solid_mesher import SolidMesher, patch_data_manager

    path = sys.argv[1] if len(sys.argv) > 1 else "test.mf"

    print("=== Step 1: Data Manager ===")
    dm = SolidDataManager(path)
    dm.process_all(case_name="DEAD")
    patch_data_manager(dm)

    print("\n=== Step 2: Mesher ===")
    mesher = SolidMesher(dm, nx=4, ny=2, nz=2)
    mesher.mesh_all()

    print("\n=== Step 3: Assembler ===")
    asm = SolidAssembler(dm)
    K, P = asm.assemble_system()

    print("\n=== Step 4: Solve ===")
    U, R = asm.solve()

    max_u = np.max(np.abs(U))
    print(f"\nMax displacement: {max_u:.4e} m")

    print("\n=== Step 5: Stresses (first 3 elements) ===")
    stress_results = asm.compute_element_stresses(U)
    for s in stress_results[:3]:
        print(f"  elem {s['id']:4d}  vm={s['von_mises']:.4e} Pa  "
              f"sxx={s['stress'][0]:.4e}")

    print("\n✅ Full solid pipeline working.")