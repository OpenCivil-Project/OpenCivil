import numpy as np
import pyqtgraph.opengl as gl
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QTimer
from PyQt6.QtGui import QPainter, QColor, QPen, QVector3D
from core.units import unit_registry
from graphic.camera_ctrl import ArcballCamera
from post.deflection import get_deflected_shape
from post.animation import AnimationManager
from graphic.view_cube import ViewCube
from OpenGL.GL import *
class MCanvas3D(gl.GLViewWidget):
    signal_canvas_clicked = pyqtSignal(float, float, float)
    signal_right_clicked = pyqtSignal()
    signal_box_selection = pyqtSignal(list, list, bool)
    signal_element_selected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)

        self.display_config = {
            "node_size": 6,
            "node_color": (1, 1, 0, 1),
            "line_width": 2.0,
            "extrude_opacity": 0.35,
            "show_edges": False,
            "edge_width": 1.5,
            "edge_color": (0, 0, 0, 1),
            "slab_opacity": 0.4
        }
        self.view_cube = ViewCube()
        self.opts['distance'] = 40
        self.opts['elevation'] = 30
        self.opts['azimuth'] = 45
        self.opts['fov'] = 60                              
        self.setBackgroundColor('#FFFFFF')

        self.current_model = None
        self.selected_element_ids = [] 
        self.selected_node_ids = [] 
        self.view_extruded = False
        self.snapping_enabled = False
        self.load_labels = []
        self.view_extruded = False 
        self.show_joints = True      
        self.show_supports = True    
        self.show_releases = True   
        self.show_loads = True
        self.load_type_filter = "both"
        self.visible_load_patterns = []
        self.show_local_axes = False
        self.show_slabs = True
        self.show_constraints = True
        self.camera = ArcballCamera(self)
        self.view_deflected = False    
        self.deflection_scale = 50.0
        self.view_shadow = True
        self.shadow_color = (0.7, 0.7, 0.7, 0.5)

        self.deflection_cache = {}
        self.cache_valid = False
        self.cache_scale_used = None  
        self.anim_factor = 1.0 
        self.animation_manager = AnimationManager(self)
        self.animation_manager.signal_frame_update.connect(self._on_anim_frame)
        
        self.prerendered_geometry_frames = []                                 
        self.is_animation_cached = False                                           
        self.current_animation_frame = 0                                            
        
        self.animation_manager.canvas = self

        self.static_items = []      
        self.node_items = []         
        self.element_items = []      
        self.last_selection_state = {'nodes': [], 'elements': [], 'blink': True}

        self.active_view_plane = None 

        self.drag_start = None
        self.drag_current = None
        self.is_selecting = False

        self.blink_state = True
                                    
        self.pivot_dot = gl.GLScatterPlotItem(pos=np.array([[0,0,0]]), size=12, 
                                              color=(1, 1, 0, 0.8), pxMode=True)
        self.pivot_dot.setGLOptions('translucent')
        self.pivot_dot.setVisible(False)
        self.addItem(self.pivot_dot)
        
        self.pivot_timer = QTimer()
        self.pivot_timer.setSingleShot(True)
        self.pivot_timer.timeout.connect(lambda: self.pivot_dot.setVisible(False))

        self.snap_ring = gl.GLLinePlotItem(pos=np.array([[0,0,0]]), mode='line_strip', 
                                           color=(1, 0, 0, 1), width=3, antialias=True)
        self.snap_ring.setGLOptions('translucent')
        self.addItem(self.snap_ring)
        
        self.snap_dot = gl.GLScatterPlotItem(pos=np.array([[0,0,0]]), size=10, 
                                             color=(1, 0, 0, 1), pxMode=True)
        self.snap_dot.setGLOptions('translucent')
        self.addItem(self.snap_dot)
        
        self.snap_ring.setVisible(False)
        self.snap_dot.setVisible(False)

    def _line_intersects_rect(self, p1, p2, rect):
        """
        Robust Line Segment vs Rectangle Intersection.
        rect = (x_min, y_min, x_max, y_max)
        """
        x_min, y_min, x_max, y_max = rect
        
        if min(p1[0], p2[0]) > x_max or max(p1[0], p2[0]) < x_min: return False
        if min(p1[1], p2[1]) > y_max or max(p1[1], p2[1]) < y_min: return False
        
        if x_min <= p1[0] <= x_max and y_min <= p1[1] <= y_max: return True
        if x_min <= p2[0] <= x_max and y_min <= p2[1] <= y_max: return True
        
        def ccw(A, B, C):
            return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])

        def intersect(A, B, C, D):
            return ccw(A,C,D) != ccw(B,C,D) and ccw(A,B,C) != ccw(A,B,D)

        bl = (x_min, y_min); br = (x_max, y_min)
        tr = (x_max, y_max); tl = (x_min, y_max)
        
        if intersect(p1, p2, bl, br): return True         
        if intersect(p1, p2, br, tr): return True        
        if intersect(p1, p2, tr, tl): return True      
        if intersect(p1, p2, tl, bl): return True       
        
        return False

    def set_standard_view(self, view_name):
                                              
        mid_x, mid_y, mid_z = 0, 0, 0
        max_dim = 40
        if self.current_model and self.current_model.grid:
                                                            
            gx = self.current_model.grid.x_grids
            gy = self.current_model.grid.y_grids
            gz = self.current_model.grid.z_grids
            if gx and gy and gz:
                mid_x = (min(gx) + max(gx)) / 2
                mid_y = (min(gy) + max(gy)) / 2
                mid_z = (min(gz) + max(gz)) / 2
                max_dim = max(max(gx)-min(gx), max(gy)-min(gy), max(gz)-min(gz)) * 1.5

        target_center = QVector3D(mid_x, mid_y, mid_z)
        target_dist = max_dim
        
        t_az, t_el, t_fov = -45, 30, 60
        
        if view_name == "ISO": t_az, t_el, t_fov = -135, 30, 0; target_dist = max_dim * 4.0
        elif view_name == "3D": t_az, t_el, t_fov = -135, 30, 60
        elif view_name == "XY": t_az, t_el, t_fov = -90, 90, 0; target_dist = max_dim * 1.5
        elif view_name == "XZ": t_az, t_el, t_fov = -90, 0, 0; target_dist = max_dim * 1.5
        elif view_name == "YZ": t_az, t_el, t_fov = 180, 0, 0; target_dist = max_dim * 1.5

        self.opts['fov'] = t_fov
        self.camera.animate_to(target_center, target_dist, t_az, t_el)

    def draw_model(self, model, sel_elems=None, sel_nodes=None):
        """
        Draws the model on the canvas.
        
        IMPORTANT: If animation is running, this method will:
        - Update selection state silently
        - NOT redraw (to prevent interrupting smooth animation)
        
        To force redraw during animation, call _force_draw_model() instead.
        """
                                             
        self.current_model = model
        if sel_elems is not None: 
            self.selected_element_ids = sel_elems
        if sel_nodes is not None: 
            self.selected_node_ids = sel_nodes
        
        if self.animation_manager.is_running:
                                                                             
            return                                               
        
        self._force_draw_model(model, sel_elems, sel_nodes)
    
    def _force_draw_model(self, model, sel_elems=None, sel_nodes=None):
        """
        Force redraw the model even if animation is running.
        Used internally by draw_model when animation is stopped.
        """
        self.current_model = model
        if sel_elems is not None: self.selected_element_ids = sel_elems
        if sel_nodes is not None: self.selected_node_ids = sel_nodes
        self.load_labels = []

        self.node_items.clear()     
        self.element_items.clear()

        self.invalidate_deflection_cache()

        for item in self.items[:]:
            self.removeItem(item)

        self._draw_reference_grids(model)

        if self.show_joints or self.show_supports:
            self._draw_nodes(model)
        
        if self.show_constraints:  
            self._draw_constraints(model)
                                                  
        if self.view_extruded:
            self._draw_elements_extruded(model)
        else:
                              
            self._draw_elements_wireframe(model) 
            
        if self.show_loads:
            self._draw_loads(model)                      
            self._draw_member_loads(model)                             
            self._draw_member_point_loads(model)

        if self.show_slabs:
            self._draw_slabs(model)

        if self.show_local_axes:
            self._draw_local_axes(model)

        if self.snap_ring not in self.items: self.addItem(self.snap_ring)
        if self.snap_dot not in self.items: self.addItem(self.snap_dot)
             
        self.snap_ring.setGLOptions('translucent')
        self.snap_dot.setGLOptions('translucent')

    def _draw_nodes(self, model):
        if not model.nodes: return
        
        pos_free = []
        sel_pos = []
        ghost_pos = []
        supports_fixed = []; supports_pinned = []; supports_roller = []

        size = self.display_config.get("node_size", 6)
        color_tuple = self.display_config.get("node_color", (1, 1, 0, 1))
                              
        for nid, n in model.nodes.items():
            xyz = [n.x, n.y, n.z]
            v_state = self._get_visibility_state(n.x, n.y, n.z)                
    
            if v_state == 1:             
                ghost_pos.append(xyz)
                continue                                      

            is_active = self._is_visible(n.x, n.y, n.z)
            if not is_active:
                ghost_pos.append(xyz)
                continue

            is_sel = (nid in self.selected_node_ids)
            if is_sel:
                sel_pos.append(xyz)
            
            r = n.restraints
            is_fixed = all(r[:3]) and all(r[3:]) 
            is_pinned = all(r[:3]) and not any(r[3:]) 
            has_any = any(r)

            if has_any and self.show_supports:
                if is_fixed: supports_fixed.append(xyz)
                elif is_pinned: supports_pinned.append(xyz)
                else: supports_roller.append(xyz)
            elif self.show_joints and not is_sel:
                 pos_free.append(xyz)

        if pos_free: 
            item = gl.GLScatterPlotItem(
                pos=np.array(pos_free), 
                size=size,                           
                color=color_tuple,                   
                pxMode=True)
            self.addItem(item)
            self.node_items.append(item)
        
        if sel_pos: 
                                                                                 
            sp = gl.GLScatterPlotItem(
                pos=np.array(sel_pos), size=size+2, color=(1, 0, 0, 1), pxMode=True)
            sp.setGLOptions('opaque')
            self.addItem(sp)
            self.node_items.append(sp)

        if supports_fixed: self._draw_support_meshes(supports_fixed, 'fixed')
        if supports_pinned: self._draw_support_meshes(supports_pinned, 'pinned')
        if supports_roller: self._draw_support_meshes(supports_roller, 'roller')
        
        if ghost_pos and self.show_joints:
            item = gl.GLScatterPlotItem(
                pos=np.array(ghost_pos), size=4, color=(0.7, 0.7, 0.7, 0.4), pxMode=True
            )
            self.addItem(item)
            self.node_items.append(item)

    def _is_visible(self, x, y, z):
        """
        Helper compatibility method. 
        Returns True if the object is visible (either Active OR Ghost).
        This ensures loads and nodes in the background are not skipped.
        """
                                                                    
        if not hasattr(self, 'active_view_plane'): return True
        
        state = self._get_visibility_state(x, y, z)
        return state >= 1                                                    
    
    def _draw_elements_wireframe(self, model):
        if not model.elements: return

        flex_pos = []; flex_colors = []
        rigid_pos = []; rigid_colors = []
        rigid_black = (0, 0, 0, 1)
        
        curved_pos = []; curved_colors = []
        
        release_dots = []

        ghost_pos = []
        sel_color = np.array([1.0, 0.0, 0.0, 1.0]) 
        def_color = np.array([0.5, 0.5, 0.5, 1.0]) 
        width = self.display_config.get("line_width", 2.0)

        can_deflect = (self.view_deflected and 
                       hasattr(model, 'has_results') and 
                       model.has_results and 
                       model.results is not None)

        for eid, el in model.elements.items():
            n1, n2 = el.node_i, el.node_j
            v1 = self._get_visibility_state(n1.x, n1.y, n1.z)
            v2 = self._get_visibility_state(n2.x, n2.y, n2.z)

            if v1 == 1 and v2 == 1:
                ghost_pos.extend([np.array([n1.x, n1.y, n1.z]), np.array([n2.x, n2.y, n2.z])])
                continue
            p1 = np.array([n1.x, n1.y, n1.z])
            p2 = np.array([n2.x, n2.y, n2.z])
                             
            if eid in self.selected_element_ids:
                c = sel_color
            else:
                c = getattr(el.section, 'color', def_color)
                if len(c) == 3: c = (*c, 1.0)
                c = np.array(c)

            drawn_as_curve = False
            
            if can_deflect:
                res_i = model.results.get("displacements", {}).get(str(n1.id))
                res_j = model.results.get("displacements", {}).get(str(n2.id))
                
                if res_i and res_j:
                                                         
                    cache_key = eid
                    
                    if self.cache_scale_used != self.deflection_scale:
                        self.invalidate_deflection_cache()
                        self.deflection_cache.clear()
                        self.cache_scale_used = self.deflection_scale
                    
                    if cache_key not in self.deflection_cache:
                        v1, v2, v3 = self._get_consistent_axes(el)
                        
                        curve_data = get_deflected_shape(
                            [n1.x, n1.y, n1.z], 
                            [n2.x, n2.y, n2.z], 
                            res_i, res_j, 
                            v1, v2, v3, 
                            scale=self.deflection_scale,                            
                            num_points=11
                        )
                        
                        self.deflection_cache[cache_key] = {
                            'curve_data': curve_data,
                            'p1_orig': p1.copy(),
                            'p2_orig': p2.copy()
                        }
                    
                    cached = self.deflection_cache[cache_key]
                    curve_data_full = cached['curve_data']
                    p1_orig = cached['p1_orig']
                    
                    for k in range(len(curve_data_full) - 1):
                        pos_full, _, _ = curve_data_full[k]
                        pos_full_next, _, _ = curve_data_full[k+1]
                        
                        s = k / (len(curve_data_full) - 1)                         
                        pos_orig = p1 + s * (p2 - p1)
                        
                        displacement = pos_full - pos_orig
                        p_start = pos_orig + displacement * self.anim_factor
                        
                        s_next = (k + 1) / (len(curve_data_full) - 1)
                        pos_orig_next = p1 + s_next * (p2 - p1)
                        displacement_next = pos_full_next - pos_orig_next
                        p_end = pos_orig_next + displacement_next * self.anim_factor
                        
                        curved_pos.append(p_start)
                        curved_pos.append(p_end)
                        curved_colors.append(c)
                        curved_colors.append(c)
                    
                    drawn_as_curve = True
                                                         
                    if self.view_shadow:
                        dist = np.linalg.norm(p2 - p1)
                        dash_len = 0.5
                        if dist > 0:
                            num_dashes = int(dist / dash_len)
                            vec = (p2 - p1) / dist
                            for d in range(0, num_dashes, 2):
                                d_start = p1 + (vec * d * dash_len)
                                d_end   = p1 + (vec * (d + 1) * dash_len)
                                if np.linalg.norm(d_end - p1) > dist: d_end = p2
                                
                                ghost_pos.append(d_start)
                                ghost_pos.append(d_end)

            if not drawn_as_curve:
                off_i = getattr(el, 'end_offset_i', 0.0)
                off_j = getattr(el, 'end_offset_j', 0.0)
                
                vec = p2 - p1
                length = np.linalg.norm(vec)
                p1_flex = p1; p2_flex = p2
                
                if length > 0.001 and (off_i > 0 or off_j > 0):
                    u = vec / length
                    if off_i + off_j >= length:
                        scale = (length / (off_i + off_j)) * 0.99
                        p1_flex = p1 + (u * off_i * scale)
                        p2_flex = p2 - (u * off_j * scale)
                    else:
                        p1_flex = p1 + (u * off_i)
                        p2_flex = p2 - (u * off_j)

                    if off_i > 0:
                        rigid_pos.extend([p1, p1_flex])
                        rigid_colors.extend([rigid_black, rigid_black])
                    if off_j > 0:
                        rigid_pos.extend([p2_flex, p2])
                        rigid_colors.extend([rigid_black, rigid_black])
                
                flex_pos.extend([p1_flex, p2_flex])
                flex_colors.extend([c, c])

                if self.show_releases:
                    flex_vec = p2_flex - p1_flex
                    flex_len = np.linalg.norm(flex_vec)
                    if flex_len > 0:
                                                                         
                        offset_vec = (flex_vec / flex_len) * 0.15
                        
                        if hasattr(el, 'releases_i') and (el.releases_i[4] or el.releases_i[5]):
                            release_dots.append(p1_flex + offset_vec)
                        
                        if hasattr(el, 'releases_j') and (el.releases_j[4] or el.releases_j[5]):
                            release_dots.append(p2_flex - offset_vec)
                                                     
        if flex_pos:
            item = gl.GLLinePlotItem(
                pos=np.array(flex_pos), color=np.array(flex_colors), 
                mode='lines', width=width, antialias=True
            )
            self.addItem(item)
            self.element_items.append(item)
            
        if rigid_pos:
             item = gl.GLLinePlotItem(
                 pos=np.array(rigid_pos), color=np.array(rigid_colors), 
                 mode='lines', width=width+2, antialias=True
             )
             self.addItem(item)
             self.element_items.append(item)
            
        if curved_pos:
            item = gl.GLLinePlotItem(
                pos=np.array(curved_pos), color=np.array(curved_colors), 
                mode='lines', width=3.0, antialias=True                          
            )
            self.addItem(item)
            self.element_items.append(item)
            
        if release_dots:
            dot_item = gl.GLScatterPlotItem(
                pos=np.array(release_dots), 
                size=0.25,                                      
                color=(0, 1, 0, 1),          
                pxMode=False
            )
            dot_item.setGLOptions('opaque')
            self.addItem(dot_item)
            self.element_items.append(dot_item)
            
        if ghost_pos:
            c = self.shadow_color
            ghost_item = gl.GLLinePlotItem(
                pos=np.array(ghost_pos), 
                color=c, 
                mode='lines', width=2.0, antialias=True
            )
            ghost_item.setGLOptions('translucent')
            self.addItem(ghost_item)
            self.element_items.append(ghost_item)

    def _draw_elements_extruded(self, model):
        if not model.elements: return

        self.ex_vertices = []
        self.ex_faces = []
        self.ex_colors = []
        self.ex_edges = []
        self.ex_edge_colors = []
        
        center_lines = []
        center_colors = []
        color_edge_select = np.array([1.0, 1.0, 0.0, 1.0])                
        
        opacity = self.display_config.get("extrude_opacity", 0.35)
        show_edges = self.display_config.get("show_edges", False)
        edge_c = np.array(self.display_config.get("edge_color", (0, 0, 0, 1)))
        edge_width = self.display_config.get("edge_width", 1.0)
        
        can_deflect = (self.view_deflected and 
                       hasattr(model, 'has_results') and 
                       model.has_results and 
                       model.results is not None)

        for eid, el in model.elements.items():
            n1, n2 = el.node_i, el.node_j
            
            v1 = self._get_visibility_state(n1.x, n1.y, n1.z)
            v2 = self._get_visibility_state(n2.x, n2.y, n2.z)

            if v1 == 0 or v2 == 0: continue

            is_active_elem = (v1 == 2 and v2 == 2)

            is_active_elem = (v1 == 2 and v2 == 2)

            sec = el.section
            shape_yz = sec.get_shape_coords()
            if not shape_yz: continue 
                             
            if not is_active_elem:
                                                          
                face_color = np.array([0.6, 0.6, 0.6, 0.3]) 
                current_edge_color = np.array([0.6, 0.6, 0.6, 0.1])
            else:
                                            
                c_raw = getattr(sec, 'color', [0.7, 0.7, 0.7])
                if len(c_raw) == 4: c_raw = c_raw[:3]
                face_color = np.array([c_raw[0], c_raw[1], c_raw[2], opacity])
                current_edge_color = edge_c

            path_points = [] 
            
            p1 = np.array([n1.x, n1.y, n1.z])
            p2 = np.array([n2.x, n2.y, n2.z])
            
            if can_deflect:
                res_i = model.results.get("displacements", {}).get(str(n1.id))
                res_j = model.results.get("displacements", {}).get(str(n2.id))
                
                if res_i and res_j:
                    v1_orig, v2_orig, v3_orig = self._get_consistent_axes(el)
                    eff_scale = self.deflection_scale * self.anim_factor

                    curve_data = get_deflected_shape(
                        [n1.x, n1.y, n1.z], [n2.x, n2.y, n2.z],
                        res_i, res_j,
                        v1_orig, v2_orig, v3_orig,
                        scale=eff_scale,
                        num_points=11
                    )
                    
                    for k in range(len(curve_data)):
                        pos, tan_vec, twist = curve_data[k]
                        
                        v1_curr = tan_vec 

                        c_t = np.cos(twist); s_t = np.sin(twist)
                        v2_twisted = (c_t * v2_orig) + (s_t * v3_orig)
                        
                        proj = np.dot(v2_twisted, v1_curr) * v1_curr
                        v2_curr = v2_twisted - proj
                        n2_len = np.linalg.norm(v2_curr)
                        if n2_len > 1e-6: v2_curr /= n2_len
                        else: v2_curr = v2_orig 
                            
                        v3_curr = np.cross(v1_curr, v2_curr)
                        path_points.append( (pos, v2_curr, v3_curr) )

            if not path_points:
                                            
                off_i = getattr(el, 'end_offset_i', 0.0)
                off_j = getattr(el, 'end_offset_j', 0.0)
                
                vec = p2 - p1
                length = np.linalg.norm(vec)
                vx = vec / length if length > 0 else np.array([1,0,0])

                p1_draw = p1
                p2_draw = p2

                if (off_i > 0 or off_j > 0) and length > 0.001:
                    if off_i + off_j >= length:
                        scale = (length / (off_i + off_j)) * 0.99
                        p1_draw = p1 + (vx * off_i * scale)
                        p2_draw = p2 - (vx * off_j * scale)
                    else:
                        p1_draw = p1 + (vx * off_i)
                        p2_draw = p2 - (vx * off_j)

                if eid in self.selected_element_ids:
                     center_lines.extend([p1, p2]) 
                     center_colors.extend([color_edge_select, color_edge_select])

                v1, v2, v3 = self._get_consistent_axes(el)
                path_points.append( (p1_draw, v2, v3) )
                path_points.append( (p2_draw, v2, v3) )

            y_shift, z_shift = sec.get_insertion_point_shift(el.cardinal_point)
            off_vec_i = getattr(el, 'joint_offset_i', np.array([0,0,0]))
            off_vec_j = getattr(el, 'joint_offset_j', np.array([0,0,0]))
            
            num_pts = len(path_points)
            
            for i in range(num_pts - 1):
                pos_a, v2_a, v3_a = path_points[i]
                pos_b, v2_b, v3_b = path_points[i+1]
                
                if num_pts > 1:
                    s_a = i / (num_pts - 1)
                    s_b = (i + 1) / (num_pts - 1)
                else:
                    s_a, s_b = 0.0, 1.0

                curr_off_a = (1 - s_a) * off_vec_i + s_a * off_vec_j
                curr_off_b = (1 - s_b) * off_vec_i + s_b * off_vec_j
                
                center_a = pos_a + curr_off_a + (y_shift * v2_a) + (z_shift * v3_a)
                center_b = pos_b + curr_off_b + (y_shift * v2_b) + (z_shift * v3_b)

                is_first_seg = (i == 0)
                is_last_seg = (i == num_pts - 2)

                self._add_loft_segment(
                    center_a, center_b, 
                    v2_a, v3_a, v2_b, v3_b,
                    shape_yz, face_color, 
                    show_edges, current_edge_color,
                    draw_start_ring=is_first_seg, 
                    draw_end_ring=is_last_seg
                )

        if center_lines:
             cl = gl.GLLinePlotItem(
                 pos=np.array(center_lines), color=np.array(center_colors),
                 mode='lines', width=5.0, antialias=True
             )
             cl.setGLOptions('translucent')
             self.addItem(cl)

        if self.ex_vertices:
            mesh = gl.GLMeshItem(
                vertexes=np.array(self.ex_vertices, dtype=np.float32),
                faces=np.array(self.ex_faces, dtype=np.int32),
                vertexColors=np.array(self.ex_colors, dtype=np.float32),
                smooth=False, drawEdges=False, glOptions='translucent'
            )
            self.addItem(mesh)

        if show_edges and self.ex_edges:
             ed = gl.GLLinePlotItem(
                 pos=np.array(self.ex_edges), 
                 color=np.array(self.ex_edge_colors), 
                 mode='lines', width=edge_width, antialias=True 
             )
             ed.setGLOptions('opaque') 
             self.addItem(ed)

    def _add_loft_segment(self, c1, c2, v2_a, v3_a, v2_b, v3_b, shape, color, show_edges, edge_color, 
                          draw_start_ring=False, draw_end_ring=False):
        """
        Smart Extrusion: Generates triangles but selectively hides internal 'ribs' 
        to maintain the clean 'glass' look.
        """
                               
        start_idx = len(self.ex_vertices)
        
        verts_a = []
        for y, z in shape:
            p = c1 + (y * v2_a) + (z * v3_a)
            verts_a.append(p)
            
        verts_b = []
        for y, z in shape:
            p = c2 + (y * v2_b) + (z * v3_b)
            verts_b.append(p)
            
        self.ex_vertices.extend(verts_a)
        self.ex_vertices.extend(verts_b)
        
        for _ in range(len(verts_a) + len(verts_b)):
            self.ex_colors.append(color)
            
        n = len(shape)
        for i in range(n):
            next_i = (i + 1) % n
            
            idx_a_curr = start_idx + i
            idx_a_next = start_idx + next_i
            idx_b_curr = start_idx + n + i
            idx_b_next = start_idx + n + next_i
            
            self.ex_faces.append([idx_a_curr, idx_a_next, idx_b_next])
            self.ex_faces.append([idx_a_curr, idx_b_next, idx_b_curr])
            
            if show_edges:
                                                                            
                self.ex_edges.extend([verts_a[i], verts_b[i]])
                self.ex_edge_colors.extend([edge_color, edge_color])
                
                if draw_start_ring:
                    self.ex_edges.extend([verts_a[i], verts_a[next_i]])
                    self.ex_edge_colors.extend([edge_color, edge_color])
                
                if draw_end_ring:
                    self.ex_edges.extend([verts_b[i], verts_b[next_i]])
                    self.ex_edge_colors.extend([edge_color, edge_color])
    
    def _add_loft_to_arrays(self, c1, c2, v2_a, v3_a, v2_b, v3_b, shape, color, show_edges, edge_color,
                            draw_start_ring=False, draw_end_ring=False,
                            ex_vertices=None, ex_faces=None, ex_colors=None,
                            ex_edges=None, ex_edge_colors=None):
        """
        Same as _add_loft_segment but adds to provided arrays instead of self.ex_*
        Used for pre-rendering animation frames.
        """
                               
        start_idx = len(ex_vertices)
        
        verts_a = []
        for y, z in shape:
            p = c1 + (y * v2_a) + (z * v3_a)
            verts_a.append(p)
        
        verts_b = []
        for y, z in shape:
            p = c2 + (y * v2_b) + (z * v3_b)
            verts_b.append(p)
        
        ex_vertices.extend(verts_a)
        ex_vertices.extend(verts_b)
        
        for _ in range(len(verts_a) + len(verts_b)):
            ex_colors.append(color)
        
        n = len(shape)
        for i in range(n):
            next_i = (i + 1) % n
            
            idx_a_curr = start_idx + i
            idx_a_next = start_idx + next_i
            idx_b_curr = start_idx + n + i
            idx_b_next = start_idx + n + next_i
            
            ex_faces.append([idx_a_curr, idx_a_next, idx_b_next])
            ex_faces.append([idx_a_curr, idx_b_next, idx_b_curr])
            
            if show_edges:
                                   
                ex_edges.extend([verts_a[i], verts_b[i]])
                ex_edge_colors.extend([edge_color, edge_color])
                
                if draw_start_ring:
                    ex_edges.extend([verts_a[i], verts_a[next_i]])
                    ex_edge_colors.extend([edge_color, edge_color])
                
                if draw_end_ring:
                    ex_edges.extend([verts_b[i], verts_b[next_i]])
                    ex_edge_colors.extend([edge_color, edge_color])
    
    def _triangulate_cap_indices(self, indices, full_faces):
        """Helper to triangulate a polygon given vertex indices."""
        if len(indices) < 3: return
        root = indices[0]
        for i in range(1, len(indices) - 1):
            full_faces.append([root, indices[i], indices[i+1]])
    def _triangulate_cap(self, indices, full_faces, full_colors, color):
        """
        Closes the ends of the extruded shape using a Triangle Fan.
        Works well for Rectangles and standard I-Sections.
        """
        if len(indices) < 3: return
        
        root = indices[0]
        
        for i in range(1, len(indices) - 1):
            p2 = indices[i]
            p3 = indices[i+1]
            
            full_faces.append([root, p2, p3])
            
            full_colors.append(color)
            full_colors.append(color)
            full_colors.append(color)

    def _draw_slabs(self, model):
        if not hasattr(model, 'slabs') or not model.slabs: return
        
        opacity = self.display_config.get("slab_opacity", 0.4)
                              
        base_color = (0.7, 0.7, 0.7, opacity)                   
        
        verts = []; faces = []; colors = []
        v_start_idx = 0 

        for slab in model.slabs.values():
            nodes = slab.nodes
            n_count = len(nodes)
            if n_count < 3: continue
            if not self._is_visible(nodes[0].x, nodes[0].y, nodes[0].z): continue

            for n in nodes:
                verts.append([n.x, n.y, n.z])
                colors.append(base_color)
            
            for i in range(1, n_count - 1):
                faces.append([v_start_idx, v_start_idx + i, v_start_idx + i + 1])
            v_start_idx += n_count

        if not verts: return

        mesh = gl.GLMeshItem(
            vertexes=np.array(verts), faces=np.array(faces, dtype=np.int32),
            vertexColors=np.array(colors), smooth=False, shader='balloon',
            glOptions='translucent')
        self.addItem(mesh)

    def _get_visibility_state(self, x, y, z):
        """
        Returns:
        0: Hidden (not used usually)
        1: Background/Ghosted (Off-plane)
        2: Active/Editable (On-plane or 3D mode)
        """
        if self.active_view_plane is None:
            return 2
            
        axis = self.active_view_plane['axis']
        val = self.active_view_plane['value']
        tol = 0.001
        
        current_val = {'x': x, 'y': y, 'z': z}[axis]
        
        if abs(current_val - val) < tol:
            return 2         
        return 1             

    def _draw_support_meshes(self, positions, s_type):
        """
        Draws 3D shapes for supports.
        Fixed = Cube, Pinned = Pyramid, Roller = Sphere
        """
        if not positions: return

        all_verts = []
        all_faces = []
        all_colors = []
        
        s = 0.3                                       
        
        if s_type == 'fixed': c = (0, 1, 1, 1) 
        else: c = (0, 1, 0, 1)

        idx_offset = 0

        for x, y, z in positions:
            if s_type == 'fixed':
                                        
                z_top = z
                z_bot = z - (2 * s)
                
                v = [
                    [x-s, y-s, z_bot], [x+s, y-s, z_bot], [x+s, y+s, z_bot], [x-s, y+s, z_bot], 
                    [x-s, y-s, z_top], [x+s, y-s, z_top], [x+s, y+s, z_top], [x-s, y+s, z_top]
                ]
                f = [
                    [0, 1, 2], [0, 2, 3], [4, 5, 6], [4, 6, 7],           
                    [0, 1, 5], [0, 5, 4], [2, 3, 7], [2, 7, 6],              
                    [0, 3, 7], [0, 7, 4], [1, 2, 6], [1, 6, 5]               
                ]
                all_verts.extend(v)
                all_faces.extend([[i + idx_offset for i in face] for face in f])
                for _ in range(8): all_colors.append(c)
                idx_offset += 8

            elif s_type == 'pinned':
                                           
                v = [
                    [x, y, z],                        
                    [x-s, y-s, z-s*2], [x+s, y-s, z-s*2], 
                    [x+s, y+s, z-s*2], [x-s, y+s, z-s*2]
                ]
                f = [
                    [0, 1, 2], [0, 2, 3], [0, 3, 4], [0, 4, 1],        
                    [1, 2, 3], [1, 3, 4]                              
                ]
                all_verts.extend(v)
                all_faces.extend([[i + idx_offset for i in face] for face in f])
                for _ in range(5): all_colors.append(c)
                idx_offset += 5

            elif s_type == 'roller':
                                                        
                radius = s
                bands = 8 
                z_center = z - radius                     
                
                local_verts = []
                local_faces = []
                
                for i in range(bands + 1):
                    lat = np.pi * i / bands                          
                    z_val = np.cos(lat)
                    r_ring = np.sin(lat)
                    
                    for j in range(bands):           
                         lon = 2 * np.pi * j / bands
                         x_val = r_ring * np.cos(lon)
                         y_val = r_ring * np.sin(lon)
                                                    
                         local_verts.append([x + x_val*radius, y + y_val*radius, z_center + z_val*radius])
                
                for i in range(bands):
                    for j in range(bands):
                        row1 = i * bands
                        row2 = (i + 1) * bands
                        
                        c1 = j
                        c2 = (j + 1) % bands
                        
                        p1, p2 = row1 + c1, row1 + c2
                        p3, p4 = row2 + c2, row2 + c1
                        
                        local_faces.append([p1, p2, p4])
                        local_faces.append([p2, p3, p4])

                all_verts.extend(local_verts)
                all_faces.extend([[idx + idx_offset for idx in face] for face in local_faces])
                
                for _ in range(len(local_verts)): all_colors.append(c)
                idx_offset += len(local_verts)

        if not all_verts: return

        mesh = gl.GLMeshItem(
            vertexes=np.array(all_verts, dtype=np.float32),
            faces=np.array(all_faces, dtype=np.int32),
            vertexColors=np.array(all_colors, dtype=np.float32),
            smooth=False, 
            shader='balloon',
            glOptions='opaque'
        )
        self.addItem(mesh)
    
    def _draw_loads(self, model):
        """
        Visualizes Nodal Loads.
        - Always: Draws Arrow.
        - Selected: Draws Text Label with Units.
        """
        if not model.loads: return
        if not self.show_loads: return
        if self.load_type_filter == "frame": return 
        
        arrow_lines = []
        arrow_colors = []
        
        L = 2.0; H = 0.5; W = 0.2                           
        
        def add_arrow(pt, direction, color, is_moment):
            tip = pt
            tail = pt - (direction * L)
            arrow_lines.append(tail); arrow_lines.append(tip)
            arrow_colors.append(color); arrow_colors.append(color)
            
            def add_head(base_pt):
                if abs(direction[2]) > 0.9: perp = np.array([1.0, 0.0, 0.0])                        
                elif abs(direction[1]) > 0.9: perp = np.array([1.0, 0.0, 0.0])                        
                else: perp = np.array([0.0, 0.0, 1.0])                        
                w_vec = perp * W
                base = base_pt - (direction * H)
                arrow_lines.append(base_pt); arrow_lines.append(base + w_vec)
                arrow_lines.append(base_pt); arrow_lines.append(base - w_vec)
                for _ in range(4): arrow_colors.append(color)

            add_head(tip)             
            if is_moment:
                add_head(tip - (direction * (H * 0.8)))

        for load in model.loads:
            if not hasattr(load, 'node_id'): continue
            if self.visible_load_patterns and load.pattern_name not in self.visible_load_patterns: continue

            node = model.nodes.get(load.node_id)
            if not node: continue
            if not self._is_visible(node.x, node.y, node.z): continue
            
            origin = np.array([node.x, node.y, node.z])
            is_selected = (node.id in self.selected_node_ids)

            def process_component(val, axis_vec, color, is_moment):
                if abs(val) > 0:
                    d = axis_vec * (1 if val > 0 else -1)
                    add_arrow(origin, d, color, is_moment)
                    

                    if is_selected:
                        l_type = "Moment" if is_moment else "Force"
                        self._add_load_label(origin, d, val, l_type, color)

  
            c_black = (0, 0, 0, 1)

            process_component(load.fz, np.array([0, 0, 1.0]), c_black, False)
            process_component(load.fx, np.array([1.0, 0, 0]), c_black, False)
            process_component(load.fy, np.array([0, 1.0, 0]), c_black, False)

            process_component(load.mz, np.array([0, 0, 1.0]), c_black, True)
            process_component(load.mx, np.array([1.0, 0, 0]), c_black, True)
            process_component(load.my, np.array([0, 1.0, 0]), c_black, True)

        if arrow_lines:
            self.addItem(gl.GLLinePlotItem(
                pos=np.array(arrow_lines), 
                color=np.array(arrow_colors), 
                mode='lines', width=2, antialias=True
            ))

    def _add_load_label(self, origin, direction, val, l_type, color):
        if l_type == "Moment":
            m_scale = unit_registry.force_scale * unit_registry.length_scale
            display_val = abs(val) * m_scale
            unit_str = f"{unit_registry.force_unit_name}.{unit_registry.length_unit_name}"
        else:
            display_val = unit_registry.to_display_force(abs(val))
            unit_str = unit_registry.force_unit_name
            
        label_pos = origin - (direction * 2.2)
        self.load_labels.append({
            'pos_3d': label_pos,
            'text': f"{display_val:.2f} {unit_str}",
            'color': color
        })

    def _draw_reference_grids(self, model):

        def get_visible(lines_attr):
            if not lines_attr: return [0.0]
                                                                      
            if isinstance(lines_attr[0], dict):
                return [item['ord'] for item in lines_attr if item.get('visible', True)]
                                                                 
            return lines_attr

        vis_x = get_visible(getattr(model.grid, 'x_lines', model.grid.x_grids))
        vis_y = get_visible(getattr(model.grid, 'y_lines', model.grid.y_grids))
        vis_z = get_visible(getattr(model.grid, 'z_lines', model.grid.z_grids))
        
        if not vis_x or not vis_y or not vis_z: return

        z_min, z_max = min(vis_z), max(vis_z)
        x_min, x_max = min(vis_x), max(vis_x)
        y_min, y_max = min(vis_y), max(vis_y)

        bright_pos = []                       
        dim_pos = []                        

        def is_on_active_plane(p1, p2):
            if not self.active_view_plane: return False                                    
            
            axis = self.active_view_plane['axis']
            val = self.active_view_plane['value']
            tol = 0.001
            
            if axis == 'x': return abs(p1[0] - val) < tol and abs(p2[0] - val) < tol
            if axis == 'y': return abs(p1[1] - val) < tol and abs(p2[1] - val) < tol
            if axis == 'z': return abs(p1[2] - val) < tol and abs(p2[2] - val) < tol
            return False

        for x in vis_x:
            for y in vis_y:
                p1 = [x, y, z_min]; p2 = [x, y, z_max]
                if is_on_active_plane(p1, p2): bright_pos.extend([p1, p2])
                else: dim_pos.extend([p1, p2])

        for z in vis_z:
            for y in vis_y:
                p1 = [x_min, y, z]; p2 = [x_max, y, z]
                if is_on_active_plane(p1, p2): bright_pos.extend([p1, p2])
                else: dim_pos.extend([p1, p2])

        for z in vis_z:
            for x in vis_x:
                p1 = [x, y_min, z]; p2 = [x, y_max, z]
                if is_on_active_plane(p1, p2): bright_pos.extend([p1, p2])
                else: dim_pos.extend([p1, p2])

        if bright_pos:
            self.addItem(gl.GLLinePlotItem(pos=np.array(bright_pos), mode='lines', 
                                           color=(0, 1, 1, 0.8), width=2, antialias=True))
            
        if dim_pos:
            alpha = 0.6 if self.active_view_plane is None else 0.1
            c = (0.6, 0.6, 0.6, alpha)
            self.addItem(gl.GLLinePlotItem(pos=np.array(dim_pos), mode='lines', 
                                           color=c, width=2, antialias=True))
        
        self.addItem(gl.GLLinePlotItem(pos=np.array([[0,0,0], [5,0,0]]), color=(1,0,0,1), width=3, glOptions='opaque', antialias=True))
        self.addItem(gl.GLTextItem(pos=np.array([5.5,0,0]), text="X", color=(1,0,0,1)))
        
        self.addItem(gl.GLLinePlotItem(pos=np.array([[0,0,0], [0,5,0]]), color=(0,1,0,1), width=3, glOptions='opaque', antialias=True))
        self.addItem(gl.GLTextItem(pos=np.array([0,5.5,0]), text="Y", color=(0,1,0,1)))
        
        self.addItem(gl.GLLinePlotItem(pos=np.array([[0,0,0], [0,0,5]]), color=(0,0,1,1), width=3, glOptions='opaque', antialias=True))
        self.addItem(gl.GLTextItem(pos=np.array([0,0,5.5]), text="Z", color=(0,0,1,1)))

    def get_snap_point(self, mouse_x, mouse_y):
        if not self.snapping_enabled:
            self.snap_ring.setVisible(False)
            self.snap_dot.setVisible(False)
            return None
        if not self.current_model: return None

        candidates = []
        grids = self.current_model.grid
        
        if self.active_view_plane:
            val = self.active_view_plane['value']
            axis = self.active_view_plane['axis']
            z_range = [val] if axis == 'z' else grids.z_grids
            y_range = [val] if axis == 'y' else grids.y_grids
            x_range = [val] if axis == 'x' else grids.x_grids
        else:
            z_range = grids.z_grids
            y_range = grids.y_grids
            x_range = grids.x_grids

        for z in z_range:
            for x in x_range:
                for y in y_range:
                    candidates.append((x, y, z))
        
        if not candidates: return None
        
        view_w = self.width()
        view_h = self.height()
        full_area = (0, 0, view_w, view_h)
        m_view = self.viewMatrix()
        m_proj = self.projectionMatrix(region=full_area, viewport=full_area)
        mvp = m_proj * m_view
        mvp_matrix = np.array(mvp.data()).reshape(4, 4).T

        best_point = None
        closest_dist = 25.0                                 
        
        for pt in candidates:
            vec = np.array([pt[0], pt[1], pt[2], 1.0])
            clip = np.dot(mvp_matrix, vec)
            if clip[3] == 0: continue
            ndc_x = clip[0] / clip[3]
            ndc_y = clip[1] / clip[3]
            screen_x = (ndc_x + 1) * view_w / 2
            screen_y = (1 - ndc_y) * view_h / 2
            
            dx = screen_x - mouse_x
            dy = screen_y - mouse_y
            dist = (dx**2 + dy**2)**0.5
            
            if dist < closest_dist:
                closest_dist = dist
                best_point = pt

        if best_point:
            bx, by, bz = best_point
            
            inv_view = np.linalg.inv(np.array(m_view.data()).reshape(4,4).T)
            cam_pos = inv_view[:3, 3]
            dir_vec = np.array([cam_pos[0]-bx, cam_pos[1]-by, cam_pos[2]-bz])
            dist_cam = np.linalg.norm(dir_vec)
            
            if dist_cam > 0:
                norm_dir = dir_vec / dist_cam
                                                               
                nx, ny, nz = bx + norm_dir[0]*0.3, by + norm_dir[1]*0.3, bz + norm_dir[2]*0.3
            else:
                nx, ny, nz = bx, by, bz
                norm_dir = np.array([0,0,1])

            world_up = np.array([0, 0, 1])
            if abs(np.dot(world_up, norm_dir)) > 0.99: 
                world_up = np.array([0, 1, 0])                       
            
            right = np.cross(world_up, norm_dir)
            right /= np.linalg.norm(right)
            
            up = np.cross(norm_dir, right)
            up /= np.linalg.norm(up)
            
            radius = 0.4            
            segments = 16
            angles = np.linspace(0, 2*np.pi, segments + 1)
            ring_pts = []
            
            center = np.array([nx, ny, nz])
            
            for ang in angles:
                                                             
                pt = center + radius * (np.cos(ang) * right + np.sin(ang) * up)
                ring_pts.append(pt)

            self.snap_ring.setData(pos=np.array(ring_pts), color=(1, 0, 0, 1), width=3)
            self.snap_ring.setVisible(True)

            self.snap_dot.setData(pos=np.array([[nx, ny, nz]]), color=(1, 1, 0, 1), size=8)                
            self.snap_dot.setVisible(True)
            
        else:
            self.snap_ring.setVisible(False)
            self.snap_dot.setVisible(False)
        
        return best_point
    
    def _on_anim_frame(self, factor):
        """
        Called by the AnimationManager 30 times a second.
        
        NEW BEHAVIOR (Fast!):
        - If geometry is pre-rendered, just swap to the right frame
        - If not pre-rendered, fall back to old behavior
        
        This is where the magic happens - instead of recalculating everything,
        we just select a pre-built frame!
        """
                                                  
        self.anim_factor = factor
        
        if not self.view_deflected:
            return

        if self.is_animation_cached and self.prerendered_geometry_frames:
                                                                
            frame_idx = self.animation_manager.current_frame_index
            
            if 0 <= frame_idx < len(self.prerendered_geometry_frames):
                self._render_prerendered_frame(frame_idx)
                return                                      
        
        self.draw_model(
            self.current_model, 
            self.selected_element_ids, 
            self.selected_node_ids
        )
    
    def invalidate_animation_cache(self):
        """
        Clears the pre-rendered animation geometry cache.
        
        Call this when:
        - Deflection scale changes
        - Model changes
        - Results change
        - Any setting that affects rendering
        """
        self.prerendered_geometry_frames.clear()
        self.is_animation_cached = False
        self.current_animation_frame = 0
    
    def _clear_static_elements(self):
        """
        Removes all static element geometry from the scene.
        
        Called when starting animation to prevent "double structure" issue.
        Keeps: nodes, supports, loads, constraints, grid, snap markers
        Removes: All element lines and meshes
        """
        items_to_remove = []
        
        for item in self.items[:]:
                                                                                   
            if isinstance(item, gl.GLLinePlotItem):
                if item not in [self.snap_ring, self.snap_dot]:
                                                                           
                    items_to_remove.append(item)
            
            elif isinstance(item, gl.GLMeshItem):
                items_to_remove.append(item)
        
        for item in items_to_remove:
            try:
                self.removeItem(item)
            except:
                pass
        
        self.element_items.clear()
    
    def update_selection_during_animation(self, sel_elems=None, sel_nodes=None):
        """
        Updates selection state during animation without causing redraw lag.
        
        This is called when user selects nodes/elements while animation is running.
        Instead of redrawing everything (which causes lag), we just update the
        selection state. The next animation frame will show the updated selection.
        
        Args:
            sel_elems: List of selected element IDs
            sel_nodes: List of selected node IDs
        """
        if sel_elems is not None:
            self.selected_element_ids = sel_elems
        if sel_nodes is not None:
            self.selected_node_ids = sel_nodes
        
    def prerender_animation_frames(self, anim_factors, progress_callback=None):
        """
        Pre-calculates ALL geometry for all 60 animation frames.
        
        THIS IS THE KEY METHOD THAT MAKES ANIMATION SMOOTH!
        
        Args:
            anim_factors: List of 60 animation factor values (-1.0 to 1.0)
            progress_callback: Function(percent) called with progress 0-100
            
        Process:
        1. For each of 60 frames:
           - Sets anim_factor
           - Calculates ALL curved element geometry
           - Stores positions and colors
        2. Updates progress bar
        
        Result: Playback just swaps between pre-built frames = BUTTER SMOOTH!
        
        On a slow PC:
        - Pre-rendering takes 5-10 seconds (shows progress bar)
        - Playback is 60 FPS smooth (no calculations during playback)
        """
        if not self.current_model:
            return
        
        can_deflect = (self.view_deflected and 
                       hasattr(self.current_model, 'has_results') and 
                       self.current_model.has_results and 
                       self.current_model.results is not None)
        
        if not can_deflect:
                                                       
            self.is_animation_cached = False
            return
        
        self.prerendered_geometry_frames.clear()
        
        total_frames = len(anim_factors)
        
        for frame_idx, factor in enumerate(anim_factors):
                                               
            frame_geometry = self._calculate_frame_geometry(factor)
            
            self.prerendered_geometry_frames.append(frame_geometry)
            
            if progress_callback:
                percent = int((frame_idx + 1) / total_frames * 100)
                progress_callback(percent)
        
        self.is_animation_cached = True
        self.current_animation_frame = 0
    
    def _calculate_frame_geometry(self, anim_factor):
        """
        Calculates the complete geometry for ONE animation frame.
        
        NOW INCLUDES BOTH WIREFRAME AND EXTRUDED GEOMETRY!
        
        Args:
            anim_factor: The animation factor for this frame (-1.0 to 1.0)
            
        Returns:
            Dictionary containing all rendering data for this frame:
            {
                # Wireframe data
                'curved_pos': [...],      
                'curved_colors': [...],   
                
                # Extruded data
                'ex_vertices': [...],     # Mesh vertices
                'ex_faces': [...],        # Face indices
                'ex_colors': [...],       # Vertex colors
                'ex_edges': [...],        # Edge lines
                'ex_edge_colors': [...],  # Edge colors
                'center_lines': [...],    # Selection highlights
                'center_colors': [...],   
            }
        """
        model = self.current_model
        
        curved_pos = []
        curved_colors = []
        
        ex_vertices = []
        ex_faces = []
        ex_colors = []
        ex_edges = []
        ex_edge_colors = []
        center_lines = []
        center_colors = []
        
        opacity = self.display_config.get("extrude_opacity", 0.35)
        show_edges = self.display_config.get("show_edges", False)
        edge_c = np.array(self.display_config.get("edge_color", (0, 0, 0, 1)))
        color_edge_select = np.array([1.0, 1.0, 0.0, 1.0])
        
        for eid, el in model.elements.items():
            n1, n2 = el.node_i, el.node_j
            
            v1 = self._get_visibility_state(n1.x, n1.y, n1.z)
            v2 = self._get_visibility_state(n2.x, n2.y, n2.z)
            
            if v1 == 0 or v2 == 0:
                continue
            
            if v1 == 1 and v2 == 1:
                continue
            
            p1 = np.array([n1.x, n1.y, n1.z])
            p2 = np.array([n2.x, n2.y, n2.z])
            
            if eid in self.selected_element_ids:
                wire_color = np.array([1.0, 0.0, 0.0, 1.0])
            else:
                wire_color = getattr(el.section, 'color', np.array([0.5, 0.5, 0.5, 1.0]))
                if len(wire_color) == 3:
                    wire_color = (*wire_color, 1.0)
                wire_color = np.array(wire_color)
            
            res_i = model.results.get("displacements", {}).get(str(n1.id))
            res_j = model.results.get("displacements", {}).get(str(n2.id))
            
            if not (res_i and res_j):
                continue                            
            
            cache_key = eid
            
            if self.cache_scale_used != self.deflection_scale:
                self.invalidate_deflection_cache()
                self.deflection_cache.clear()
                self.cache_scale_used = self.deflection_scale
            
            if cache_key not in self.deflection_cache:
                v1_ax, v2_ax, v3_ax = self._get_consistent_axes(el)
                
                curve_data = get_deflected_shape(
                    [n1.x, n1.y, n1.z], 
                    [n2.x, n2.y, n2.z], 
                    res_i, res_j, 
                    v1_ax, v2_ax, v3_ax, 
                    scale=self.deflection_scale,
                    num_points=11
                )
                
                self.deflection_cache[cache_key] = {
                    'curve_data': curve_data,
                    'p1_orig': p1.copy(),
                    'p2_orig': p2.copy()
                }
            
            cached = self.deflection_cache[cache_key]
            curve_data_full = cached['curve_data']
            
            for k in range(len(curve_data_full) - 1):
                pos_full, _, _ = curve_data_full[k]
                pos_full_next, _, _ = curve_data_full[k+1]
                
                s = k / (len(curve_data_full) - 1)
                pos_orig = p1 + s * (p2 - p1)
                
                s_next = (k + 1) / (len(curve_data_full) - 1)
                pos_orig_next = p1 + s_next * (p2 - p1)
                
                displacement = pos_full - pos_orig
                p_start = pos_orig + displacement * anim_factor
                
                displacement_next = pos_full_next - pos_orig_next
                p_end = pos_orig_next + displacement_next * anim_factor
                
                curved_pos.append(p_start)
                curved_pos.append(p_end)
                curved_colors.append(wire_color)
                curved_colors.append(wire_color)
            
            sec = el.section
            shape_yz = sec.get_shape_coords()
            if not shape_yz:
                continue
            
            is_active_elem = (v1 == 2 and v2 == 2)
            
            if not is_active_elem:
                face_color = np.array([0.6, 0.6, 0.6, 0.3])
                current_edge_color = np.array([0.6, 0.6, 0.6, 0.1])
            else:
                c_raw = getattr(sec, 'color', [0.7, 0.7, 0.7])
                if len(c_raw) == 4:
                    c_raw = c_raw[:3]
                face_color = np.array([c_raw[0], c_raw[1], c_raw[2], opacity])
                current_edge_color = edge_c
            
            path_points = []
            v1_orig, v2_orig, v3_orig = self._get_consistent_axes(el)
            
            for k in range(len(curve_data_full)):
                pos_full, tan_vec, twist = curve_data_full[k]
                
                s = k / (len(curve_data_full) - 1) if len(curve_data_full) > 1 else 0.0
                pos_orig = p1 + s * (p2 - p1)
                
                displacement = pos_full - pos_orig
                pos_anim = pos_orig + displacement * anim_factor
                
                v1_curr = tan_vec
                c_t = np.cos(twist)
                s_t = np.sin(twist)
                v2_twisted = (c_t * v2_orig) + (s_t * v3_orig)
                
                proj = np.dot(v2_twisted, v1_curr) * v1_curr
                v2_curr = v2_twisted - proj
                n2_len = np.linalg.norm(v2_curr)
                if n2_len > 1e-6:
                    v2_curr /= n2_len
                else:
                    v2_curr = v2_orig
                
                v3_curr = np.cross(v1_curr, v2_curr)
                path_points.append((pos_anim, v2_curr, v3_curr))
            
            if eid in self.selected_element_ids and len(path_points) >= 2:
                center_lines.extend([path_points[0][0], path_points[-1][0]])
                center_colors.extend([color_edge_select, color_edge_select])
            
            y_shift, z_shift = sec.get_insertion_point_shift(el.cardinal_point)
            off_vec_i = getattr(el, 'joint_offset_i', np.array([0, 0, 0]))
            off_vec_j = getattr(el, 'joint_offset_j', np.array([0, 0, 0]))
            
            num_pts = len(path_points)
            
            for i in range(num_pts - 1):
                pos_a, v2_a, v3_a = path_points[i]
                pos_b, v2_b, v3_b = path_points[i + 1]
                
                if num_pts > 1:
                    s_a = i / (num_pts - 1)
                    s_b = (i + 1) / (num_pts - 1)
                else:
                    s_a, s_b = 0.0, 1.0
                
                curr_off_a = (1 - s_a) * off_vec_i + s_a * off_vec_j
                curr_off_b = (1 - s_b) * off_vec_i + s_b * off_vec_j
                
                center_a = pos_a + curr_off_a + (y_shift * v2_a) + (z_shift * v3_a)
                center_b = pos_b + curr_off_b + (y_shift * v2_b) + (z_shift * v3_b)
                
                is_first_seg = (i == 0)
                is_last_seg = (i == num_pts - 2)
                
                self._add_loft_to_arrays(
                    center_a, center_b,
                    v2_a, v3_a, v2_b, v3_b,
                    shape_yz, face_color,
                    show_edges, current_edge_color,
                    draw_start_ring=is_first_seg,
                    draw_end_ring=is_last_seg,
                    ex_vertices=ex_vertices,
                    ex_faces=ex_faces,
                    ex_colors=ex_colors,
                    ex_edges=ex_edges,
                    ex_edge_colors=ex_edge_colors
                )
        
        return {
            'curved_pos': curved_pos,
            'curved_colors': curved_colors,
            'ex_vertices': ex_vertices,
            'ex_faces': ex_faces,
            'ex_colors': ex_colors,
            'ex_edges': ex_edges,
            'ex_edge_colors': ex_edge_colors,
            'center_lines': center_lines,
            'center_colors': center_colors,
        }
    
    def _render_prerendered_frame(self, frame_idx):
        """
        Renders a pre-calculated animation frame.
        
        NOW SUPPORTS BOTH WIREFRAME AND EXTRUDED MODES!
        
        THIS IS BLAZING FAST because:
        - No calculations needed
        - No cache lookups  
        - No get_deflected_shape calls
        - Just swap OpenGL buffers
        
        Args:
            frame_idx: Index of the frame to render (0-59)
        """
                                           
        frame = self.prerendered_geometry_frames[frame_idx]
        
        for item in self.element_items:
            try:
                self.removeItem(item)
            except:
                pass
        self.element_items.clear()
        
        if self.view_extruded:
                                       
            ex_vertices = frame['ex_vertices']
            ex_faces = frame['ex_faces']
            ex_colors = frame['ex_colors']
            ex_edges = frame['ex_edges']
            ex_edge_colors = frame['ex_edge_colors']
            center_lines = frame['center_lines']
            center_colors = frame['center_colors']
            
            if center_lines:
                cl = gl.GLLinePlotItem(
                    pos=np.array(center_lines),
                    color=np.array(center_colors),
                    mode='lines',
                    width=5.0,
                    antialias=True
                )
                cl.setGLOptions('translucent')
                self.addItem(cl)
                self.element_items.append(cl)
            
            if ex_vertices:
                mesh = gl.GLMeshItem(
                    vertexes=np.array(ex_vertices, dtype=np.float32),
                    faces=np.array(ex_faces, dtype=np.int32),
                    vertexColors=np.array(ex_colors, dtype=np.float32),
                    smooth=False,
                    drawEdges=False,
                    glOptions='translucent'
                )
                self.addItem(mesh)
                self.element_items.append(mesh)
            
            show_edges = self.display_config.get("show_edges", False)
            edge_width = self.display_config.get("edge_width", 1.0)
            
            if show_edges and ex_edges:
                ed = gl.GLLinePlotItem(
                    pos=np.array(ex_edges),
                    color=np.array(ex_edge_colors),
                    mode='lines',
                    width=edge_width,
                    antialias=True
                )
                ed.setGLOptions('opaque')
                self.addItem(ed)
                self.element_items.append(ed)
        
        else:
                                        
            curved_pos = frame['curved_pos']
            curved_colors = frame['curved_colors']
            
            if curved_pos:
                curved_item = gl.GLLinePlotItem(
                    pos=np.array(curved_pos),
                    color=np.array(curved_colors),
                    mode='lines',
                    width=self.display_config.get("line_width", 2.0),
                    antialias=True
                )
                self.addItem(curved_item)
                self.element_items.append(curved_item)
        
    def mousePressEvent(self, event):

        hit = self.view_cube.check_click(event.pos().x(), event.pos().y(), self.width(), self.height())
 
        if hit:
            print("View Cube Clicked!")
            # Logic to snap view goes here:
            # self.set_standard_view("TOP")
            return # Don't select beams if we clicked the cube


        self._prev_mouse_pos = event.pos()
        modifiers = QApplication.keyboardModifiers()
        
        if modifiers == Qt.KeyboardModifier.ShiftModifier:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            if self.snapping_enabled:
                pos = event.pos()
                snap_coord = self.get_snap_point(pos.x(), pos.y())
                if snap_coord is not None:
                    self.signal_canvas_clicked.emit(snap_coord[0], snap_coord[1], snap_coord[2])
                return

            self.drag_start = event.pos()
            self.drag_current = event.pos()
            self.is_selecting = True
            self.update()

        elif event.button() == Qt.MouseButton.RightButton:
            self.signal_right_clicked.emit()
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.drag_current = event.pos()
            self.update()
            return

        if event.buttons() == Qt.MouseButton.MiddleButton:
                                                                                
            pass

        if event.buttons() == Qt.MouseButton.MiddleButton:
                             
            if hasattr(self, '_prev_mouse_pos'):
                dx = event.pos().x() - self._prev_mouse_pos.x()
                dy = event.pos().y() - self._prev_mouse_pos.y()
                self.camera.pan(dx, dy, self.width(), self.height())
            self._prev_mouse_pos = event.pos()
            
        elif event.buttons() == Qt.MouseButton.LeftButton:
                                                                           
             self.show_pivot_dot(True)
             super().mouseMoveEvent(event)
             
        else:
             super().mouseMoveEvent(event)
             
        self.get_snap_point(event.pos().x(), event.pos().y())
        
    def wheelEvent(self, event):
                         
        delta = event.angleDelta().y()
        pos = event.position()
        
        self.camera.zoom(delta, pos.x(), pos.y(), self.width(), self.height())
        
    def mouseReleaseEvent(self, event):
        if self.is_selecting and event.button() == Qt.MouseButton.LeftButton:
            self.is_selecting = False
            self.update() 
            
            if self.drag_start:
                                          
                drag_dist = (event.pos() - self.drag_start).manhattanLength()
                
                if drag_dist > 5: 
                    self.process_box_selection(self.drag_start, event.pos())
                
                else:
                    self.pick_single_object(event.pos())

            self.drag_start = None
            self.drag_current = None
            
        super().mouseReleaseEvent(event)

    def pick_single_object(self, pos):
        """Simulates a tiny box selection around the cursor to pick one object."""
                                                              
        p_start = pos
        p_end = type(pos)(pos.x() + 10, pos.y() + 10) 
        
        start_centered = type(pos)(pos.x() - 5, pos.y() - 5)
        end_centered   = type(pos)(pos.x() + 5, pos.y() + 5)
        
        self.process_box_selection(start_centered, end_centered)

    def paintEvent(self, event):
        super().paintEvent(event)
        
        painter = QPainter(self)                                
        
        if self.is_selecting and self.drag_start and self.drag_current:
            x1, y1 = self.drag_start.x(), self.drag_start.y()
            x2, y2 = self.drag_current.x(), self.drag_current.y()
            w_sel = x2 - x1
            h_sel = y2 - y1
            rect = QRect(min(x1, x2), min(y1, y2), abs(w_sel), abs(h_sel))
            
            if w_sel > 0:
                c = QColor(0, 0, 255, 50); border = QColor(0, 0, 255, 200)
            else:
                c = QColor(0, 255, 0, 50); border = QColor(0, 255, 0, 200)
            
            painter.setBrush(c)
            painter.setPen(QPen(border, 1, Qt.PenStyle.SolidLine))
            painter.drawRect(rect)
        
        if self.load_labels and self.current_model:
            
            w = self.width()
            h = self.height()
            full_area = (0, 0, w, h)
            m_view = self.viewMatrix()
            m_proj = self.projectionMatrix(region=full_area, viewport=full_area)
            mvp = np.array((m_proj * m_view).data()).reshape(4, 4).T
            

            TEXT_WORLD_HEIGHT = 0.35
            
            font = painter.font()
            
            for label in self.load_labels:
                pos_3d = label['pos_3d']
                
                vec = np.array([pos_3d[0], pos_3d[1], pos_3d[2], 1.0])
                clip = np.dot(mvp, vec)
                
                if clip[3] <= 0.1: continue 

                ndc_x = clip[0] / clip[3]
                ndc_y = clip[1] / clip[3]
                sx = (ndc_x + 1) * w / 2
                sy = (1 - ndc_y) * h / 2
                
                if sx < -50 or sx > w + 50 or sy < -50 or sy > h + 50:
                    continue

                px_size = (h * TEXT_WORLD_HEIGHT) / (clip[3] * 1.2)
                
                if px_size < 6: 
                    continue
                
                if px_size > 60: px_size = 60

                font.setPixelSize(int(px_size))
                painter.setFont(font)

                r, g, b = label['color'][:3]
                text_color = QColor(int(r*255), int(g*255), int(b*255))
    
                text = label['text']
                metrics = painter.fontMetrics()
                t_width = metrics.horizontalAdvance(text)
                t_height = metrics.height()
                
                text_x = int(sx) + 5
                text_y = int(sy) - 5
                
                bg_rect = QRect(text_x - 2, text_y - t_height + 2, t_width + 4, t_height)
                painter.fillRect(bg_rect, QColor(255, 255, 255, 180))                              
                
                painter.setPen(text_color)
                painter.drawText(text_x, text_y, text)
        
        painter.end()

    def process_box_selection(self, p_start, p_end):
        if not self.current_model: return
        
        x_min = min(p_start.x(), p_end.x())
        x_max = max(p_start.x(), p_end.x())
        y_min = min(p_start.y(), p_end.y())
        y_max = max(p_start.y(), p_end.y())
        
        is_window_select = (p_end.x() > p_start.x())

        w = self.width()
        h = self.height()
        
        full_area = (0, 0, w, h)
        m_view = self.viewMatrix()
        m_proj = self.projectionMatrix(region=full_area, viewport=full_area)
        mvp = np.array((m_proj * m_view).data()).reshape(4, 4).T

        found_nodes = []
        found_elems = []

        node_screens = {}
        for nid, node in self.current_model.nodes.items():
            if self._get_visibility_state(node.x, node.y, node.z) != 2: 
                continue
            s_pos = self._project_to_screen(node.x, node.y, node.z, mvp, w, h)
            if s_pos:
                node_screens[nid] = s_pos
                sx, sy = s_pos
                if x_min <= sx <= x_max and y_min <= sy <= y_max:
                    found_nodes.append(nid)

        for eid, el in self.current_model.elements.items():
            n1, n2 = el.node_i, el.node_j
            
            v1 = self._get_visibility_state(n1.x, n1.y, n1.z)
            v2 = self._get_visibility_state(n2.x, n2.y, n2.z)
            
            if v1 != 2 or v2 != 2: 
                continue              

            if el.node_i.id not in node_screens or el.node_j.id not in node_screens:
                continue
            
            p1 = node_screens[el.node_i.id]
            p2 = node_screens[el.node_j.id]
            
            p1_in = (x_min <= p1[0] <= x_max and y_min <= p1[1] <= y_max)
            p2_in = (x_min <= p2[0] <= x_max and y_min <= p2[1] <= y_max)

            if is_window_select:
                                                  
                if p1_in and p2_in: found_elems.append(eid)
            else:
                                                    
                rect = (x_min, y_min, x_max, y_max)
                if self._line_intersects_rect(p1, p2, rect):
                    found_elems.append(eid)

        modifiers = QApplication.keyboardModifiers()
        is_additive = (modifiers == Qt.KeyboardModifier.ControlModifier)
        self.signal_box_selection.emit(found_nodes, found_elems, is_additive)
    def _project_to_screen(self, x, y, z, mvp, w, h):
        vec = np.array([x, y, z, 1.0])
        clip = np.dot(mvp, vec)
        if clip[3] == 0: return None
        ndc_x = clip[0] / clip[3]
        ndc_y = clip[1] / clip[3]
        screen_x = (ndc_x + 1) * w / 2
        screen_y = (1 - ndc_y) * h / 2
        return (screen_x, screen_y)
    
    def keyPressEvent(self, event):
        super().keyPressEvent(event)
        event.ignore()

    
    def _draw_member_loads(self, model):
        """
        Visualizes Distributed Loads (Ghost Fill Style).
        - Unselected: Faint colored curtain ONLY.
        - Selected: Full detail + Text with Units.
        """
        if not model.loads: return
        if not self.show_loads: return
        if self.load_type_filter == "nodal": return
        
        sel_verts = []; sel_colors = []; sel_faces = []
        sel_idx_counter = 0
        sel_lines = []; sel_line_colors = []

        ghost_verts = []; ghost_colors = []; ghost_faces = []
        ghost_idx_counter = 0

        scale = 0.75
      
        c_grav_ghost = (0, 0, 0, 0.2)
        c_local_ghost = (0, 0, 0, 0.2)
        c_other_ghost = (0, 0, 0, 0.2)

        c_grav_sel_fill = (0, 0, 0, 0.4); c_grav_line = (0, 0, 0, 1.0)
        c_local_sel_fill = (0, 0, 0, 0.4); c_local_line = (0, 0, 0, 1.0)
        c_other_sel_fill = (0, 0, 0, 0.4); c_other_line = (0, 0, 0, 1.0)

        for load in model.loads:
            if not hasattr(load, 'wx'): continue
            if not hasattr(load, 'element_id'): continue
            if self.visible_load_patterns and load.pattern_name not in self.visible_load_patterns:
                continue
            
            el = model.elements.get(load.element_id)
            if not el: continue
            
            v1 = self._get_visibility_state(el.node_i.x, el.node_i.y, el.node_i.z)
            v2 = self._get_visibility_state(el.node_j.x, el.node_j.y, el.node_j.z)
            if v1 != 2 or v2 != 2: continue

            is_selected = (el.id in self.selected_element_ids)

            p1 = np.array([el.node_i.x, el.node_i.y, el.node_i.z])
            p2 = np.array([el.node_j.x, el.node_j.y, el.node_j.z])
            beam_vec = p2 - p1
            beam_len = np.linalg.norm(beam_vec)
            if beam_len == 0: continue
            beam_dir = beam_vec / beam_len 
            
            raw_w = [load.wx, load.wy, load.wz]
            v1_ax, v2_ax, v3_ax = self._get_consistent_axes(el) 

            for axis_idx in range(3):
                val = raw_w[axis_idx]
                if abs(val) < 1e-6: continue

                base_height = 0.5
                growth_factor = 0.2
                
                magnitude = max(1.0, abs(val))
                
                scale = base_height + (np.log10(magnitude) * growth_factor)
                
                if scale > 1.5: scale = 1.5 


                sign = 1 if val > 0 else -1
                
                if load.coord_system == "Local":
                    if axis_idx == 0: load_vec = v1_ax 
                    elif axis_idx == 1: load_vec = v2_ax
                    elif axis_idx == 2: load_vec = v3_ax
                    c_fill_sel, c_line, c_ghost = c_local_sel_fill, c_local_line, c_local_ghost
                else:         
                    load_vec = np.zeros(3); load_vec[axis_idx] = 1.0  
                    if axis_idx == 2 and sign < 0:
                        c_fill_sel, c_line, c_ghost = c_grav_sel_fill, c_grav_line, c_grav_ghost
                    else:
                        c_fill_sel, c_line, c_ghost = c_other_sel_fill, c_other_line, c_other_ghost

                offset_vec = -1 * sign * load_vec * scale 
                cross_prod = np.cross(beam_dir, load_vec)
                is_parallel = np.linalg.norm(cross_prod) < 0.01
                visual_shift = np.zeros(3)
                if is_parallel: visual_shift = v2_ax * 0.5 

                pt_base_1 = p1 + visual_shift
                pt_base_2 = p2 + visual_shift
                pt_top_1  = p1 + offset_vec + visual_shift
                pt_top_2  = p2 + offset_vec + visual_shift


                if not is_selected:
                    ghost_verts.extend([pt_base_1, pt_base_2, pt_top_2, pt_top_1])
                    idx = ghost_idx_counter
                    ghost_faces.append([idx, idx+1, idx+2])
                    ghost_faces.append([idx, idx+2, idx+3])
                    for _ in range(4): ghost_colors.append(c_ghost)
                    ghost_idx_counter += 4
                    continue 

                sel_verts.extend([pt_base_1, pt_base_2, pt_top_2, pt_top_1])
                idx = sel_idx_counter
                sel_faces.append([idx, idx+1, idx+2])
                sel_faces.append([idx, idx+2, idx+3])
                for _ in range(4): sel_colors.append(c_fill_sel)
                sel_idx_counter += 4

                sel_lines.extend([pt_top_1, pt_top_2, pt_top_1, pt_base_1, pt_top_2, pt_base_2])
                for _ in range(6): sel_line_colors.append(c_line)

                if is_parallel: spread_vec = np.cross(beam_dir, visual_shift)
                else: spread_vec = cross_prod
                if np.linalg.norm(spread_vec) > 0:
                    spread_vec = (spread_vec / np.linalg.norm(spread_vec)) * 0.2
                else: spread_vec = np.array([0.2, 0, 0])

                def draw_arrow(tip_pos, direction, color):
                    arrow_length = 1.2
                    head_size = 0.45
                    tail = tip_pos + direction * arrow_length
                    sel_lines.extend([tail, tip_pos])
                    sel_line_colors.extend([color, color])
                    
                    if abs(direction[2]) > 0.9:
                        perp = np.array([1.0, 0.0, 0.0])
                    else:
                        perp = np.array([0.0, 0.0, 1.0])
                    
                    side_vec = np.cross(direction, perp)
                    side_vec = (side_vec / np.linalg.norm(side_vec)) * head_size
                    
                    base = tip_pos + direction * head_size
                    sel_lines.extend([tip_pos, base + side_vec])
                    sel_lines.extend([tip_pos, base - side_vec])
                    sel_line_colors.extend([color, color, color, color])

                arrow_dir = -sign * load_vec 


                pt_mid = (pt_base_1 + pt_base_2) / 2
                draw_arrow(pt_mid, arrow_dir, c_line)

                draw_arrow(pt_base_1, arrow_dir, c_line)
                draw_arrow(pt_base_2, arrow_dir, c_line)


                display_val = val * unit_registry.force_scale / unit_registry.length_scale
                unit_str = unit_registry.distributed_load_unit
                mid_height = (pt_top_1 + pt_top_2) / 2
                
                self.load_labels.append({
                    'pos_3d': mid_height.tolist(),                               
                    'text': f"{display_val:.2f} {unit_str}",  
                    'color': c_line                                         
                })

        if ghost_verts:
            mesh_ghost = gl.GLMeshItem(
                vertexes=np.array(ghost_verts, dtype=np.float32),
                faces=np.array(ghost_faces, dtype=np.int32),
                vertexColors=np.array(ghost_colors, dtype=np.float32),
                smooth=False, shader='balloon', glOptions='translucent'
            )
            self.addItem(mesh_ghost)
            self.element_items.append(mesh_ghost)

        if sel_verts:
            mesh_sel = gl.GLMeshItem(
                vertexes=np.array(sel_verts, dtype=np.float32),
                faces=np.array(sel_faces, dtype=np.int32),
                vertexColors=np.array(sel_colors, dtype=np.float32),
                smooth=False, shader='balloon', glOptions='translucent'
            )
            self.addItem(mesh_sel)
            self.element_items.append(mesh_sel) 

        if sel_lines:
            lines = gl.GLLinePlotItem(
                pos=np.array(sel_lines), color=np.array(sel_line_colors), 
                mode='lines', width=2, antialias=True
            )
            self.addItem(lines)
            self.element_items.append(lines)


    def _draw_local_axes(self, model):
        """Draws RGB arrows at the center of each element representing local axes."""
        if not model.elements: return
        
        lines = []
        colors = []
        
        L = 0.5                                          
        
        for el in model.elements.values():
            n1, n2 = el.node_i, el.node_j
            
            if not (self._is_visible(n1.x, n1.y, n1.z) and self._is_visible(n2.x, n2.y, n2.z)):
                continue

            p1 = np.array([n1.x, n1.y, n1.z])
            p2 = np.array([n2.x, n2.y, n2.z])
            mid = (p1 + p2) / 2.0
            
            v1, v2, v3 = self._get_consistent_axes(el)
            
            lines.append(mid); lines.append(mid + v1 * L)
            colors.append((1, 0, 0, 1)); colors.append((1, 0, 0, 1))
            
            lines.append(mid); lines.append(mid + v2 * L)
            colors.append((0, 1, 0, 1)); colors.append((0, 1, 0, 1))
            
            lines.append(mid); lines.append(mid + v3 * L)
            colors.append((0, 0, 1, 1)); colors.append((0, 0, 1, 1))
            
        if lines:
            self.addItem(gl.GLLinePlotItem(
                pos=np.array(lines), 
                color=np.array(colors), 
                mode='lines', 
                width=2.0, 
                antialias=True
            ))

    def _draw_constraints(self, model):
        """
        Draws the Calculated Center of Mass (Master Node) for Diaphragms.
        Visualizes them as a Green Square with lines to connected nodes.
        """
        if not model.nodes: return

        groups = {}
        for n in model.nodes.values():
            if n.diaphragm_name:
                if n.diaphragm_name not in groups:
                    groups[n.diaphragm_name] = []
                groups[n.diaphragm_name].append(n)

        if not groups: return

        master_pos = []
        conn_lines = []
        
        for name, nodes in groups.items():
            if not nodes: continue
            
            cx = sum(n.x for n in nodes) / len(nodes)
            cy = sum(n.y for n in nodes) / len(nodes)
            cz = sum(n.z for n in nodes) / len(nodes)
            
            c_pt = [cx, cy, cz]
            master_pos.append(c_pt)
            
            for n in nodes:
                                  
                if self._is_visible(n.x, n.y, n.z):
                    conn_lines.append(c_pt)
                    conn_lines.append([n.x, n.y, n.z])

        if master_pos:
            self.addItem(gl.GLScatterPlotItem(
                pos=np.array(master_pos), 
                size=15,                    
                color=(0, 1, 0, 1),                
                pxMode=True                                                            
            ))

        if conn_lines:
            self.addItem(gl.GLLinePlotItem(
                pos=np.array(conn_lines),
                color=(0, 1, 0, 0.5),                         
                mode='lines',
                width=1.0,
                antialias=True
            ))

    def _draw_member_point_loads(self, model):
        """
        Visualizes Member Point Loads.
        - Always: Draws Arrow geometry (Force or Moment).
        - Selected: Draws Text Label with Units.
        """
        if not model.loads: return
        if not self.show_loads: return
        if self.load_type_filter == "nodal": return 

        arrow_lines = []
        arrow_colors = []
        
        L = 2.0; H = 0.5; W = 0.2

        for load in model.loads:

            if not hasattr(load, 'force'): continue 
            if self.visible_load_patterns and load.pattern_name not in self.visible_load_patterns: continue

            el = model.elements.get(load.element_id)
            if not el: continue
            
            v1 = self._get_visibility_state(el.node_i.x, el.node_i.y, el.node_i.z)
            v2 = self._get_visibility_state(el.node_j.x, el.node_j.y, el.node_j.z)
            if v1 != 2 or v2 != 2: continue

            is_selected = (el.id in self.selected_element_ids)

            p1 = np.array([el.node_i.x, el.node_i.y, el.node_i.z])
            p2 = np.array([el.node_j.x, el.node_j.y, el.node_j.z])
            beam_vec = p2 - p1
            beam_len = np.linalg.norm(beam_vec)
            if beam_len == 0: continue
            
            actual_dist = load.dist * beam_len if load.is_relative else load.dist
            load_pos = p1 + (beam_vec / beam_len) * actual_dist
            
            dir_vec = np.array([0.0, 0.0, 0.0])
            if load.coord_system == "Global":
                if "Gravity" in load.direction: dir_vec = np.array([0, 0, -1])
                elif "X" in load.direction: dir_vec = np.array([1, 0, 0])
                elif "Y" in load.direction: dir_vec = np.array([0, 1, 0])
                elif "Z" in load.direction: dir_vec = np.array([0, 0, 1])
            else:
                v1, v2, v3 = self._get_consistent_axes(el)
                if "1" in load.direction: dir_vec = v1
                elif "2" in load.direction: dir_vec = v2
                elif "3" in load.direction: dir_vec = v3

            val = load.force
            if val == 0: continue
            
            draw_dir = dir_vec * (1.0 if val > 0 else -1.0)
            norm = np.linalg.norm(draw_dir)
            if norm > 0: draw_dir /= norm
            
            is_moment = hasattr(load, 'load_type') and load.load_type == "Moment"
            
            c = (0, 0, 0, 1)   

            tip = load_pos
            tail = tip - (draw_dir * L)
            arrow_lines.append(tail); arrow_lines.append(tip)
            arrow_colors.append(c); arrow_colors.append(c)

            def add_head(base_pt):
                if abs(draw_dir[2]) > 0.9: perp = np.array([1.0, 0.0, 0.0])
                elif abs(draw_dir[1]) > 0.9: perp = np.array([1.0, 0.0, 0.0])
                else: perp = np.array([0.0, 0.0, 1.0])
                w_vec = perp * W
                base = base_pt - (draw_dir * H)
                arrow_lines.append(base_pt); arrow_lines.append(base + w_vec)
                arrow_lines.append(base_pt); arrow_lines.append(base - w_vec)
                for _ in range(4): arrow_colors.append(c)

            add_head(tip)
            if is_moment:
                add_head(tip - (draw_dir * (H * 0.8)))

            if is_selected:
                self._add_load_label(load_pos, draw_dir, val, "Moment" if is_moment else "Force", c)

        if arrow_lines:
            self.addItem(gl.GLLinePlotItem(
                pos=np.array(arrow_lines), 
                color=np.array(arrow_colors), 
                mode='lines', width=2.0, antialias=True
            ))


    def show_pivot_dot(self, visible=True):
        if visible:
                                               
            c = self.opts['center']
            self.pivot_dot.setData(pos=np.array([[c.x(), c.y(), c.z()]]))
            self.pivot_dot.setVisible(True)
            self.pivot_timer.start(500)                                  
        else:
            self.pivot_dot.setVisible(False)

    def _get_consistent_axes(self, el):
        """
        Unified logic to calculate local axes (v1, v2, v3) for 
        Extrusions, Arrows, and Loads. Ensures visual consistency.
        """
        n1, n2 = el.node_i, el.node_j
        p1 = np.array([n1.x, n1.y, n1.z])
        p2 = np.array([n2.x, n2.y, n2.z])
        
        vx = p2 - p1
        L = np.linalg.norm(vx)
        if L < 1e-6: return np.eye(3)                    
        vx /= L
        
        if np.isclose(abs(vx[2]), 1.0): 
             up = np.array([1.0, 0.0, 0.0]) 
        else:
             up = np.array([0.0, 0.0, 1.0])

        vy = np.cross(up, vx)
        vy /= np.linalg.norm(vy)
        
        vz = np.cross(vx, vy)
        vz /= np.linalg.norm(vz)
        
        beta = getattr(el, 'beta_angle', 0.0)
        if beta != 0:
            rad = np.radians(beta)
            c = np.cos(rad); s = np.sin(rad)
                                  
            vy_rot = c * vy + s * vz
            vz_rot = -s * vy + c * vz
            vy, vz = vy_rot, vz_rot
            
        return vx, vy, vz

    def invalidate_deflection_cache(self):
        """
        Clears the deflection cache when results or settings change.
        Call this when:
        - New analysis results loaded
        - Deflection scale changed
        - Model geometry changes
        """
        self.deflection_cache.clear()
        self.cache_scale_used = None
        
        self.invalidate_animation_cache()

    def _smart_redraw(self):
        """
        Efficiently updates only the selection-dependent items.
        Used by blink timer to avoid full scene rebuild.
        """
        if not self.current_model:
            return
        
        current_state = {
            'nodes': self.selected_node_ids[:],
            'elements': self.selected_element_ids[:],
            'blink': self.blink_state
        }
        
        if current_state == self.last_selection_state:
            return
        
        self.last_selection_state = current_state
        
        for item in self.node_items:
            try: self.removeItem(item)
            except: pass                         
            
        for item in self.element_items:
            try: self.removeItem(item)
            except: pass 
        
        self.node_items.clear()
        self.element_items.clear()
        
        if self.show_joints or self.show_supports:
            self._draw_nodes(self.current_model)
        
        if not self.view_deflected:
            if self.view_extruded:
                self._draw_elements_extruded(self.current_model)
            else:
                self._draw_elements_wireframe(self.current_model)

    
    def paintGL(self, *args, **kwargs):
        super().paintGL()
        
        try:
            w = self.width()
            h = self.height()
            ratio = self.devicePixelRatio() if hasattr(self, 'devicePixelRatio') else 1.0
            az = self.opts.get('azimuth', 45)
            el = self.opts.get('elevation', 30)
            self.view_cube.render(w, h, az, el, device_pixel_ratio=ratio)
        except Exception as e:
            print(f"ViewCube Error: {e}")