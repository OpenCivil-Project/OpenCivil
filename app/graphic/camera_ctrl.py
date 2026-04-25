import numpy as np
from PyQt6.QtGui import QVector3D
from PyQt6.QtCore import Qt, QTimer, QVariantAnimation, QEasingCurve
import math

class ArcballCamera:
    def __init__(self, view_widget):
        self.view = view_widget

        self._model_scale = 1.0                                              

        self.anim = QVariantAnimation()
        self.anim.setDuration(420)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.valueChanged.connect(self._on_anim_step)

        self.is_rotating = False

        self.single_use_pan_active = False

    def set_model_scale(self, scale: float):
        """
        Call this whenever the model geometry changes.
        `scale` = bounding-box diagonal length in the same world units the
        canvas uses (metres, mm, ft …).  This drives all adaptive thresholds
        so the camera feels identical for a 1 mm wire and a 200 m skyscraper.
        """
        self._model_scale = max(float(scale), 1e-6)

    def rotate(self, dx, dy):
        """
        Orbit around the current center point.

        Sensitivity is fixed in screen-pixels → degrees so the orbit always
        feels the same speed regardless of zoom level.  Elevation is hard-
        clamped to ±89 ° so the camera can never flip upside-down.
        """
        SENSITIVITY = 0.35                                                  

        new_el = self.view.opts['elevation'] + dy * SENSITIVITY
        self.view.opts['elevation'] = max(-89.999, min(89.999, new_el))
        self.view.opts['azimuth'] -= dx * SENSITIVITY
        self.view.update()

        if hasattr(self.view, 'show_pivot_dot'):
            self.view.show_pivot_dot(True)

    def pan(self, dx, dy, width, height):
        """
        True CAD pan: moves the orbit center parallel to the camera plane.
        Speed is proportional to what is currently visible so it never
        over- or under-shoots regardless of zoom level or model scale.
        """
        dist = self.view.opts['distance']
        fov  = self.view.opts['fov']

        if fov == 0:
            visible_h = dist
        else:
            visible_h = 2.0 * dist * math.tan(math.radians(fov) / 2.0)

        scale = visible_h / height                                 

        forward   = self._view_direction()
        global_up = QVector3D(0, 0, 1) if abs(forward.z()) < 0.95\
                    else QVector3D(0, 1, 0)

        right    = QVector3D.crossProduct(forward, global_up).normalized()
        up       = QVector3D.crossProduct(right, forward).normalized()

        move_vec = (right * (-dx * scale)) + (up * (dy * scale))
        self.view.opts['center'] += move_vec
        self.view.update()

    def zoom(self, delta, mouse_x, mouse_y, width, height):
        """
        Zoom toward/away from the cursor position.

        Two adaptive thresholds based on model scale:
          • min_dist  – the camera never gets closer than 2 % of the model
                        bounding box, preventing it from clipping inside.
          • fly_thresh – below this distance the camera 'flies through'
                         by advancing the center point, just like SAP2000.
        """
        dist   = self.view.opts['distance']
        center = self.view.opts['center']

        min_dist   = self._model_scale * 0.02                      
        fly_thresh = self._model_scale * 0.12                       

        if dist < fly_thresh and delta > 0:
            view_vec = self._view_direction()
            step = max(dist * 0.15, min_dist * 0.5)                      
            self.view.opts['center'] = center + (view_vec * step)
            self.view.update()
            return

        factor = 0.88 if delta > 0 else 1.14

        fov = self.view.opts['fov']
        if fov == 0:
            view_h = dist
        else:
            view_h = 2.0 * dist * math.tan(math.radians(fov) / 2.0)
        view_w = view_h * (width / height)

        off_x =  (mouse_x / width)  - 0.5
        off_y = -((mouse_y / height) - 0.5)

        forward   = self._view_direction()
        global_up = QVector3D(0, 0, 1) if abs(forward.z()) < 0.95\
                    else QVector3D(0, 1, 0)
        right = QVector3D.crossProduct(forward, global_up).normalized()
        up    = QVector3D.crossProduct(right, forward).normalized()

        shift = 1.0 - factor
        move_vec = (right * (off_x * view_w * shift)) +\
                   (up    * (off_y * view_h * shift))

        self.view.opts['center']  += move_vec
        new_dist = dist * factor
        self.view.opts['distance'] = max(new_dist, min_dist)                   
        self.view.update()

    def animate_to(self, target_center=None, target_dist=None,
                   target_az=None, target_el=None):
        """Smoothly interpolate the camera to a new state."""
        self.anim.stop()

        self.anim_start = {
            'c': self.view.opts['center'],
            'd': self.view.opts['distance'],
            'a': self.view.opts['azimuth'],
            'e': self.view.opts['elevation'],
        }
        self.anim_end = {
            'c': target_center if target_center is not None else self.anim_start['c'],
            'd': target_dist   if target_dist   is not None else self.anim_start['d'],
            'a': target_az     if target_az     is not None else self.anim_start['a'],
            'e': target_el     if target_el     is not None else self.anim_start['e'],
        }

        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()

    def _view_direction(self) -> QVector3D:
        """Unit vector pointing FROM camera TO scene center."""
        az = np.radians(self.view.opts['azimuth'])
        el = np.radians(self.view.opts['elevation'])
        x  = np.cos(el) * np.cos(az)
        y  = np.cos(el) * np.sin(az)
        z  = np.sin(el)
        return QVector3D(-x, -y, -z)

    def get_view_direction(self) -> QVector3D:
        return self._view_direction()

    def _on_anim_step(self, t):
        s, e = self.anim_start, self.anim_end
        self.view.opts['center']    = s['c'] + (e['c'] - s['c']) * t
        self.view.opts['distance']  = s['d'] + (e['d'] - s['d']) * t
        self.view.opts['azimuth']   = s['a'] + (e['a'] - s['a']) * t
        self.view.opts['elevation'] = s['e'] + (e['e'] - s['e']) * t
        self.view.update()
