import sys
import os
import shlex
import copy

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.model import StructuralModel
from core.properties import (Material, RectangularSection, ISection, GeneralSection,
                             CircularSection, PipeSection, TubeSection, TrapezoidalSection)
from core.solver.linear_static.main_engine import run_linear_static_analysis

class CLIDispatcher:
    """
    Stateful CLI dispatcher.  Holds a reference to a live StructuralModel and
    its own undo/redo stacks.  Call dispatch(raw_string) once per user command.

    Designed to work both standalone (start_terminal) and embedded inside the
    OpenCivil GUI terminal panel — in the GUI case the MainWindow creates one
    dispatcher that shares self.model, so every CLI command instantly affects
    the same object the canvas is rendering.
    """

    def __init__(self, model: StructuralModel):
        self.model      = model
        self.undo_stack = []
        self.redo_stack = []
        self.MAX_UNDO   = 50

    def _snapshot(self):
        m = self.model
        return {
            'nodes':         copy.deepcopy(m.nodes),
            'elements':      copy.deepcopy(m.elements),
            'materials':     copy.deepcopy(m.materials),
            'sections':      copy.deepcopy(m.sections),
            'load_patterns': copy.deepcopy(m.load_patterns),
            'load_cases':    copy.deepcopy(m.load_cases),
            'loads':         copy.deepcopy(m.loads),
            'slabs':         copy.deepcopy(m.slabs),
            'constraints':   copy.deepcopy(m.constraints),
        }

    def _restore(self, snap):
        m = self.model
        m.nodes         = snap['nodes']
        m.elements      = snap['elements']
        m.materials     = snap['materials']
        m.sections      = snap['sections']
        m.load_patterns = snap['load_patterns']
        m.load_cases    = snap['load_cases']
        m.loads         = snap['loads']
        m.slabs         = snap['slabs']
        m.constraints   = snap['constraints']
        for el in m.elements.values():
            if el.node_i.id in m.nodes:
                el.node_i = m.nodes[el.node_i.id]
            if el.node_j.id in m.nodes:
                el.node_j = m.nodes[el.node_j.id]

    def _push_undo(self):
        self.undo_stack.append(self._snapshot())
        if len(self.undo_stack) > self.MAX_UNDO:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _resolve_grid_point(self, token):
        """
        Resolves 'A,1,Z1' → (x, y, z) by looking up IDs in model.grid.
        Used by 'frame' — creates the node if it doesn't exist yet.
        Raises ValueError with a clear message on any lookup failure.
        """
        model = self.model
        if not model.grid.x_lines or not model.grid.y_lines or not model.grid.z_lines:
            raise ValueError(
                "No grid defined. Define your grid first:\n"
                "  grid x 0 5 10\n"
                "  grid y 0 4\n"
                "  grid z 0 3 6"
            )
        parts = [p.strip() for p in token.split(",")]
        if len(parts) != 3:
            raise ValueError(f"Grid point must be 'X_ID,Y_ID,Z_ID' — got: '{token}'")

        xid, yid, zid = parts

        x = next((ln['ord'] for ln in model.grid.x_lines if str(ln['id']) == xid), None)
        y = next((ln['ord'] for ln in model.grid.y_lines if str(ln['id']) == yid), None)
        z = next((ln['ord'] for ln in model.grid.z_lines if str(ln['id']) == zid), None)

        if x is None: raise ValueError(f"X grid ID '{xid}' not found. Run 'view grid' to see defined IDs.")
        if y is None: raise ValueError(f"Y grid ID '{yid}' not found. Run 'view grid' to see defined IDs.")
        if z is None: raise ValueError(f"Z grid ID '{zid}' not found. Run 'view grid' to see defined IDs.")

        return x, y, z

    def _resolve_existing_node(self, token):
        """
        Like _resolve_grid_point but also verifies a node already exists there.
        Used by 'support' and 'load' — you can't assign to a bare grid intersection,
        there must be a frame endpoint (or existing node) at that point.
        """
        x, y, z = self._resolve_grid_point(token)
        tol = 0.005
        for node in self.model.nodes.values():
            dist = ((node.x - x)**2 + (node.y - y)**2 + (node.z - z)**2)**0.5
            if dist < tol:
                return node
        raise ValueError(
            f"No node exists at grid point {token}.\n"
            f"Draw a frame endpoint there first."
        )

    def dispatch(self, raw_input: str):
        """
        Parse and execute one CLI command string.
        Returns: "modified" | "clear" | "exit" | None
        Never raises — all exceptions are caught and printed.
        """
        raw_input = raw_input.strip()
        if not raw_input:
            return None

        try:
            cmd = [t.strip('"') for t in shlex.split(raw_input, posix=False)]
        except ValueError:
            cmd = raw_input.split()

        action = cmd[0].lower()

        try:
            return self._execute(action, cmd)
        except Exception as e:
            print(f"Oops, syntax error: {e}. Check 'help' for proper format!")
            return None

    def _execute(self, action: str, cmd: list):
        model = self.model

        _no_model_needed = {"exit", "clear", "unlock", "help", "project", "open"}
        if self.model is None and action not in _no_model_needed:
            print("Error: No active model. Run 'project <name> <path>' to create one or 'open <path>' to load one.")
            return None

        if action == "exit":
            print("Closing terminal. See ya bro!")
            return "exit"

        elif action == "clear":
            return "clear"

        elif action == "unlock":
            print(" -> Unlocking model...")
            return "unlock"

        elif action == "help":
            print("\n" + "="*65)
            print("  OpenCivil CLI - Command Reference")
            print("="*65)
            print("\n  [PROJECT]")
            print("  project <n> <full_path>       : e.g. project MyFrame E:\\Projects")
            print("  open <full_path.mf>           : e.g. open E:\\Projects\\model.mf")
            print("  save                          : Save current model to active project")
            print("  undo                          : Undo last CLI change (up to 50 steps)")
            print("  redo                          : Redo last undone CLI change")
            print("  solve                         : Save + run Linear Static solver")
            print("  list                          : List files in active project folder")
            print("  clear                         : Clear the terminal screen")
            print("\n  [PROPERTIES]")
            print("  mat <n> <E> <nu> <rho> <type>")
            print("  del_mat <n>")
            print("  mod_mat <n> <prop=val> ...     props: E nu rho fy fu type")
            print("  del_sec <n>")
            print("    e.g.  mat C30 3e7 0.2 2400 Concrete")
            print("  sec <n> <mat> <type> [params]")
            print("    rect  <b> <h>")
            print("    circ  <d>")
            print("    pipe  <d> <t>")
            print("    tube  <d> <b> <tf> <tw>")
            print("    trap  <d> <w_top> <w_bot>")
            print("    i_sec <h> <w_t> <t_t> <w_b> <t_b> <t_w>")
            print("    gen   <A> <J> <I33> <I22> <Asy> <Asz>")
            print("\n  [GEOMETRY]")
            print("  grid <x|y|z> <ord1> <ord2> ...    e.g. grid x 0 5 10 15")
            print("    x auto-names: A B C ...  |  y: 1 2 3 ...  |  z: Z1 Z2 Z3 ...")
            print("  frame <pt1> <pt2> <sec_name>       e.g. frame A,1,Z1 A,1,Z2 COL")
            print("    points use grid notation: X_ID,Y_ID,Z_ID")
            print("    nodes are created automatically as frame endpoints")
            print("  del_frame <id>")
            print("  mod_frame <id> <prop> <val>   props: cardinal, offset_i, offset_j, beta")
            print("  release <id> <i|j> <6 bools>  e.g.  release 1 j 0 0 0 0 1 1")
            print("  support <pt> <6 bools>         e.g.  support A,1,Z1 1 1 1 1 1 1  (fixed)")
            print("    bools order: Ux Uy Uz Rx Ry Rz")
            print("  view grid                      : show defined grid lines")
            print("\n  [LOADS]")
            print("  pattern <n> <type> <sw_mult>")
            print("  load <node_id> <pattern> [fx=0] [fy=0] [fz=0] [mx=0] [my=0] [mz=0]")
            print("    e.g.  load 3 DEAD fz=-50")
            print("  dist_load <beam_id> <pat> <wx> <wy> <wz> [Global|Local]")
            print("    e.g.  dist_load 2 DEAD 0 0 -10 Global")
            print("  point_load <beam_id> <pat> <F> <rel_dist> <dir>")
            print("    e.g.  point_load 2 LIVE -20 0.5 z      dirs: x y z")
            print("\n  [VIEW]")
            print("  view <mats|secs|beams|patterns|loads|grid>")
            print("="*65)
            return None

        elif action == "undo":
            if not self.undo_stack:
                print("Nothing to undo.")
                return None
            self.redo_stack.append(self._snapshot())
            self._restore(self.undo_stack.pop())
            print(f" -> Undo OK  (undo: {len(self.undo_stack)}, redo: {len(self.redo_stack)})")
            return "modified"

        elif action == "redo":
            if not self.redo_stack:
                print("Nothing to redo.")
                return None
            self.undo_stack.append(self._snapshot())
            self._restore(self.redo_stack.pop())
            print(f" -> Redo OK  (undo: {len(self.undo_stack)}, redo: {len(self.redo_stack)})")
            return "modified"

        elif action == "project":
            if len(cmd) < 3:
                print("Usage: project <n> <full_path>")
                return None
            proj_name = cmd[1]
            base_dir  = os.path.normpath(cmd[2])
            proj_dir  = os.path.join(base_dir, proj_name)
            os.makedirs(proj_dir, exist_ok=True)
            model_path   = os.path.join(proj_dir, f"{proj_name}.mf")
            results_path = os.path.join(proj_dir, f"{proj_name}_results.json")

            if self.model is None:
                self.model = StructuralModel(proj_name)

            model = self.model
            model.name                = proj_name
            model.active_project_dir  = proj_dir
            model.active_model_path   = model_path
            model.active_results_path = results_path
            model.file_path           = model_path
            model.save_to_file(model_path)
            print(f" -> Project '{proj_name}' ready at: {proj_dir}")
            return "opened"

        elif action == "open":
            if len(cmd) < 2:
                print("Usage: open <path/to/file.mf>")
                return None
            filepath = os.path.normpath(cmd[1])
            if not os.path.exists(filepath):
                print(f"Error: File not found: {filepath}")
                return None
            new_model = StructuralModel("Loaded Project")
            new_model.load_from_file(filepath)
            self.model = new_model
            self.undo_stack.clear()
            self.redo_stack.clear()
            proj_dir  = os.path.dirname(os.path.abspath(filepath))
            proj_name = os.path.splitext(os.path.basename(filepath))[0]
            self.model.active_project_dir  = proj_dir
            self.model.active_model_path   = filepath
            self.model.active_results_path = os.path.join(proj_dir, f"{proj_name}_results.json")
            self.model.file_path           = filepath               
            print(f" -> Loaded '{self.model.name}' | Nodes: {len(self.model.nodes)}, "
                f"Elements: {len(self.model.elements)}, Loads: {len(self.model.loads)}")
            return "opened"

        elif action == "save":
            path = getattr(self.model, 'active_model_path', None) or getattr(self.model, 'file_path', None)
            if not path:
                print("Error: No active project. Run 'project <n>' or open a file first.")
                return None
            model.save_to_file(path)
                                     
            self.model.active_model_path = path
            self.model.file_path         = path
            print(f" -> Saved to: {path}")
            return "saved"

        elif action == "solve":
            if len(cmd) < 2:
                                                                     
                if hasattr(model, 'load_cases') and model.load_cases:
                    print("Available load cases:")
                    for name, case in model.load_cases.items():
                        c_type = getattr(case, 'case_type', getattr(case, 'type', '?'))
                        print(f"  - {name}  ({c_type})")
                    print("Usage: solve <case_name>   e.g.  solve DEAD")
                else:
                    print("No load cases defined. Add one via Define > Load Cases.")
                return None
            case_name = cmd[1]
            if hasattr(model, 'load_cases'):
                                                      
                match = next((k for k in model.load_cases if k.lower() == case_name.lower()), None)
                if not match:
                    print(f"Error: Load case '{case_name}' not found. Type 'solve' to list available cases.")
                    return None
                case_name = match                                             
            print(f" -> Requesting analysis for load case: {case_name}")
            return f"solve:{case_name}"

        elif action == "list":
            if not hasattr(model, 'active_project_dir'):
                print("Error: No active project found. Run 'project <n>' first.")
                return None
            print(f"--- PROJECT FILES: {model.active_project_dir} ---")
            files = os.listdir(model.active_project_dir)
            if not files:
                print("  (Folder is empty)")
            for f in files:
                size = os.path.getsize(os.path.join(model.active_project_dir, f))
                print(f"  - {f} ({size / 1024:.2f} KB)")
            return None

        elif action == "mat":
            name, E, nu, rho, mat_type = cmd[1], float(cmd[2]), float(cmd[3]), float(cmd[4]), cmd[5]
            self._push_undo()
            model.add_material(Material(name, E=E, nu=nu, density=rho, mat_type=mat_type))
            print(f" -> Added Material: {name}")
            return "modified"

        elif action == "del_mat":
            if len(cmd) < 2:
                print("Usage: del_mat <n>")
                return None
            mname = cmd[1]
            if mname not in model.materials:
                print(f"Error: Material '{mname}' does not exist.")
                return None
            in_use = [s.name for s in model.sections.values() if s.material.name == mname]
            if in_use:
                print(f"Error: Material '{mname}' is used by sections: {in_use}. Delete those first.")
                return None
            self._push_undo()
            del model.materials[mname]
            print(f" -> Deleted Material '{mname}'")
            return "modified"

        elif action == "mod_mat":
            if len(cmd) < 3:
                print("Usage: mod_mat <n> <prop=val> [prop=val ...]")
                return None
            mname = cmd[1]
            if mname not in model.materials:
                print(f"Error: Material '{mname}' does not exist.")
                return None
            self._push_undo()
            mat = model.materials[mname]
            changed = []
            for token in cmd[2:]:
                prop, val = token.split("=")
                prop = prop.lower()
                if   prop == "e":    mat.E        = float(val)
                elif prop == "nu":   mat.nu       = float(val)
                elif prop == "rho":  mat.density  = float(val)
                elif prop == "fy":   mat.fy       = float(val)
                elif prop == "fu":   mat.fu       = float(val)
                elif prop == "type": mat.mat_type = val
                else:
                    print(f"  Unknown prop '{prop}'. Valid: E nu rho fy fu type")
                    continue
                changed.append(f"{prop}={val}")
            if changed:
                print(f" -> Material '{mname}' updated: {', '.join(changed)}")
            return "modified" if changed else None

        elif action == "sec":
            name, mat_name, sec_type = cmd[1], cmd[2], cmd[3].lower()
            mat = model.materials[mat_name]
            self._push_undo()
            if sec_type == "rect":
                b, h = float(cmd[4]), float(cmd[5])
                model.add_section(RectangularSection(name, mat, b=b, h=h))
            elif sec_type == "circ":
                model.add_section(CircularSection(name, mat, d=float(cmd[4])))
            elif sec_type == "pipe":
                d, t = float(cmd[4]), float(cmd[5])
                model.add_section(PipeSection(name, mat, d=d, t=t))
            elif sec_type == "tube":
                d, b, tf, tw = float(cmd[4]), float(cmd[5]), float(cmd[6]), float(cmd[7])
                model.add_section(TubeSection(name, mat, d=d, b=b, tf=tf, tw=tw))
            elif sec_type == "i_sec":
                h, w_t, t_t, w_b, t_b, t_w = map(float, cmd[4:10])
                model.add_section(ISection(name, mat, h, w_t, t_t, w_b, t_b, t_w))
            elif sec_type == "trap":
                d, w_top, w_bot = float(cmd[4]), float(cmd[5]), float(cmd[6])
                model.add_section(TrapezoidalSection(name, mat, d=d, w_top=w_top, w_bot=w_bot))
            elif sec_type == "gen":
                A, J, I33, I22, Asy, Asz = map(float, cmd[4:10])
                model.add_section(GeneralSection(name, mat, {'A': A, 'J': J, 'I33': I33,
                                                              'I22': I22, 'Asy': Asy, 'Asz': Asz}))
            else:
                print(f"Unknown section type '{sec_type}'. Check 'help'.")
                return None
            print(f" -> Added {sec_type.upper()} Section: {name}")
            return "modified"

        elif action == "del_sec":
            if len(cmd) < 2:
                print("Usage: del_sec <n>")
                return None
            sname = cmd[1]
            if sname not in model.sections:
                print(f"Error: Section '{sname}' does not exist.")
                return None
            in_use = [str(eid) for eid, el in model.elements.items() if el.section.name == sname]
            if in_use:
                print(f"Error: Section '{sname}' is used by frames: {in_use}. Delete those first.")
                return None
            self._push_undo()
            del model.sections[sname]
            print(f" -> Deleted Section '{sname}'")
            return "modified"

        elif action == "grid":
            if len(cmd) < 4:
                print("Usage: grid <x|y|z> <ord1> <ord2> ...   e.g. grid x 0 5 10 15")
                return None
            axis = cmd[1].lower()
            if axis not in ('x', 'y', 'z'):
                print("Error: axis must be x, y, or z.")
                return None
            try:
                ordinates = sorted([float(v) for v in cmd[2:]])
            except ValueError:
                print("Error: all ordinate values must be numbers.")
                return None
            if len(ordinates) < 2:
                print("Error: need at least 2 grid lines per axis.")
                return None

            def _make_ids(n, ax):
                if ax == 'x':
                    ids = []
                    for i in range(n):
                        if i < 26: ids.append(chr(65 + i))
                        else:       ids.append(chr(64 + i // 26) + chr(65 + i % 26))
                    return ids
                elif ax == 'y':
                    return [str(i + 1) for i in range(n)]
                else:
                    return [f"Z{i + 1}" for i in range(n)]

            ids   = _make_ids(len(ordinates), axis)
            lines = [{'id': ids[i], 'ord': ordinates[i], 'visible': True, 'bubble': 'End'}
                     for i in range(len(ordinates))]

            self._push_undo()
            if   axis == 'x': model.grid.x_lines = lines
            elif axis == 'y': model.grid.y_lines = lines
            else:             model.grid.z_lines = lines

            summary = ', '.join(f"{l['id']}={l['ord']}" for l in lines)
            print(f" -> Grid {axis.upper()} set: {summary}")
            print("--- CURRENT GRID ---")
            for ax, attr in (('X', 'x_lines'), ('Y', 'y_lines'), ('Z', 'z_lines')):
                ls = getattr(model.grid, attr)
                print(f"  {ax}: " + (', '.join(f"{l['id']}={l['ord']}" for l in ls) if ls else "(not defined)"))
            return "modified"

        elif action == "frame":
            if len(cmd) < 4:
                print("Usage: frame <pt1> <pt2> <sec_name>   e.g. frame A,1,Z1 A,1,Z2 COL")
                return None
            x1, y1, z1 = self._resolve_grid_point(cmd[1])
            x2, y2, z2 = self._resolve_grid_point(cmd[2])
            sec = model.sections.get(cmd[3])
            if sec is None:
                print(f"Error: Section '{cmd[3]}' not found. Run 'view secs' to list defined sections.")
                return None
            self._push_undo()
            n1 = model.get_or_create_node(x1, y1, z1)
            n2 = model.get_or_create_node(x2, y2, z2)
            el = model.add_element(n1, n2, sec)
            print(f" -> Added Frame {el.id} | {cmd[1]} (N{n1.id}) → {cmd[2]} (N{n2.id}) | Sec: {sec.name}")
            return "modified"

        elif action == "del_frame":
            if len(cmd) < 2:
                print("Usage: del_frame <frame_id>")
                return None
            eid = int(cmd[1])
            if eid not in model.elements:
                print(f"Error: Frame {eid} does not exist.")
                return None
            self._push_undo()
            model.remove_element(eid)
            print(f" -> Deleted Frame {eid} (orphan nodes auto-cleaned)")
            return "modified"

        elif action == "del_node":
            print("Error: nodes are managed automatically. Delete the connected frames instead.")
            return None

        elif action == "mod_frame":
            eid  = int(cmd[1])
            prop = cmd[2].lower()
            val  = float(cmd[3])
            el   = model.elements[eid]
            self._push_undo()
            if   prop == "cardinal":  el.cardinal_point = int(val)
            elif prop == "offset_i":  el.end_offset_i   = val
            elif prop == "offset_j":  el.end_offset_j   = val
            elif prop == "beta":      el.beta_angle      = val
            else:
                print("Unknown property. Use: cardinal, offset_i, offset_j, beta")
                return None
            print(f" -> Frame {eid} modified: {prop} = {val}")
            return "modified"

        elif action == "release":
            eid  = int(cmd[1])
            end  = cmd[2].lower()
            rels = [bool(int(x)) for x in cmd[3:9]]
            self._push_undo()
            if end == 'i':   model.elements[eid].releases_i = rels
            elif end == 'j': model.elements[eid].releases_j = rels
            print(f" -> Beam {eid} end '{end}' releases set to {rels}")
            return "modified"

        elif action == "support":
            if len(cmd) < 8:
                print("Usage: support <pt> <Ux> <Uy> <Uz> <Rx> <Ry> <Rz>   e.g. support A,1,Z1 1 1 1 1 1 1")
                return None
            node       = self._resolve_existing_node(cmd[1])
            restraints = [bool(int(x)) for x in cmd[2:8]]
            self._push_undo()
            node.restraints = restraints
            print(f" -> Node {node.id} at {cmd[1]} supports set to {restraints}")
            return "modified"

        elif action == "pattern":
            name, p_type, sw_mult = cmd[1], cmd[2], float(cmd[3])
            self._push_undo()
            model.add_load_pattern(name, p_type, sw_mult)
            print(f" -> Added Load Pattern: {name} (SW Multiplier: {sw_mult})")
            return "modified"

        elif action == "load":
            node    = self._resolve_existing_node(cmd[1])
            pattern = cmd[2]
            dof = {"fx": 0.0, "fy": 0.0, "fz": 0.0, "mx": 0.0, "my": 0.0, "mz": 0.0}
            for token in cmd[3:]:
                key, val = token.split("=")
                if key.lower() not in dof:
                    raise ValueError(f"Unknown DOF '{key}'. Use fx fy fz mx my mz.")
                dof[key.lower()] = float(val)
            self._push_undo()
            model.assign_joint_load(node.id, pattern, **dof)
            applied = ", ".join(f"{k}={v}" for k, v in dof.items() if v != 0.0)
            print(f" -> Nodal load on {cmd[1]} (N{node.id}) [{pattern}]: {applied or '(zero)'}")
            return "modified"

        elif action == "dist_load":
            eid, pat = int(cmd[1]), cmd[2]
            wx, wy, wz = float(cmd[3]), float(cmd[4]), float(cmd[5])
            coord = cmd[6] if len(cmd) > 6 else "Global"
            self._push_undo()
            model.assign_member_load(eid, pat, wx, wy, wz, coord_system=coord)
            print(f" -> Dist load on Beam {eid} [{pat}]: wx={wx}, wy={wy}, wz={wz} ({coord})")
            return "modified"

        elif action == "point_load":
            eid, pat, force, dist, dir_str = int(cmd[1]), cmd[2], float(cmd[3]), float(cmd[4]), cmd[5]
            self._push_undo()
            model.assign_member_point_load(eid, pat, force, dist, True, "Global", dir_str, "Force")
            print(f" -> Added {force}kN point load on Beam {eid} at relative dist {dist}")
            return "modified"

        elif action == "view":
            if len(cmd) < 2:
                print("Usage: view <mats|secs|nodes|beams|patterns|loads>")
                return None
            category = cmd[1].lower()
            if category == "grid":
                g = model.grid
                def _show(label, lines):
                    print(f"  {label}: " + (", ".join(f"{l['id']}={l['ord']}" for l in lines) if lines else "(not defined)"))
                print("--- GRID ---")
                _show("X", g.x_lines)
                _show("Y", g.y_lines)
                _show("Z", g.z_lines)
            elif category == "mats":
                print(f"--- MATERIALS ({len(model.materials)}) ---")
                for name, mat in model.materials.items():
                    print(f"  - {name} | E={mat.E:.2e}, nu={mat.nu}, rho={mat.density}, type={mat.mat_type}")
            elif category == "secs":
                print(f"--- SECTIONS ({len(model.sections)}) ---")
                for name, sec in model.sections.items():
                    print(f"  - {name} ({sec.material.name}) | A={sec.A:.6f}, I33={sec.I33:.6f}, I22={sec.I22:.6f}")
            elif category == "beams":
                print(f"--- FRAMES ({len(model.elements)}) ---")
                for eid, el in model.elements.items():
                    print(f"  - Beam {eid}: N{el.node_i.id} -> N{el.node_j.id} | "
                          f"Sec: {el.section.name} | Beta: {el.beta_angle}°")
            elif category == "patterns":
                print(f"--- LOAD PATTERNS ({len(model.load_patterns)}) ---")
                for name, pat in model.load_patterns.items():
                    print(f"  - {name}: Type={pat.pattern_type}, SW={pat.self_weight_multiplier}")
            elif category == "loads":
                print(f"--- APPLIED LOADS ({len(model.loads)}) ---")
                for load in model.loads:
                    if hasattr(load, 'node_id'):
                        parts = [f"{d}={getattr(load, d)}" for d in
                                 ("fx","fy","fz","mx","my","mz") if getattr(load, d) != 0.0]
                        print(f"  - Nodal   | Node {load.node_id} [{load.pattern_name}]: "
                              f"{' '.join(parts) or '(zero)'}")
                    elif hasattr(load, 'wx'):
                        print(f"  - Dist    | Beam {load.element_id} [{load.pattern_name}]: "
                              f"wy={load.wy}, wz={load.wz} ({load.coord_system})")
                    elif hasattr(load, 'force'):
                        print(f"  - Point   | Beam {load.element_id} [{load.pattern_name}]: "
                              f"F={load.force} at dist={load.dist}")
            else:
                print("Unknown category. Try: grid, mats, secs, beams, patterns, loads")
            return None

        else:
            print(f"Unknown command: '{action}'. Type 'help'.")
            return None

def start_terminal():
    print("="*65)
    print(" OpenCivil v0.7 Terminal")
    print(" Type 'help' to see commands or 'exit' to quit.")
    print("="*65)

    model = StructuralModel(name="CLI_Parametric_Model")

    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path) and file_path.endswith('.mf'):
            try:
                model.load_from_file(file_path)
                print(f"\n✅ Successfully loaded model from terminal: {file_path}")
            except Exception as e:
                print(f"\n❌ Error loading file: {e}")
        else:
            print(f"\n⚠️ Could not find or read file: {file_path}")

    dispatcher = CLIDispatcher(model)

    while True:
        try:
            raw = input("\nOC> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nClosing terminal.")
            break
        result = dispatcher.dispatch(raw)
        if result == "exit":
            break
        elif result == "clear":
            os.system('cls' if os.name == 'nt' else 'clear')
            print("="*65)
            print(" OpenCivil v0.7 Terminal - Screen Cleared")
            print("="*65)

if __name__ == "__main__":
    start_terminal()
