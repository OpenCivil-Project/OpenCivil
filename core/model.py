                        
import json
from core.mesh import Node, FrameElement
from core.properties import Material, RectangularSection, ISection, GeneralSection
from core.grid import GridLines
from core.boundary import apply_restraint, Restraint
from core.mesh import Slab 
from core.units import unit_registry
import numpy as np
from core.loads import LoadPattern, NodalLoad, MemberLoad, MemberPointLoad
                      
class MassSource:
    def __init__(self, name):
        self.name = name
        self.include_self_mass = True                                           
        self.include_patterns = True                              
        self.load_patterns = []                                                         

class LoadPattern:
    def __init__(self, name, pattern_type="DEAD", self_weight_multiplier=0.0):
        self.name = name
        self.pattern_type = pattern_type                               
        self.self_weight_multiplier = float(self_weight_multiplier)

class NodalLoad:
    def __init__(self, node_id, pattern_name, fx=0, fy=0, fz=0, mx=0, my=0, mz=0):
        self.node_id = node_id
        self.pattern_name = pattern_name
        self.fx = fx; self.fy = fy; self.fz = fz
        self.mx = mx; self.my = my; self.mz = mz
    
    def __repr__(self):
        return f"NodalLoad(node={self.node_id}, pat={self.pattern_name}, Fz={self.fz})"

class MemberLoad:
    def __init__(self, element_id, pattern_name, wx=0, wy=0, wz=0, 
                 projected=False, coord_system="Global"):
        self.element_id = element_id
        self.pattern_name = pattern_name
        self.wx = float(wx)
        self.wy = float(wy)
        self.wz = float(wz)
        self.projected = bool(projected)
        self.coord_system = coord_system                      

    def __repr__(self):
        return f"MemberLoad(elem={self.element_id}, {self.coord_system}, wz={self.wz})"

class RigidDiaphragm:
    """
    Represents a rigid floor constraint (Constraint).
    """
    def __init__(self, name, axis="Z"):
        self.name = name
        self.axis = axis                                                  
        
        self.nodes = []                                           
        self.center_of_mass = [0, 0, 0]                             

