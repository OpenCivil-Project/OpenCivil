"""
SolidDataManager  — reads OpenCivil .mf files
===============================================
Replaces the old solid_data_manager.py that expected a custom JSON.
Now reads the same .mf format the rest of OpenCivil uses.

Provides the same interface the SolidAssembler expects:
    dm.nodes        — list of node dicts
    dm.elements     — list of element dicts (populated by SolidMesher later)
    dm.total_dofs   — int  (n_nodes * 3)
    dm.build_load_vector() → np.ndarray (total_dofs,)
"""

import json
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from linear_static.element_library import get_rotation_matrix 

class SolidDataManager:
    def __init__(self, mf_path):
        try:
            with open(mf_path, 'r') as f:
                self.raw = json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"SolidDataManager: File not found: {mf_path}")
        except json.JSONDecodeError:
            raise ValueError(f"SolidDataManager: Invalid JSON: {mf_path}")

        self.node_id_to_idx = {}
        self.materials       = {}                        

        self.nodes       = []
        self.rigid_links = []                                                             
        self.elements    = []                                       
        self.total_dofs  = 0
        self.mesh_size   = 0.15                           

        self._load_case  = None                                          

    def process_all(self, case_name="DEAD"):
        """Parse materials, nodes, and load case. Call before assembling."""
        self._parse_materials()
        self._map_nodes()
        self._prepare_load_case(case_name)
        self._generate_self_weight()                                        

        print(f"SolidDataManager: {len(self.nodes)} nodes → {self.total_dofs} DOFs")
        print(f"SolidDataManager: materials = {list(self.materials.keys())}")
        print(f"SolidDataManager: load case = '{self._load_case['name']}' "
              f"patterns = {self._load_case['patterns']}")

    def build_load_vector(self):
        P = np.zeros(self.total_dofs)
        active = self._load_case['patterns']

        for load in self.raw.get('loads', []):
            if load.get('type') != 'nodal':
                continue
            pat = load.get('pattern', '')
            if pat not in active:
                continue

            scale    = active[pat]
            node_idx = self.node_id_to_idx.get(load['node_id'])
            if node_idx is None:
                print(f"  Warning: load references unknown node id {load['node_id']}, skipped.")
                continue

            start = node_idx * 3
            P[start    ] += load.get('fx', 0.0) * scale
            P[start + 1] += load.get('fy', 0.0) * scale
            P[start + 2] += load.get('fz', 0.0) * scale

        self._add_member_dist_loads(P, active)

        return P

    def _add_member_dist_loads(self, P, active_patterns):
        """
        Converts member_dist loads into equivalent nodal forces on the solid mesh.

        Strategy — surface traction:
        For each distributed load, find all solid nodes that lie on the
        loaded face of the member (the face perpendicular to the load direction
        in local coordinates). Apply equivalent nodal forces weighted by
        tributary area so the total resultant equals w * L.

        Works for inclined members — R_3x3 handles the rotation naturally.
        Works for wx, wy, wz simultaneously.
        """
        raw_elements  = self.raw.get('elements', [])
        raw_sections  = {s['name']: s for s in self.raw.get('sections', [])}
        raw_nodes_map = {n['id']: n for n in self.raw['nodes']}

        for load in self.raw.get('loads', []):
            if load.get('type') != 'member_dist':
                continue
            pat = load.get('pattern', '')
            if pat not in active_patterns:
                continue

            scale = active_patterns[pat]

            el_raw = next((e for e in raw_elements
                        if e['id'] == load['element_id']), None)
            if el_raw is None:
                print(f"  Warning: member_dist references unknown element "
                    f"{load['element_id']}, skipped.")
                continue

            n1d = raw_nodes_map.get(el_raw['n1_id'])
            n2d = raw_nodes_map.get(el_raw['n2_id'])
            if n1d is None or n2d is None:
                continue

            p1 = np.array([n1d['x'], n1d['y'], n1d['z']], dtype=float)
            p2 = np.array([n2d['x'], n2d['y'], n2d['z']], dtype=float)
            L  = np.linalg.norm(p2 - p1)
            if L < 1e-9:
                continue

            sec  = raw_sections.get(el_raw.get('sec_name', ''), {})
            sec_b, sec_h = self._get_section_bbox(sec)
            half_b = sec_b / 2.0 + 1e-3
            half_h = sec_h / 2.0 + 1e-3

            beta = el_raw.get('beta', 0.0)
            R    = get_rotation_matrix(p1, p2, beta)                            

            vx = R[0]                             
            vy = R[1]            
            vz = R[2]            

            w_defined = np.array([load.get('wx', 0.0),
                                load.get('wy', 0.0),
                                load.get('wz', 0.0)], dtype=float) * scale

            if load.get('coord', 'Global') == 'Global':
                w_local = R @ w_defined                       
            else:
                w_local = w_defined                         

            wx_l, wy_l, wz_l = w_local                                        

            member_nodes = []                                       

            for n in self.nodes:
                delta   = n['coords'] - p1
                x_along = float(np.dot(delta, vx))
                y_loc   = float(np.dot(delta, vy))
                z_loc   = float(np.dot(delta, vz))

                if (-1e-3 <= x_along <= L + 1e-3 and
                        abs(y_loc) <= half_b and
                        abs(z_loc) <= half_h):
                    member_nodes.append((n, x_along, y_loc, z_loc))

            if not member_nodes:
                print(f"  Warning: member_dist on element {load['element_id']} "
                    f"— no solid nodes found inside member volume, skipped.")
                continue

            print(f"  DEBUG elem {load['element_id']}: found {len(member_nodes)} nodes inside volume "
                f"x_range=[{min(t[1] for t in member_nodes):.3f}, {max(t[1] for t in member_nodes):.3f}] "
                f"L={L:.3f}")

            def build_slices():
                """Groups member_nodes into x-slices (cross-section layers)."""
                slice_tol = self.mesh_size * 0.3
                slices = []                              
                for n, x_a, y_l, z_l in sorted(member_nodes, key=lambda t: t[1]):
                    placed = False
                    for sl in slices:
                        if abs(x_a - sl[0]) < slice_tol:
                            sl[1].append(n)
                            placed = True
                            break
                    if not placed:
                        slices.append([x_a, [n]])
                slices.sort(key=lambda s: s[0])
                return slices

            def distribute_to_face(component_val, face_axis):
                if abs(component_val) < 1e-14:
                    return
                slices = build_slices()
                print(f"    slices={len(slices)} mesh_size={self.mesh_size} slice_tol={self.mesh_size*0.3:.4f}")
                if not slices:
                    return
                xs   = np.array([s[0] for s in slices])
                trib = np.zeros(len(slices))
                for i in range(len(slices)):
                    left  = (xs[i] - xs[i-1]) / 2.0 if i > 0              else xs[i]
                    right = (xs[i+1] - xs[i]) / 2.0 if i < len(slices)-1  else L - xs[i]
                    trib[i] = left + right
                for i, (x_mean, nodes_in_slice) in enumerate(slices):
                                             
                    mid_nodes = [n for n in nodes_in_slice if n.get('is_midedge', False)]
                    target_nodes = mid_nodes if mid_nodes else nodes_in_slice
                    
                    f_each   = component_val * trib[i] / len(target_nodes)                        
                    f_global = f_each * vy if face_axis == 'y' else f_each * vz
                    for n in target_nodes:                        
                        idx = n['idx'] * 3
                        P[idx    ] += f_global[0]
                        P[idx + 1] += f_global[1]
                        P[idx + 2] += f_global[2]

            distribute_to_face(wy_l, 'y')
            distribute_to_face(wz_l, 'z')

            if abs(wx_l) > 1e-14:
                slices = build_slices()
                xs   = np.array([s[0] for s in slices])
                trib = np.zeros(len(slices))
                for i in range(len(slices)):
                    left  = (xs[i] - xs[i-1]) / 2.0 if i > 0              else xs[i]
                    right = (xs[i+1] - xs[i]) / 2.0 if i < len(slices)-1  else L - xs[i]
                    trib[i] = left + right
                for i, (x_mean, nodes_in_slice) in enumerate(slices):
                                             
                    mid_nodes = [n for n in nodes_in_slice if n.get('is_midedge', False)]
                    target_nodes = mid_nodes if mid_nodes else nodes_in_slice
                    
                    f_each = wx_l * trib[i] / len(target_nodes)                        
                    for n in target_nodes:                        
                        idx = n['idx'] * 3
                        P[idx    ] += f_each * vx[0]
                        P[idx + 1] += f_each * vx[1]
                        P[idx + 2] += f_each * vx[2]

            total_applied = (abs(wx_l) + abs(wy_l) + abs(wz_l)) * L
            print(f"  member_dist elem {load['element_id']}: "
                f"w_local=[{wx_l:.2e},{wy_l:.2e},{wz_l:.2e}] N/m  "
                f"L={L:.3f}m  total≈{total_applied:.2e} N")

    def _get_section_bbox(self, sec):
        """Returns (width_y, height_z) — mirrors SolidMesher._section_bbox."""
        t = sec.get('type', 'rectangular')
        if t == 'rectangular':  return float(sec.get('b', 0.3)), float(sec.get('h', 0.3))
        if t == 'circular':     return float(sec.get('d', 0.3)), float(sec.get('d', 0.3))
        if t == 'pipe':         return float(sec.get('d', 0.3)), float(sec.get('d', 0.3))
        if t == 'i_section':    return max(float(sec.get('w_top', 0.3)), float(sec.get('w_bot', 0.3))), float(sec.get('h', 0.3))
        if t == 'tube':         return float(sec.get('b', 0.3)), float(sec.get('d', 0.3))
        if t == 'trapezoidal':  return max(float(sec.get('w_top', 0.3)), float(sec.get('w_bot', 0.3))), float(sec.get('d', 0.3))
        if t == 'arbitrary':
            verts = sec.get('vertices', [])
            if verts:
                ys = [v[0] for v in verts]
                zs = [v[1] for v in verts]
                return float(max(ys) - min(ys)), float(max(zs) - min(zs))
        return float(sec.get('b', 0.3)), float(sec.get('h', 0.3))

    def _parse_materials(self):
        for mat in self.raw.get('materials', []):
            self.materials[mat['name']] = {
                'E':   mat['E'],
                'nu':  mat['nu'],
                'rho': mat.get('rho', 0.0),                                 
            }

    def _map_nodes(self):
        user_ids = sorted(n['id'] for n in self.raw['nodes'])
        for idx, uid in enumerate(user_ids):
            self.node_id_to_idx[uid] = idx

        for n in self.raw['nodes']:
            idx        = self.node_id_to_idx[n['id']]
            raw_res    = n.get('restraints', [False] * 6)

            restraints = [bool(raw_res[i]) if i < len(raw_res) else False for i in range(6)]

            self.nodes.append({
                'id':         n['id'],
                'idx':        idx,
                'coords':     np.array([n['x'], n['y'], n['z']], dtype=float),
                'restraints': restraints,                                   
            })

        self.total_dofs = len(user_ids) * 3

    def _prepare_load_case(self, case_name):
        cases = self.raw.get('load_cases', [])
        case  = next((c for c in cases if c['name'] == case_name), None)

        if case is None and cases:
            case = cases[0]
            print(f"  Warning: load case '{case_name}' not found, "
                  f"using '{case['name']}' instead.")

        if case is None:
            raise ValueError(f"SolidDataManager: No load cases defined in model.")

        patterns = {p[0]: float(p[1]) for p in case.get('loads', [])}

        self._load_case = {
            'name':     case['name'],
            'patterns': patterns,
        }

    def _generate_self_weight(self):
        """
        Injects self-weight as nodal loads after elements are added by SolidMesher.
        Called again by SolidMesher.attach() once elements are populated.
        If elements list is empty now, this is a no-op (will be called again later).
        """
        if not self.elements:
            return                                                              

        active = self._load_case['patterns']

        sw_patterns = {}
        for pat in self.raw.get('load_patterns', []):
            if pat['name'] in active and pat.get('sw_mult', 0.0) != 0.0:
                sw_patterns[pat['name']] = pat['sw_mult'] * active[pat['name']]

        if not sw_patterns:
            return

        g = 9.81         
        count = 0

        for el in self.elements:
            mat = el['material']
            rho = mat.get('rho', 0.0)                                         
            if rho <= 0:
                continue

            coords = el['coords']          
            edge   = coords[1:4] - coords[0]
            V      = abs(np.linalg.det(edge)) / 6.0
            
            weight_corner = rho * V * (-1.0 / 20.0)                      
            weight_mid    = rho * V * (1.0 / 5.0)

            for pat_name, total_scale in sw_patterns.items():
                                                                             
                for i_local, n_idx in enumerate(el['node_indices']):
                    
                    w_node = weight_corner if i_local < 4 else weight_mid
                    
                    self.raw.setdefault('loads', []).append({
                        'type':    'nodal',
                        'pattern': pat_name,
                        'node_id': self.nodes[n_idx]['id'],
                        'fx': 0.0,
                        'fy': 0.0,
                        'fz': -w_node * total_scale,                        
                        'mx': 0.0, 'my': 0.0, 'mz': 0.0,
                    })
                    count += 1
        if count:
            print(f"  SolidDataManager: injected {count} self-weight nodal loads "
                  f"for patterns {list(sw_patterns.keys())}")
            
    def prep_submodel_boundaries(self, selected_element_ids, linear_results_path):
        """
        Identifies the boundary 'Cut Nodes' between selected and unselected elements,
        extracts their global displacements, and preps them as fixed boundaries.
        """
        import json
        
        print("SolidDataManager: Prepping Submodel Boundaries...")
        
        # 1. Load the linear static results
        try:
            with open(linear_results_path, 'r') as f:
                results = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Could not load linear results from {linear_results_path}: {e}")
            
        displacements = results.get("displacements", {})
        
        # 2. Identify the Cut Nodes
        selected_nodes = set()
        unselected_nodes = set()
        
        for el in self.raw.get('elements', []):
            if el['id'] in selected_element_ids:
                selected_nodes.add(el['n1_id'])
                selected_nodes.add(el['n2_id'])
            else:
                unselected_nodes.add(el['n1_id'])
                unselected_nodes.add(el['n2_id'])
                
        # The cut boundary is strictly where selected elements meet unselected elements
        cut_nodes = selected_nodes.intersection(unselected_nodes)
        
        # Also include any nodes within the selection that are actual global supports
        for n in self.raw.get('nodes', []):
            if n['id'] in selected_nodes and any(n.get('restraints', [False]*6)):
                cut_nodes.add(n['id'])

        print(f"  -> Identified Cut Nodes: {list(cut_nodes)}")

        # 3. Store prescribed displacements & trick the mesher
        self.prescribed_displacements = {}  # Format: { node_idx: [Ux, Uy, Uz, Rx, Ry, Rz] }
        
        count = 0
        for n in self.nodes:
            if n['id'] in cut_nodes:
                nid_str = str(n['id'])
                if nid_str in displacements:
                    # Save the 6-DOF displacement to apply in the SolidAssembler later
                    self.prescribed_displacements[n['idx']] = displacements[nid_str]
                    
                    # THE TRICK: Flag as fully restrained so SolidMesher builds Rigid Links here!
                    n['restraints'] = [True, True, True, True, True, True]
                    count += 1
                else:
                    print(f"  Warning: Cut Node {n['id']} not found in linear results!")
                    
        print(f"  -> Loaded exact global displacements for {count} boundary nodes.")

    def prep_submodel_boundaries_force_based(self, selected_element_ids,
                                              linear_results_path, matrices_path):
        """
        Force-based submodeling.

        Instead of imposing global displacements at cut nodes (which requires
        the K_fs * U_s partition trick), this method:
          1. Computes the internal end-forces at the cut from the global frame solution
          2. Applies them as external nodal loads on the rigid-link master DOFs
          3. Real support nodes inside the selection still get disp=0 BCs to kill RBD

        Inputs
        ------
        selected_element_ids : set/list of frame element IDs in the submodel
        linear_results_path  : path to  *_results.json  (displacements per node)
        matrices_path        : path to  *_matrices.json (k, t, fef per element)

        Outputs stored on self
        ----------------------
        self.cut_node_forces              : {node_id: np.array(6,) global}
        self.cut_nodes                    : set of node IDs with force BCs
        self.support_nodes_in_selection   : set of node IDs with disp=0 BCs
        """
        import json

        print("SolidDataManager: Prepping Force-Based Submodel Boundaries...")

        # ── 1. Load frame results and element matrices ────────────────────────
        try:
            with open(linear_results_path, 'r') as f:
                results = json.load(f)
            with open(matrices_path, 'r') as f:
                matrices = json.load(f)
        except Exception as e:
            raise RuntimeError(f"Could not load results/matrices: {e}")

        displacements = results.get("displacements", {})

        # ── 2. Classify nodes ─────────────────────────────────────────────────
        selected_nodes   = set()
        unselected_nodes = set()

        for el in self.raw.get('elements', []):
            ni, nj = el['n1_id'], el['n2_id']
            if el['id'] in selected_element_ids:
                selected_nodes.add(ni)
                selected_nodes.add(nj)
            else:
                unselected_nodes.add(ni)
                unselected_nodes.add(nj)

        # Nodes shared between inside and outside frame elements
        boundary_cut_nodes = selected_nodes & unselected_nodes

        # Real physical supports inside the selection — these kill rigid body motion
        support_nodes_in_selection = set()
        for n in self.raw.get('nodes', []):
            if n['id'] in selected_nodes and any(n.get('restraints', [False] * 6)):
                support_nodes_in_selection.add(n['id'])

        # All nodes that need a rigid link in the solid mesh
        all_rigid_link_nodes = boundary_cut_nodes | support_nodes_in_selection

        print(f"  -> Boundary cut nodes  (force BCs) : {sorted(boundary_cut_nodes)}")
        print(f"  -> Support nodes in selection (disp=0): {sorted(support_nodes_in_selection)}")

        # ── 3. Compute cut forces for every crossing element ──────────────────
        # A crossing element is OUTSIDE the selection AND touches a cut node.
        self.cut_node_forces = {}   # node_id → np.array(6,) in global coords

        for el in self.raw.get('elements', []):
            if el['id'] in selected_element_ids:
                continue  # purely inside — not a crossing element

            ni_id, nj_id = el['n1_id'], el['n2_id']
            ni_is_cut = ni_id in boundary_cut_nodes
            nj_is_cut = nj_id in boundary_cut_nodes

            if not ni_is_cut and not nj_is_cut:
                continue  # not touching the cut boundary

            str_id = str(el['id'])
            if str_id not in matrices:
                print(f"  Warning: No matrix data for element {el['id']}, skipping.")
                continue

            mat_data = matrices[str_id]
            k   = np.array(mat_data['k'])    # 12×12 local stiffness
            t   = np.array(mat_data['t'])    # 12×12 T_total = T_ecc @ T_rot
            fef = np.array(mat_data['fef'])  # 12   fixed-end forces (local)

            u_i = np.array(displacements.get(str(ni_id), [0.0] * 6))
            u_j = np.array(displacements.get(str(nj_id), [0.0] * 6))
            u_global_12 = np.concatenate([u_i, u_j])

            # Same formula as element_forces.py → end forces in LOCAL coords
            end_forces_local = k @ (t @ u_global_12) + fef

            # t[0:3, 0:3] == R_3x3  because T_ecc[0:3,0:3] == eye(3)
            R_3x3 = t[0:3, 0:3]

            def _to_global(F_loc6):
                """Rotate a 6-DOF local force vector to global coords."""
                out = np.zeros(6)
                out[0:3] = R_3x3.T @ F_loc6[0:3]   # forces
                out[3:6] = R_3x3.T @ F_loc6[3:6]   # moments
                return out

            if ni_is_cut:
                F_g = _to_global(end_forces_local[0:6])
                # FIX: Apply the opposite force to the boundary node
                self.cut_node_forces[ni_id] = (
                    self.cut_node_forces.get(ni_id, np.zeros(6)) - F_g
                )

            if nj_is_cut:
                F_g = _to_global(end_forces_local[6:12])
                # FIX: Apply the opposite force to the boundary node
                self.cut_node_forces[nj_id] = (
                    self.cut_node_forces.get(nj_id, np.zeros(6)) - F_g
                )

        print(f"  -> Computed cut forces for {len(self.cut_node_forces)} boundary nodes:")
        for nid, F in self.cut_node_forces.items():
            print(f"     Node {nid}: "
                  f"Fx={F[0]:.3f}  Fy={F[1]:.3f}  Fz={F[2]:.3f} | "
                  f"Mx={F[3]:.3f}  My={F[4]:.3f}  Mz={F[5]:.3f}")

        # ── 4. Flag nodes so SolidMesher creates rigid links at them ──────────
        # The assembler will later differentiate: cut_nodes → force BC,
        # support_nodes_in_selection → disp=0 BC.
        self.cut_nodes                  = boundary_cut_nodes
        self.support_nodes_in_selection = support_nodes_in_selection

        for n in self.nodes:
            if n['id'] in all_rigid_link_nodes:
                n['restraints'] = [True, True, True, True, True, True]

        print(f"  -> Force-based boundary prep complete. "
              f"{len(all_rigid_link_nodes)} rigid-link nodes flagged.")

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "test.mf"

    dm = SolidDataManager(path)
    dm.process_all(case_name="DEAD")

    print(f"\nFirst 3 nodes:")
    for n in dm.nodes[:3]:
        print(f"  id={n['id']}  idx={n['idx']}  "
              f"coords={n['coords']}  restraints={n['restraints']}")

    P = dm.build_load_vector()
    nonzero = [(i, v) for i, v in enumerate(P) if abs(v) > 1e-9]
    print(f"\nLoad vector non-zeros ({len(nonzero)} entries):")
    for i, v in nonzero[:10]:
        print(f"  DOF {i}: {v:.4e}")