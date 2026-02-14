from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import math

class ViewCube:
    def __init__(self):
        self.size = 100
        self.margin = 30
        self.position = "TOP_RIGHT"
    
        self.face_colors = {
            "TOP":    [(0.98, 0.98, 0.98), (0.90, 0.90, 0.90)], 
            "BOTTOM": [(0.70, 0.70, 0.70), (0.60, 0.60, 0.60)],
            "FRONT":  [(0.94, 0.94, 0.94), (0.84, 0.84, 0.84)], 
            "BACK":   [(0.75, 0.75, 0.75), (0.65, 0.65, 0.65)], 
            "RIGHT":  [(0.90, 0.90, 0.90), (0.80, 0.80, 0.80)],
            "LEFT":   [(0.73, 0.73, 0.73), (0.63, 0.63, 0.63)]  
        }
        
        self.vertices = [
            [-1, -1, -1], [ 1, -1, -1], [ 1,  1, -1], [-1,  1, -1],
            [-1, -1,  1], [ 1, -1,  1], [ 1,  1,  1], [-1,  1,  1]
        ]
        
        self.faces = {
            "TOP":    ([4, 5, 6, 7], (0, 0, 1)),
            "BOTTOM": ([0, 3, 2, 1], (0, 0, -1)),
            "FRONT":  ([0, 1, 5, 4], (0, -1, 0)),
            "BACK":   ([2, 3, 7, 6], (0, 1, 0)),
            "RIGHT":  ([1, 2, 6, 5], (1, 0, 0)),
            "LEFT":   ([0, 4, 7, 3], (-1, 0, 0))
        }

    def render(self, width, height, azimuth, elevation, device_pixel_ratio=1.0):
        phys_w = int(width * device_pixel_ratio)
        phys_h = int(height * device_pixel_ratio)
        size_px = int(self.size * device_pixel_ratio)
        margin_px = int(self.margin * device_pixel_ratio)

        if phys_w <= 0 or phys_h <= 0:
            return
        if self.position == "TOP_RIGHT":
            x_pos, y_pos = phys_w - size_px - margin_px, phys_h - size_px - margin_px
        elif self.position == "TOP_LEFT":
            x_pos, y_pos = margin_px, phys_h - size_px - margin_px
        elif self.position == "BOTTOM_RIGHT":
            x_pos, y_pos = phys_w - size_px - margin_px, margin_px
        else:
            x_pos, y_pos = margin_px, margin_px

        # 2. Save State
        glPushAttrib(GL_ALL_ATTRIB_BITS)
        glPushClientAttrib(GL_CLIENT_ALL_ATTRIB_BITS)
        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()

        try:
            glUseProgram(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
            try: glBindVertexArray(0) 
            except: pass

            glDisable(GL_LIGHTING)
            glDisable(GL_TEXTURE_2D)
            glEnable(GL_DEPTH_TEST)
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
            glEnable(GL_LINE_SMOOTH)
            glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

            glViewport(x_pos, y_pos, size_px, size_px)
            glMatrixMode(GL_PROJECTION)
            glLoadIdentity()
            gluPerspective(22, 1.0, 1.0, 100.0)
            
            glMatrixMode(GL_MODELVIEW)
            glLoadIdentity()
            
            rad_az = math.radians(azimuth - 90)
            rad_el = math.radians(elevation)
            dist = 11.0
            
            eye_x = dist * math.cos(rad_el) * math.cos(rad_az)
            eye_y = dist * math.cos(rad_el) * math.sin(rad_az)
            eye_z = dist * math.sin(rad_el)
            
            up_vector = (0, 1, 0) if abs(elevation) > 88.0 else (0, 0, 1)
            gluLookAt(eye_x, eye_y, eye_z, 0, 0, 0, *up_vector)
            
            self._draw_background()
            
            self._draw_compass()
            
            self._draw_shadow()
            
            view_vec = (-eye_x, -eye_y, -eye_z) 
            self._draw_cube(view_vec)
            
            glFlush()

        except Exception as e:
            print(f"ViewCube Error: {e}")

        finally:
            glMatrixMode(GL_PROJECTION)
            glPopMatrix()
            glMatrixMode(GL_MODELVIEW)
            glPopMatrix()
            glPopClientAttrib()
            glPopAttrib()
            glViewport(0, 0, phys_w, phys_h)

    def _draw_background(self):
        glDisable(GL_DEPTH_TEST)
        glBegin(GL_TRIANGLE_FAN)
        glColor4f(0.98, 0.98, 0.98, 0.5)
        glVertex3f(0, 0, -1)
        
        radius = 2.2
        segments = 60
        for i in range(segments + 1):
            angle = 2.0 * math.pi * i / segments
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            glColor4f(0.95, 0.95, 0.95, 0.0)
            glVertex3f(x, y, -1)
        glEnd()
        glEnable(GL_DEPTH_TEST)

    def _draw_compass(self):
        """Draws a subtle ring with a North indicator below the cube"""
        glLineWidth(1.5)
        radius = 1.6
        z_level = -1.3
        
        glBegin(GL_LINE_LOOP)
        glColor4f(0.6, 0.6, 0.6, 0.5)
        for i in range(60):
            angle = 2.0 * math.pi * i / 60
            glVertex3f(radius * math.cos(angle), radius * math.sin(angle), z_level)
        glEnd()
        
        glBegin(GL_TRIANGLES)
        glColor4f(0.9, 0.3, 0.3, 0.9) 

        glVertex3f(0, radius + 0.3, z_level)

        glVertex3f(-0.15, radius, z_level)
        glVertex3f( 0.15, radius, z_level)
        glEnd()
        
        # Cardinal Ticks
        glBegin(GL_LINES)
        glColor4f(0.6, 0.6, 0.6, 0.5)
        dirs = [(radius, 0), (-radius, 0), (0, -radius)] # E, W, S
        for dx, dy in dirs:
            glVertex3f(dx, dy, z_level)
            glVertex3f(dx * 0.9, dy * 0.9, z_level)
        glEnd()

    def _draw_shadow(self):
        """Draws a fake ambient occlusion shadow below the cube"""
        glDisable(GL_DEPTH_TEST) 
        glBegin(GL_TRIANGLE_FAN)
        glColor4f(0.1, 0.1, 0.1, 0.15) 
        glVertex3f(0, 0, -1.25)
        
        for i in range(21):
            angle = 2.0 * math.pi * i / 20
            x = 1.2 * math.cos(angle)
            y = 1.2 * math.sin(angle)
            glColor4f(0.1, 0.1, 0.1, 0.0) 
            glVertex3f(x, y, -1.25)
        glEnd()
        glEnable(GL_DEPTH_TEST)

    def _draw_cube(self, view_vec):
        glClear(GL_DEPTH_BUFFER_BIT)
        
        vl = math.sqrt(view_vec[0]**2 + view_vec[1]**2 + view_vec[2]**2)
        vx, vy, vz = view_vec[0]/vl, view_vec[1]/vl, view_vec[2]/vl
        
        for label, (indices, normal) in self.faces.items():
            colors = self.face_colors[label]
            
            dot = normal[0]*vx + normal[1]*vy + normal[2]*vz
            facing_factor = max(0.0, dot)
            
            light_intensity = 0.6 + (0.4 * facing_factor)
            
            glBegin(GL_QUADS)
            for i, idx in enumerate(indices):
                c = colors[0] if i < 2 else colors[1]
                
                highlight = 1.1 if facing_factor > 0.9 else 1.0
                
                glColor4f(
                    min(1.0, c[0] * light_intensity * highlight), 
                    min(1.0, c[1] * light_intensity * highlight), 
                    min(1.0, c[2] * light_intensity * highlight), 
                    0.5
                )
                glVertex3fv(self.vertices[idx])
            glEnd()
        
        glLineWidth(2.0)
        glColor4f(0.35, 0.35, 0.35, 0.6) 
        glBegin(GL_LINES)
        edges = [
            (0,1), (1,2), (2,3), (3,0),
            (4,5), (5,6), (6,7), (7,4),
            (0,4), (1,5), (2,6), (3,7)
        ]
        for s, e in edges:
            glVertex3fv(self.vertices[s])
            glVertex3fv(self.vertices[e])
        glEnd()

    def check_click(self, mouse_x, mouse_y, width, height):
        if self.position == "TOP_RIGHT":
            rect_x = width - self.size - self.margin
            rect_y = self.margin
        elif self.position == "TOP_LEFT":
            rect_x = self.margin
            rect_y = self.margin
        elif self.position == "BOTTOM_RIGHT":
            rect_x = width - self.size - self.margin
            rect_y = height - self.size - self.margin
        else:
            rect_x = self.margin
            rect_y = height - self.size - self.margin
            
        return (rect_x <= mouse_x <= rect_x + self.size) and \
               (rect_y <= mouse_y <= rect_y + self.size)