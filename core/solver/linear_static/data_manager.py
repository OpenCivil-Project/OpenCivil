                                                             
import json
import numpy as np
from error_definitions import SolverException

class DataManager:
    def __init__(self, json_path):
        try:
            with open(json_path, 'r') as f:
                self.raw = json.load(f)
        except FileNotFoundError:
            raise SolverException("E101", f"Path: {json_path}")
        except json.JSONDecodeError:
            raise SolverException("E102", f"File: {json_path}")
        
        self.node_id_to_idx = {}                         
        self.materials = {}                              
        self.sections = {}                              
        
        self.nodes = []                                      
        self.elements = []                                      
        self.load_case = None                                       
        self.total_dofs = 0                                      

    def _generate_self_weight(self):
        """
        Calculates A * gamma (Unit Weight) for every element and injects it as a 
        Member Distributed Load into the raw load list.
        """
                                                                         
        if 'load_patterns' not in self.raw: return
        
        active_pattern_names = {p[0] for p in self.load_case['patterns']} 
        
        target_patterns = []
        for pat in self.raw['load_patterns']:
                                                                    
            if pat['name'] in active_pattern_names and pat['sw_mult'] != 0:
                target_patterns.append(pat)

        if not target_patterns: return

        print(f"      Generating self-weight for patterns: {[p['name'] for p in target_patterns]}")

        count = 0
        
        for el in self.elements:
                                 
            A = el['section']['A']
            gamma = el['material']['rho']                                  
            
            w_per_len = A * gamma 
            
            if w_per_len <= 1e-9: continue

            for pat in target_patterns:
                mult = pat['sw_mult']
                
                w_z = -1.0 * w_per_len * mult
                
                new_load = {
                    'type': 'member_dist',
                    'pattern': pat['name'],
                    'element_id': el['id'],
                    'wx': 0.0, 
                    'wy': 0.0, 
                    'wz': w_z,
                    'coord': 'Global',
                    'projected': False
                }
                
                if 'loads' not in self.raw: self.raw['loads'] = []
                self.raw['loads'].append(new_load)
                count += 1
                
        if count > 0:
            print(f"      -> Injected {count} self-weight load records.")

    def process_all(self, case_name="DEAD"):
        """The master sequence to prepare the solver data."""
        self._parse_properties()
        self._map_nodes()
        self._parse_elements()
        self._prepare_load_case(case_name)
        self._generate_self_weight()

    def _map_nodes(self):
                                         
        user_ids = sorted([n['id'] for n in self.raw['nodes']])
        for idx, u_id in enumerate(user_ids):
            self.node_id_to_idx[u_id] = idx
            
        for n_data in self.raw['nodes']:
            self.nodes.append({
                'id': n_data['id'],
                'idx': self.node_id_to_idx[n_data['id']],
                'coords': np.array([n_data['x'], n_data['y'], n_data['z']]),
                'restraints': n_data['restraints'],
                'diaphragm': n_data.get('diaphragm', None)
            })
            
        self.total_dofs = len(user_ids) * 6

        self.diaphragm_groups = {}
        for c in self.raw.get('constraints', []):
            self.diaphragm_groups[c['name']] = []
        for node in self.nodes:
            dia = node['diaphragm']
            if dia and dia in self.diaphragm_groups:
                self.diaphragm_groups[dia].append(node['id'])
        
        active = {k: v for k, v in self.diaphragm_groups.items() if len(v) >= 2}
        if active:
            print(f"      Diaphragms found: { {k: len(v) for k, v in active.items()} }")

    def _parse_properties(self):
                            
        for mat in self.raw['materials']:
            self.materials[mat['name']] = {
                'E': mat['E'], 
                'G': mat['G'], 
                'rho': mat['rho']
            }
            
        for sec in self.raw['sections']:
            p = sec['properties']
            self.sections[sec['name']] = {
                'mat_name': sec['mat_name'],
                'A':   p.get('A', 0.0),
                'J':   p.get('J', 0.0),
                'I33': p.get('I33', 0.0),
                'I22': p.get('I22', 0.0),
                'As2': p.get('As2', 0.0),                                             
                'As3': p.get('As3', 0.0)                                              
            }

    def _parse_elements(self):
        for el_data in self.raw['elements']:
                              
            idx_i = self.node_id_to_idx[el_data['n1_id']]
            idx_j = self.node_id_to_idx[el_data['n2_id']]
            
            p1 = next(n['coords'] for n in self.nodes if n['idx'] == idx_i)
            p2 = next(n['coords'] for n in self.nodes if n['idx'] == idx_j)
            
            off_i = np.array(el_data.get('off_i', [0,0,0]))
            off_j = np.array(el_data.get('off_j', [0,0,0]))

            p1_adj = p1 + off_i
            p2_adj = p2 + off_j
            
            L_total = np.linalg.norm(p2_adj - p1_adj)
            
            if L_total < 1e-9:
                raise SolverException("E201", f"Element ID: {el_data['id']} connects coincident nodes.")

            end_off_i = el_data.get('end_off_i', 0.0)
            end_off_j = el_data.get('end_off_j', 0.0)
            
            L_clear = L_total - (end_off_i + end_off_j)
            
            try:
                self.elements.append({
                    'id': el_data['id'],
                    'node_indices': [idx_i, idx_j],
                    'section': self.sections[el_data['sec_name']],
                    'material': self.materials[self.sections[el_data['sec_name']]['mat_name']],
                    'L_total': L_total,
                    'L_clear': L_clear,
                    'end_off_i': end_off_i, 
                    'end_off_j': end_off_j,
                    'beta': el_data['beta'],
                    'releases': [el_data['rel_i'], el_data['rel_j']],
                    'offsets': [el_data['off_i'], el_data['off_j']]
                })
            except KeyError as e:
                                                   
                raise SolverException("E103", f"Element {el_data['id']} references missing section: {e}")

    def _prepare_load_case(self, case_name):
                                
        case_data = next((c for c in self.raw['load_cases'] if c['name'] == case_name), None)
        
        if not case_data and case_name == "DEAD" and len(self.raw['load_cases']) > 0:
             case_data = self.raw['load_cases'][0]

        if not case_data:
            raise SolverException("E104", f"Load Case '{case_name}' is not defined in the input.")
            
        self.load_case = {
            'name': case_name,
            'patterns': case_data['loads'],                               
        }
        
    def build_load_vector(self):
        """Constructs the global P vector for the selected Load Case."""
        P = np.zeros(self.total_dofs)
        
        active_patterns = {pat: scale for pat, scale in self.load_case['patterns']}
        
        for load in self.raw['loads']:
            if load['pattern'] not in active_patterns: continue
            scale = active_patterns[load['pattern']]
            
            if load['type'] == 'nodal':
                node_idx = self.node_id_to_idx[load['node_id']]
                start_row = node_idx * 6
                forces = np.array([load['fx'], load['fy'], load['fz'], load['mx'], load['my'], load['mz']])
                P[start_row : start_row + 6] += forces * scale
                
        return P