class StructuralModel:
    def __init__(self, name="New Model"):
        self.name = name

        self.graphics_settings = {}                        
        
        self.nodes = {}                        
        self.elements = {}                             
        self.materials = {}                          
        self.sections = {}                          
        self.load_patterns = {}                           
        self.load_cases = {}   
        self.functions = {}                                      
        self.mass_sources = {}
        self.loads = []                                         
        self.add_load_pattern("DEAD", "DEAD", 1.0)
        self.create_default_cases()
        self.slabs = {}
        self.functions = {}
        self.constraints = {}
                         
        self.grid = GridLines()
        
        self._node_counter = 1
        self._elem_counter = 1
        self._slab_counter = 1

        self.add_load_pattern("DEAD", "DEAD", 1.0)

    def add_material(self, material):
        self.materials[material.name] = material
        return material

    def add_section(self, section):
        self.sections[section.name] = section
        return section

    def _get_next_node_id(self):
        """Calculates the next available Node ID."""
        if not self.nodes:
            return 1
        return max(self.nodes.keys()) + 1

    def _get_next_elem_id(self):
        """Calculates the next available Element ID."""
        if not self.elements:
            return 1
        return max(self.elements.keys()) + 1

    def add_node(self, x, y, z):
        """Creates and adds a node with a guaranteed unique ID."""
        new_id = self._get_next_node_id()
        new_node = Node(new_id, x, y, z)
        self.nodes[new_id] = new_node
                                                      
        self._node_counter = new_id + 1 
        return new_node

    def add_element(self, node_i, node_j, section, beta=0.0):
        """Creates and adds a frame element with a guaranteed unique ID."""
        new_id = self._get_next_elem_id()
        new_elem = FrameElement(new_id, node_i, node_j, section, beta)
        self.elements[new_id] = new_elem
        self._elem_counter = new_id + 1
        return new_elem

    def add_slab(self, nodes, thickness, material=None):
        """
        Creates and adds a visual Slab element.
        nodes: list of Node objects (3 or 4 nodes)
        """
        new_slab = Slab(self._slab_counter, nodes, thickness, material)
        self.slabs[self._slab_counter] = new_slab
        self._slab_counter += 1
        return new_slab

    def get_total_dofs(self):
        """Returns total degrees of freedom (Nodes * 6)"""
        return len(self.nodes) * 6
    
    def add_load_pattern(self, name, p_type, multiplier):
        self.load_patterns[name] = LoadPattern(name, p_type, multiplier)
        
        if name not in self.load_cases:
                                             
            lc = LoadCase(name, "Linear Static")
            lc.loads.append((name, 1.0))                                        
            self.load_cases[name] = lc

    def create_default_cases(self):
        """Syncs Load Patterns to Load Cases."""
                                
        if "MODAL" not in self.load_cases:
            self.load_cases["MODAL"] = LoadCase("MODAL", "Modal")
            
        for pat_name in self.load_patterns.keys():
            if pat_name not in self.load_cases:
                                                                    
                lc = LoadCase(pat_name, "Linear Static")
                lc.loads.append((pat_name, 1.0))
                self.load_cases[pat_name] = lc

    def add_load_case(self, case):
        self.load_cases[case.name] = case

    def assign_joint_load(self, node_id, pattern_name, fx=0, fy=0, fz=0, mx=0, my=0, mz=0, mode="replace"):
        """
        Assigns load to a node.
        mode: 'add' (accumulate), 'replace' (overwrite), 'delete' (remove)
        """
        if node_id not in self.nodes:
            raise KeyError(f"Node {node_id} does not exist.")
            
        existing_indices = []
        for i, load in enumerate(self.loads):
                                                                               
            if hasattr(load, 'node_id') and load.node_id == node_id and load.pattern_name == pattern_name:
                existing_indices.append(i)
        
        if mode == "delete":
                                                                  
            for i in reversed(existing_indices):
                del self.loads[i]
            return

        elif mode == "replace":
                                           
            for i in reversed(existing_indices):
                del self.loads[i]
            
            if any([fx, fy, fz, mx, my, mz]):
                new_load = NodalLoad(node_id, pattern_name, fx, fy, fz, mx, my, mz)
                self.loads.append(new_load)

        elif mode == "add":
                                                               
            if existing_indices:
                idx = existing_indices[0]
                self.loads[idx].fx += fx
                self.loads[idx].fy += fy
                self.loads[idx].fz += fz
                self.loads[idx].mx += mx
                self.loads[idx].my += my
                self.loads[idx].mz += mz
            else:
                 if any([fx, fy, fz, mx, my, mz]):
                    new_load = NodalLoad(node_id, pattern_name, fx, fy, fz, mx, my, mz)
                    self.loads.append(new_load)
                    
    def is_node_used(self, node_id):
        """
        Integrity Check: Returns True if the node is supporting any geometry.
        Used to prevent accidental deletion of critical joints.
        """
                           
        for el in self.elements.values():
            if el.node_i.id == node_id or el.node_j.id == node_id:
                return True
        
        for slab in self.slabs.values():
            for n in slab.nodes:
                if n.id == node_id:
                    return True
                    
        return False
    
    def assign_member_load(self, element_id, pattern_name, wx=0, wy=0, wz=0, 
                           projected=False, coord_system="Global", mode="replace"):
        """
        Assigns distributed load to a frame element.
        wx, wy, wz: Load magnitude in the specified coordinate system axes.
        coord_system: "Global" or "Local".
        """
        if element_id not in self.elements:
            raise KeyError(f"Element {element_id} does not exist.")
        
        existing_indices = []
        for i, load in enumerate(self.loads):
            if hasattr(load, 'element_id') and load.element_id == element_id and load.pattern_name == pattern_name:
                existing_indices.append(i)

        if mode == "delete":
            for i in reversed(existing_indices):
                del self.loads[i]
            return

        elif mode == "replace":
            for i in reversed(existing_indices):
                del self.loads[i]
            
            if any([wx, wy, wz]):
                new_load = MemberLoad(element_id, pattern_name, wx, wy, wz, 
                                      projected=projected, coord_system=coord_system)
                self.loads.append(new_load)

        elif mode == "add":
                                                                   
            added = False
            for idx in existing_indices:
                existing = self.loads[idx]
                if existing.coord_system == coord_system and existing.projected == projected:
                    existing.wx += wx
                    existing.wy += wy
                    existing.wz += wz
                    added = True
                    break
            
            if not added and any([wx, wy, wz]):
                new_load = MemberLoad(element_id, pattern_name, wx, wy, wz, 
                                      projected=projected, coord_system=coord_system)
                self.loads.append(new_load)

    def save_to_file(self, filepath):
        """Serializes the model data to a JSON file"""
        data = {
            "info": {
                "name": self.name,
                "units": unit_registry.current_unit_label 
            },
            "graphics": self.graphics_settings,
            "load_cases": [],
            "grid": {
                "x_lines": self.grid.x_lines,
                "y_lines": self.grid.y_lines,
                "z_lines": self.grid.z_lines
            },
            "materials": [],
            "sections": [],
            "nodes": [],
            "elements": [],
            "slabs": [],       
            "constraints": [],
            "load_patterns": [],
            "loads": [],
            "mass_sources": [],
            "functions": []
        }

        for lc in self.load_cases.values():
            data["load_cases"].append({
                "name": lc.name,
                "type": lc.case_type,
                "loads": lc.loads,                                                             
                "p_delta": lc.p_delta,
                "mass_source": lc.mass_source,
                "num_modes": getattr(lc, 'num_modes', 12),
                "rsa_loads": getattr(lc, 'rsa_loads', []),
                "modal_comb": getattr(lc, 'modal_comb', 'SRSS'),
                "dir_comb": getattr(lc, 'dir_comb', 'SRSS'),
                "modal_damping": getattr(lc, 'modal_damping', 0.05) 
            })

        for mat in self.materials.values():
            data["materials"].append({
                "name": mat.name,
                "E": mat.E, "nu": mat.nu, "G": mat.G, "rho": mat.density,
                "type": mat.mat_type, "fy": mat.fy, "fu": mat.fu
            })

        for sec in self.sections.values():
            sec_data = {
                "name": sec.name,
                "mat_name": sec.material.name,
                "color": sec.color,
                "modifiers": sec.modifiers,
                "properties": {
                    "A": sec.A, 
                    "J": sec.J, 
                    "I33": sec.I33, 
                    "I22": sec.I22, 
                    "As2": sec.Asy, 
                    "As3": sec.Asz
                }
            }
            if isinstance(sec, RectangularSection):
                sec_data.update({"type": "rectangular", "b": sec.b, "h": sec.h})
            elif isinstance(sec, ISection):
                sec_data.update({"type": "i_section", "h": sec.h, "w_top": sec.w_top, "t_top": sec.t_top, "w_bot": sec.w_bot, "t_bot": sec.t_bot, "t_web": sec.t_web})
            
            elif isinstance(sec, GeneralSection):
                sec_data.update({"type": "general"})
            
            data["sections"].append(sec_data)

        for n in self.nodes.values():
            data["nodes"].append({
                "id": n.id, "x": n.x, "y": n.y, "z": n.z,
                "restraints": n.restraints, "diaphragm": n.diaphragm_name  
            })

        for el in self.elements.values():
            data["elements"].append({
                "id": el.id,
                "n1_id": el.node_i.id,
                "n2_id": el.node_j.id,
                "sec_name": el.section.name,
                "beta": el.beta_angle,
                "rel_i": el.releases_i,
                "rel_j": el.releases_j,
                "cardinal": el.cardinal_point,
                "off_i": el.joint_offset_i.tolist(), 
                "off_j": el.joint_offset_j.tolist(),  
                "end_off_i": el.end_offset_i,
                "end_off_j": el.end_offset_j,
                "rz_factor": el.rigid_zone_factor
            })

        for slab in self.slabs.values():
            data["slabs"].append({"id": slab.id, "node_ids": [n.id for n in slab.nodes], "thick": slab.thickness})
        for name, const in self.constraints.items():
            data["constraints"].append({"name": name, "axis": const.axis})
        for lp in self.load_patterns.values():
            data["load_patterns"].append({"name": lp.name, "type": lp.pattern_type, "sw_mult": lp.self_weight_multiplier})
                                                                 
        for load in self.loads:
            load_data = {"pattern": load.pattern_name}
            
            if hasattr(load, 'force'): 
                load_data.update({
                    "type": "member_point",
                    "element_id": load.element_id,
                    "force": load.force,
                    "dist": load.dist,
                    "is_rel": load.is_relative,
                    "coord": load.coord_system,
                    "dir": load.direction,
                    "l_type": load.load_type
                })
            
            elif hasattr(load, 'wx'):
                load_data.update({
                    "type": "member_dist",
                    "element_id": load.element_id,
                    "wx": load.wx, "wy": load.wy, "wz": load.wz,
                    "projected": getattr(load, 'projected', False),
                    "coord": getattr(load, 'coord_system', "Global")
                })
                
            elif hasattr(load, 'node_id'):
                load_data.update({
                    "type": "nodal",
                    "node_id": load.node_id,
                    "fx": load.fx, "fy": load.fy, "fz": load.fz,
                    "mx": load.mx, "my": load.my, "mz": load.mz
                })
            
            data["loads"].append(load_data)

        if hasattr(self, 'mass_sources'):
            for ms in self.mass_sources.values():
                ms_data = {
                    "name": ms.name,
                    "include_self_mass": ms.include_self_mass,
                    "include_patterns": ms.include_patterns,
                    "load_patterns": ms.load_patterns                       
                }
                data["mass_sources"].append(ms_data)

        if hasattr(self, 'functions'):
            for func_name, func_data in self.functions.items():
                                                                                                 
                data["functions"].append(func_data)

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Model saved to {filepath}")

    def load_from_file(self, filepath):
        """Clears current model and loads data from JSON"""
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        self.nodes.clear(); self.elements.clear(); self.materials.clear()
        self.sections.clear(); self.load_patterns.clear(); self.loads.clear()
        self.slabs.clear(); self.constraints.clear()
        self.functions = {}
        self._node_counter = 1; self._elem_counter = 1; self._slab_counter = 1 
        
        self.name = data["info"]["name"]
        self.saved_unit_system = data["info"].get("units", "kN, m, C")
        
        grid_data = data["grid"]
        if "x_lines" in grid_data:
            self.grid.x_lines = grid_data["x_lines"]; self.grid.y_lines = grid_data["y_lines"]; self.grid.z_lines = grid_data["z_lines"]
        else:
            self.grid.x_grids = grid_data["x"]; self.grid.y_grids = grid_data["y"]; self.grid.z_grids = grid_data["z"]

        for m_data in data["materials"]:
            mat = Material(m_data["name"], m_data["E"], m_data["nu"], m_data["rho"], m_data["type"], m_data.get("fy", 0), m_data.get("fu", 0))
            self.add_material(mat)

        for s_data in data["sections"]:
            mat = self.materials.get(s_data["mat_name"])
            if not mat: continue 
            sec = None
            if s_data["type"] == "rectangular":
                sec = RectangularSection(s_data["name"], mat, s_data["b"], s_data["h"])
            elif s_data["type"] == "i_section":
                                                                        
                saved_props = s_data.get("properties", None) 
                
                sec = ISection(
                    s_data["name"], 
                    mat, 
                    s_data["h"], 
                    s_data["w_top"], 
                    s_data["t_top"], 
                    s_data["w_bot"], 
                    s_data["t_bot"], 
                    s_data["t_web"],
                    props=saved_props                   
                )
            elif s_data["type"] == "general":
                                             
                p = s_data["properties"]
                props_dict = {
                    'A': p["A"], 'J': p["J"], 
                    'I33': p["I33"], 'I22': p["I22"],
                    'Asy': p["As2"], 'Asz': p["As3"]
                }
                sec = GeneralSection(s_data["name"], mat, props_dict)

            if sec:
                if "color" in s_data: sec.color = tuple(s_data["color"])
                if "modifiers" in s_data: sec.modifiers = s_data["modifiers"]
                self.add_section(sec)

        for n_data in data["nodes"]:
            n_id = n_data["id"]
            node = self.add_node(n_data["x"], n_data["y"], n_data["z"])
            del self.nodes[node.id]; node.id = n_id; self.nodes[n_id] = node
            node.restraints = n_data["restraints"]
            if "diaphragm" in n_data: node.diaphragm_name = n_data["diaphragm"]
            self._node_counter = max(self._node_counter, n_id + 1)

        if "constraints" in data:
            for c_data in data["constraints"]: self.add_constraint(c_data["name"], c_data["axis"])

        self.slabs.clear(); self.constraints.clear()
        self.graphics_settings = data.get("graphics", {})
        self.name = data["info"]["name"]

        for el_data in data["elements"]:
            n1 = self.nodes.get(el_data["n1_id"])
            n2 = self.nodes.get(el_data["n2_id"])
            sec = self.sections.get(el_data["sec_name"])
            
            if n1 and n2 and sec:
                beta = el_data.get("beta", 0.0)
                el = self.add_element(n1, n2, sec, beta)
                el.releases_i = el_data.get("rel_i", [False]*6)
                el.releases_j = el_data.get("rel_j", [False]*6)
                
                del self.elements[el.id]; el.id = el_data["id"]; self.elements[el.id] = el
                self._elem_counter = max(self._elem_counter, el.id + 1)
                
                if "cardinal" in el_data:
                    el.cardinal_point = el_data["cardinal"]
                if "off_i" in el_data:
                    el.joint_offset_i = np.array(el_data["off_i"])
                if "off_j" in el_data:
                    el.joint_offset_j = np.array(el_data["off_j"])

                el.end_offset_i = el_data.get("end_off_i", 0.0)
                el.end_offset_j = el_data.get("end_off_j", 0.0)
                el.rigid_zone_factor = el_data.get("rz_factor", 0.0)

        if "slabs" in data:
            for sl_data in data["slabs"]:
                slab_nodes = []
                for nid in sl_data["node_ids"]:
                    if nid in self.nodes: slab_nodes.append(self.nodes[nid])
                if len(slab_nodes) >= 3:
                    new_slab = self.add_slab(slab_nodes, sl_data["thick"])
                    del self.slabs[new_slab.id]; new_slab.id = sl_data["id"]; self.slabs[new_slab.id] = new_slab
                    self._slab_counter = max(self._slab_counter, new_slab.id + 1)

        if "load_cases" in data:
            for lc_data in data["load_cases"]:
                name = lc_data["name"]
                c_type = lc_data.get("type", "Linear Static")
                
                new_lc = LoadCase(name, c_type)
                
                raw_loads = lc_data.get("loads", [])
                new_lc.loads = [tuple(item) for item in raw_loads] 
                raw_rsa = lc_data.get("rsa_loads", [])
                new_lc.rsa_loads = [tuple(item) for item in raw_rsa]
                new_lc.modal_comb = lc_data.get("modal_comb", "SRSS")
                new_lc.dir_comb = lc_data.get("dir_comb", "SRSS")
                new_lc.p_delta = lc_data.get("p_delta", False)
                new_lc.mass_source = lc_data.get("mass_source", "Default")
                new_lc.num_modes = lc_data.get("num_modes", 12)
                new_lc.modal_damping = lc_data.get("modal_damping", 0.05)
                
                self.load_cases[name] = new_lc
        else:
                                    
            self.create_default_cases()

        if "mass_sources" in data:
                                             
            if not hasattr(self, 'mass_sources'):
                self.mass_sources = {}

            for ms_data in data["mass_sources"]:
                new_ms = MassSource(ms_data["name"])
                new_ms.include_self_mass = ms_data["include_self_mass"]
                new_ms.include_patterns = ms_data["include_patterns"]
                                                             
                new_ms.load_patterns = [tuple(x) for x in ms_data["load_patterns"]]

                self.mass_sources[new_ms.name] = new_ms

        if "load_patterns" in data:
            for lp_data in data["load_patterns"]: self.add_load_pattern(lp_data["name"], lp_data["type"], lp_data["sw_mult"])
        else: self.add_load_pattern("DEAD", "DEAD", 1.0)
             
        if "functions" in data:
            for func_data in data["functions"]:
                f_name = func_data["name"]
                self.functions[f_name] = func_data

        if "loads" in data:
            for load_data in data["loads"]:
                pattern_name = load_data["pattern"]
                l_type = load_data.get("type", "nodal")                         
                
                if l_type == "member": l_type = "member_dist"

                if l_type == "nodal":
                    new_load = NodalLoad(load_data["node_id"], pattern_name, 
                                         load_data["fx"], load_data["fy"], load_data["fz"], 
                                         load_data["mx"], load_data["my"], load_data["mz"])
                    self.loads.append(new_load)

                elif l_type == "member_dist":
                                                                       
                    coord = load_data.get("coord", "Global")
                    proj = load_data.get("projected", False)
                    new_load = MemberLoad(load_data["element_id"], pattern_name, 
                                          load_data["wx"], load_data["wy"], load_data["wz"],
                                          projected=proj, coord_system=coord)
                    self.loads.append(new_load)

                elif l_type == "member_point":
                                   
                    new_load = MemberPointLoad(
                        load_data["element_id"], pattern_name,
                        load_data["force"], load_data["dist"],
                        load_data["is_rel"], load_data["coord"],
                        load_data["dir"], load_data.get("l_type", "Force")
                    )
                    self.loads.append(new_load)
        
        print(f"Model loaded from {filepath}")

    def add_constraint(self, name, axis="Z"):
        """Defines a new Rigid Diaphragm (e.g., 'D1')"""

        if name not in self.constraints:
            self.constraints[name] = RigidDiaphragm(name, axis)

    def replicate_selection(self, node_ids, elem_ids, dx, dy, dz, num_copies, delete_original=False):
        """
        Replicates selected nodes and elements linearly.
        Features:
        - Copies Restraints, Releases, and ALL LOADS (Point/Dist/Nodal).
        - Copies Advanced Attributes (Cardinal Points, Rigid Offsets).
        - Smart Diaphragm Logic.
        """
                                                                                    
        involved_node_ids = set(node_ids)
        for eid in elem_ids:
            if eid in self.elements:
                el = self.elements[eid]
                involved_node_ids.add(el.node_i.id)
                involved_node_ids.add(el.node_j.id)
        
        node_load_map = {}
        elem_load_map = {}
        
        for load in self.loads:
            if hasattr(load, 'node_id'):
                if load.node_id not in node_load_map: node_load_map[load.node_id] = []
                node_load_map[load.node_id].append(load)
            elif hasattr(load, 'element_id'):
                if load.element_id not in elem_load_map: elem_load_map[load.element_id] = []
                elem_load_map[load.element_id].append(load)

        for i in range(1, num_copies + 1):
            node_map = {}                                  

            for nid in involved_node_ids:
                if nid not in self.nodes: continue
                original_node = self.nodes[nid]
                
                nx = original_node.x + (dx * i)
                ny = original_node.y + (dy * i)
                nz = original_node.z + (dz * i)
                
                new_node = self.get_or_create_node(nx, ny, nz)
                node_map[nid] = new_node
                
                new_node.restraints = original_node.restraints[:] 
                
                if abs(dz) > 0.001:
                    new_node.diaphragm_name = None 
                else:
                    new_node.diaphragm_name = original_node.diaphragm_name

                if nid in node_load_map:
                    for old_load in node_load_map[nid]:
                        self.assign_joint_load(
                            new_node.id, 
                            old_load.pattern_name,
                            old_load.fx, old_load.fy, old_load.fz,
                            old_load.mx, old_load.my, old_load.mz,
                            mode="add"
                        )

            for eid in elem_ids:
                if eid not in self.elements: continue
                original_elem = self.elements[eid]
                
                if original_elem.node_i.id not in node_map or original_elem.node_j.id not in node_map:
                    continue 
                
                new_n1 = node_map[original_elem.node_i.id]
                new_n2 = node_map[original_elem.node_j.id]
                
                new_elem = self.add_element(new_n1, new_n2, original_elem.section, original_elem.beta_angle)
                
                new_elem.releases_i = original_elem.releases_i[:]
                new_elem.releases_j = original_elem.releases_j[:]
                
                new_elem.cardinal_point = original_elem.cardinal_point
                if hasattr(original_elem, 'joint_offset_i'):
                    new_elem.joint_offset_i = original_elem.joint_offset_i.copy()
                if hasattr(original_elem, 'joint_offset_j'):
                    new_elem.joint_offset_j = original_elem.joint_offset_j.copy()

                new_elem.end_offset_i = getattr(original_elem, 'end_offset_i', 0.0)
                new_elem.end_offset_j = getattr(original_elem, 'end_offset_j', 0.0)
                new_elem.rigid_zone_factor = getattr(original_elem, 'rigid_zone_factor', 0.0)

                if eid in elem_load_map:
                    for old_load in elem_load_map[eid]:
                        
                        if hasattr(old_load, 'wx'):
                             self.assign_member_load(
                                new_elem.id,
                                old_load.pattern_name,
                                old_load.wx, old_load.wy, old_load.wz,
                                projected=getattr(old_load, 'projected', False),
                                coord_system=getattr(old_load, 'coord_system', "Global"),
                                mode="add"
                            )
                        
                        elif hasattr(old_load, 'force'):
                            self.assign_member_point_load(
                                new_elem.id,
                                old_load.pattern_name,
                                old_load.force,
                                old_load.dist,
                                old_load.is_relative,
                                old_load.coord_system,
                                old_load.direction,
                                getattr(old_load, 'load_type', "Force"),
                                mode="add"
                            )

        if delete_original:
            for eid in elem_ids:
                if eid in self.elements:
                    self.remove_element(eid) 
            
            for nid in node_ids:
                 self._cleanup_orphan_node(nid)

        print(f"Replicated {len(elem_ids)} frames and {len(node_ids)} joints {num_copies} times.")
    
    def merge_nodes(self, tolerance=0.001):
        """
        Merges nodes that are within a specific distance of each other.
        Remaps elements to the 'master' node and deletes 'slave' nodes.
        Returns the number of nodes deleted.
        """
                                                                    
        sorted_nodes = sorted(self.nodes.values(), key=lambda n: (n.x, n.y, n.z))
        
        remap_dict = {}                             
        nodes_to_delete = set()
        
        for i in range(len(sorted_nodes)):
            master = sorted_nodes[i]
            if master.id in nodes_to_delete: continue                                   
            
            for j in range(i + 1, len(sorted_nodes)):
                slave = sorted_nodes[j]
                
                if (slave.x - master.x) > tolerance: break
                
                dist = ((master.x - slave.x)**2 + (master.y - slave.y)**2 + (master.z - slave.z)**2)**0.5
                
                if dist < tolerance:
                                        
                    remap_dict[slave.id] = master.id
                    nodes_to_delete.add(slave.id)
                    
        if not remap_dict:
            print("No duplicate nodes found.")
            return 0

        for el in self.elements.values():
            if el.node_i.id in remap_dict:
                el.node_i = self.nodes[remap_dict[el.node_i.id]]
            if el.node_j.id in remap_dict:
                el.node_j = self.nodes[remap_dict[el.node_j.id]]
        
        for slab in self.slabs.values():
            new_nodes = []
            for n in slab.nodes:
                if n.id in remap_dict:
                    new_nodes.append(self.nodes[remap_dict[n.id]])
                else:
                    new_nodes.append(n)
            slab.nodes = new_nodes

        for load in self.loads:
            if hasattr(load, 'node_id') and load.node_id in remap_dict:
                load.node_id = remap_dict[load.node_id]

        for nid in nodes_to_delete:
            del self.nodes[nid]

        print(f"Merged {len(nodes_to_delete)} duplicate nodes.")
        return len(nodes_to_delete)

    def get_or_create_node(self, x, y, z, tol=0.005):
        """
        Prevents duplicates by checking if a node exists within tolerance.
        """
        for node in self.nodes.values():
            dist = ((node.x - x)**2 + (node.y - y)**2 + (node.z - z)**2)**0.5
            if dist < tol:
                return node
        return self.add_node(x, y, z)

    def remove_element(self, element_id):
        """
        Deletes an element, its assigned loads, and cleans up valid orphan nodes.
        """
        if element_id not in self.elements: return
        
        el = self.elements[element_id]
        n1_id = el.node_i.id
        n2_id = el.node_j.id
        
        del self.elements[element_id]
        
        self.loads = [
            load for load in self.loads 
            if not (hasattr(load, 'element_id') and load.element_id == element_id)
        ]
        
        self._cleanup_orphan_node(n1_id)
        self._cleanup_orphan_node(n2_id)

    def _cleanup_orphan_node(self, node_id):
        """
        Deletes a node only if it is completely unused.
        Also removes any Nodal Loads assigned to it.
        """
        if node_id not in self.nodes: return
        
        for el in self.elements.values():
            if el.node_i.id == node_id or el.node_j.id == node_id:
                return               

        for slab in self.slabs.values():
            for n in slab.nodes:
                if n.id == node_id:
                    return               

        if any(self.nodes[node_id].restraints):
            return 

        self.loads = [
            load for load in self.loads 
            if not (hasattr(load, 'node_id') and load.node_id == node_id)
        ]

        del self.nodes[node_id]
        print(f"Garbage Collector: Removed orphaned Node {node_id} and its loads.")

    def assign_member_point_load(self, element_id, pattern_name, force, dist, is_relative, 
                                 coord_system, direction, load_type="Force", mode="replace"):
        """
        Assigns a concentrated Point Load or Moment to a frame element.
        """
        if element_id not in self.elements:
            raise KeyError(f"Element {element_id} does not exist.")

        existing_indices = []
        for i, load in enumerate(self.loads):
                                                                                       
            if (hasattr(load, 'element_id') and 
                hasattr(load, 'force') and                                           
                load.element_id == element_id and 
                load.pattern_name == pattern_name):
                existing_indices.append(i)

        if mode == "delete":
            for i in reversed(existing_indices):
                del self.loads[i]
            return

        elif mode == "replace":
                                                  
            for i in reversed(existing_indices):
                del self.loads[i]
            
            if force != 0:
                new_load = MemberPointLoad(element_id, pattern_name, force, dist, 
                                           is_relative, coord_system, direction, load_type)
                self.loads.append(new_load)

        elif mode == "add":
                                                                                                     
            if force != 0:
                new_load = MemberPointLoad(element_id, pattern_name, force, dist, 
                                           is_relative, coord_system, direction, load_type)
                self.loads.append(new_load)

class LoadCase:
    def __init__(self, name, case_type="Linear Static"):
        self.name = name
        self.case_type = case_type                                                            
        
        self.loads = [] 
        
        self.mass_source = "Default"                        
        self.p_delta = False                                   
        self.modal_case = None                                                     
        self.num_modes = 12                                
