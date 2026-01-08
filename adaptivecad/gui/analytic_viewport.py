"""Analytic SDF OpenGL viewport & control panel (PySide6 version).

Refactored to standardize on PySide6 (no PyQt6 mixing) and allow
injection of a shared AACore analytic scene so multiple view components
can operate on the same underlying primitive set.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider,
    QComboBox, QCheckBox, QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox,
    QScrollArea, QSizePolicy, QInputDialog, QToolButton, QGridLayout,
    QTextEdit, QLineEdit, QListWidget, QListWidgetItem, QFileDialog,
    QMessageBox, QProgressDialog,
    QMainWindow, QDockWidget, QTabWidget, QPlainTextEdit,
    QTableWidget, QTableWidgetItem
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtGui import QSurfaceFormat, QMouseEvent, QWheelEvent, QPainter, QPen, QColor
from PySide6.QtCore import Qt, QSize, QTimer, Signal, QThread
from PySide6.QtGui import QGuiApplication
from OpenGL.GL import *
import numpy as np
from pathlib import Path
from adaptivecad.sketch.model import SketchDocument
from adaptivecad.sketch.units import Units
from adaptivecad.aacore.sdf import (
    Scene as AACoreScene, Prim, KIND_SPHERE, KIND_BOX, KIND_CAPSULE, KIND_TORUS,
    KIND_MOBIUS, KIND_SUPERELLIPSOID, KIND_QUASICRYSTAL, KIND_TORUS4D, KIND_MANDELBULB, KIND_KLEIN, KIND_MENGER, KIND_HYPERBOLIC, KIND_GYROID, KIND_TREFOIL, OP_SOLID, OP_SUBTRACT, MAX_PRIMS
)
import time, os
import sys
import json
import importlib.util
import ctypes
from functools import partial, lru_cache
import logging
log = logging.getLogger("adaptivecad.gui")
try:
    from adaptivecad.ai.intent_router import CADActionBus, chat_with_tools
    from adaptivecad.geometry.pia_primitives import (
        make_pi_circle_profile,
        upgrade_profile_meta_to_pia,
        pi_circle_points,
    )
    _HAVE_AI = True
except Exception:
    CADActionBus = None  # type: ignore
    chat_with_tools = None  # type: ignore
    make_pi_circle_profile = None  # type: ignore
    upgrade_profile_meta_to_pia = None  # type: ignore
    pi_circle_points = None  # type: ignore
    _HAVE_AI = False

try:
    from adaptivecad.plugins.tool_registry import ToolRegistry
except Exception:
    ToolRegistry = None  # type: ignore
try:
    from PIL import Image  # type: ignore
    _HAVE_PIL = True
except Exception:
    _HAVE_PIL = False

# Optional radial tool wheel overlay (used as a HUD over the viewport)
try:
    from adaptivecad.ui.radial_tool_wheel import RadialToolWheelOverlay, ToolSpec
    _HAVE_WHEEL = True
except Exception:
    RadialToolWheelOverlay = None  # type: ignore
    ToolSpec = None  # type: ignore
    _HAVE_WHEEL = False

_CUPY_INIT_ERROR: str | None = None


@lru_cache(maxsize=1)
def _cupy_available() -> bool:
    try:
        global _CUPY_INIT_ERROR
        if importlib.util.find_spec("cupy") is None:
            _CUPY_INIT_ERROR = "CuPy package not found"
            return False
        if sys.platform.startswith("win"):
            try:
                # Ensure nvrtc64_120_0.dll and friends from the pip CUDA runtimes are discoverable
                candidate_specs = [
                    importlib.util.find_spec("nvidia.cuda_runtime"),
                    importlib.util.find_spec("nvidia.cuda_nvrtc"),
                ]
                for spec in candidate_specs:
                    if not spec or not spec.origin:
                        continue
                    base = Path(spec.origin).resolve().parent
                    for sub in ("bin", "lib", "Lib", "DLLs"):
                        dll_dir = base / sub
                        if dll_dir.exists():
                            try:
                                os.add_dll_directory(str(dll_dir))
                            except Exception:
                                pass
            except Exception:
                pass
        import cupy  # type: ignore

        cupy.zeros((1,), dtype=cupy.float32)  # minimal allocation to confirm runtime
        _CUPY_INIT_ERROR = None
        return True
    except Exception as exc:
        _CUPY_INIT_ERROR = str(exc)
        try:
            log.debug("CuPy unavailable: %s", _CUPY_INIT_ERROR)
        except Exception:
            pass
        return False

    # --- 2D Sketch Overlay (Polyline + Snaps) ---------------------------------
    SNAP_PX = 10  # pixel radius for snapping

    class SketchEntity:
        def __init__(self):
            self.construction = False
        def draw(self, p: QPainter, view): ...
        def snap_points(self): return []  # list of (x,y) in world (Z=0)
        def snap_points_typed(self):
            return [(pt, 'other') for pt in self.snap_points()]

    class Polyline2D(SketchEntity):
        def __init__(self, pts=None):
            import numpy as _np
            super().__init__()
            self.pts = [ _np.array(p, dtype=_np.float32) for p in (pts or []) ]  # (x,y)
            self.closed = False
        def snap_points(self):
            import numpy as _np
            out = []
            out += self.pts
            for a,b in zip(self.pts[:-1], self.pts[1:]):
                out.append( (a+b)/2.0 )
            if self.closed and len(self.pts) >= 2:
                a = self.pts[-1]; b = self.pts[0]
                out.append((a+b)/2.0)
            return out
        def snap_points_typed(self):
            out=[]
            if self.pts:
                out.append((self.pts[0],'end'))
                if len(self.pts)>1:
                    out.append((self.pts[-1],'end'))
            for a,b in zip(self.pts[:-1], self.pts[1:]):
                out.append(((a+b)/2.0, 'mid'))
            if self.closed and len(self.pts)>=2:
                a=self.pts[-1]; b=self.pts[0]
                out.append(((a+b)/2.0, 'mid'))
            return out
        def draw(self, p: QPainter, view):
            import numpy as _np
            if not self.pts:
                return
            pts2 = [ view._world_to_screen(_np.array([x,y,0.0], _np.float32)) for (x,y) in self.pts ]
            if len(pts2) >= 2:
                pen = QPen(QColor(220,220,220)); pen.setWidth(2)
                if getattr(self,'construction',False): pen.setStyle(Qt.PenStyle.DashLine)
                p.setPen(pen)
                for a,b in zip(pts2[:-1], pts2[1:]):
                    p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
                if self.closed:
                    a=pts2[-1]; b=pts2[0]
                    p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            pen = QPen(QColor(255,200,120)); pen.setWidth(6); p.setPen(pen)
            for s in pts2: p.drawPoint(int(s[0]), int(s[1]))

    class Line2D(SketchEntity):
        def __init__(self, p0, p1=None):
            import numpy as _np
            super().__init__()
            self.p0 = _np.array(p0, dtype=_np.float32)
            self.p1 = _np.array(p1, dtype=_np.float32) if p1 is not None else None
        def snap_points(self):
            import numpy as _np
            pts = [self.p0]
            if self.p1 is not None:
                pts.append(self.p1)
                pts.append((self.p0 + self.p1)/2.0)
            return pts
        def draw(self, p: QPainter, view):
            import numpy as _np
            s0 = view._world_to_screen(_np.array([self.p0[0], self.p0[1], 0.0], _np.float32))
            pen = QPen(QColor(220,220,220)); pen.setWidth(2)
            if getattr(self,'construction',False): pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            if self.p1 is not None:
                s1 = view._world_to_screen(_np.array([self.p1[0], self.p1[1], 0.0], _np.float32))
                p.drawLine(int(s0[0]), int(s0[1]), int(s1[0]), int(s1[1]))
            pen = QPen(QColor(255,200,140)); pen.setWidth(6); p.setPen(pen); p.drawPoint(int(s0[0]), int(s0[1]))
            if self.p1 is not None:
                p.drawPoint(int(s1[0]), int(s1[1]))

    class Circle2D(SketchEntity):
        def __init__(self, center, radius=0.0):
            import numpy as _np
            super().__init__()
            self.center = _np.array(center, dtype=_np.float32)
            self.radius = float(radius)
        def snap_points(self):
            import numpy as _np, math as _m
            pts = [self.center]
            if self.radius > 1e-6:
                for ang in (0,90,180,270):
                    a = _m.radians(ang)
                    pts.append(self.center + self.radius * _np.array([_np.cos(a), _np.sin(a)], _np.float32))
            return pts
        def draw(self, p: QPainter, view):
            import numpy as _np, math as _m
            if self.radius <= 0: return
            segs = 40
            pts = []
            for i in range(segs+1):
                a = 2*_m.pi * i / segs
                w = self.center + self.radius * _np.array([_np.cos(a), _np.sin(a)], _np.float32)
                s = view._world_to_screen(_np.array([w[0], w[1], 0.0], _np.float32))
                pts.append(s)
            pen = QPen(QColor(180,220,255)); pen.setWidth(2)
            if getattr(self,'construction',False): pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            for a,b in zip(pts[:-1], pts[1:]):
                p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            # center point
            c = view._world_to_screen(_np.array([self.center[0], self.center[1], 0.0], _np.float32))
            pen = QPen(QColor(255,180,120)); pen.setWidth(6); p.setPen(pen); p.drawPoint(int(c[0]), int(c[1]))

    class Rect2D(SketchEntity):
        def __init__(self, p0, p1=None):
            import numpy as _np
            super().__init__()
            self.p0 = _np.array(p0, dtype=_np.float32)
            self.p1 = _np.array(p1, dtype=_np.float32) if p1 is not None else None
        def corners(self):
            import numpy as _np
            if self.p1 is None:
                return []
            x0,y0 = self.p0
            x1,y1 = self.p1
            mnx,mxx = min(x0,x1), max(x0,x1)
            mny,mxy = min(y0,y1), max(y0,y1)
            return [ _np.array([mnx,mny], _np.float32), _np.array([mxx,mny], _np.float32), _np.array([mxx,mxy], _np.float32), _np.array([mnx,mxy], _np.float32) ]
        def snap_points(self):
            import numpy as _np
            cs = self.corners()
            pts = cs[:]
            if len(cs)==4:
                # edge midpoints
                for a,b in zip(cs, cs[1:]+cs[:1]):
                    pts.append( (a+b)/2.0 )
                # center
                cx = sum(c[0] for c in cs)/4.0; cy = sum(c[1] for c in cs)/4.0
                pts.append(_np.array([cx,cy], _np.float32))
            return pts
        def draw(self, p: QPainter, view):
            import numpy as _np
            cs = self.corners()
            if len(cs) < 2:
                # just draw p0
                s0 = view._world_to_screen(_np.array([self.p0[0], self.p0[1], 0.0], _np.float32))
                pen = QPen(QColor(255,200,140)); pen.setWidth(6); p.setPen(pen); p.drawPoint(int(s0[0]), int(s0[1]))
                return
            pts2 = [ view._world_to_screen(_np.array([c[0], c[1], 0.0], _np.float32)) for c in cs ]
            pen = QPen(QColor(200,255,180)); pen.setWidth(2)
            if getattr(self,'construction',False): pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            for a,b in zip(pts2, pts2[1:]+pts2[:1]):
                p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            pen = QPen(QColor(255,200,140)); pen.setWidth(6); p.setPen(pen)
            for s in pts2:
                p.drawPoint(int(s[0]), int(s[1]))

    class Arc2D(SketchEntity):
        def __init__(self, p0=None, p1=None, p2=None):
            import numpy as _np
            super().__init__()
            self.p0 = _np.array(p0, dtype=_np.float32) if p0 is not None else None
            self.p1 = _np.array(p1, dtype=_np.float32) if p1 is not None else None
            self.p2 = _np.array(p2, dtype=_np.float32) if p2 is not None else None
        def _circle_from_3pts(self):
            import numpy as _np
            if self.p0 is None or self.p1 is None or self.p2 is None:
                return None
            x1,y1 = self.p0; x2,y2 = self.p1; x3,y3 = self.p2
            a = x1*(y2 - y3) - y1*(x2 - x3) + x2*y3 - x3*y2
            if abs(a) < 1e-9: return None
            b = (x1*x1 + y1*y1)*(y3 - y2) + (x2*x2 + y2*y2)*(y1 - y3) + (x3*x3 + y3*y3)*(y2 - y1)
            c = (x1*x1 + y1*y1)*(x2 - x3) + (x2*x2 + y2*y2)*(x3 - x1) + (x3*x3 + y3*y3)*(x1 - x2)
            cx = -b/(2*a); cy = -c/(2*a)
            r = float(_np.hypot(x1-cx, y1-cy))
            return _np.array([cx,cy], _np.float32), r
        def snap_points(self):
            import numpy as _np
            pts=[]
            if self.p0 is not None: pts.append(self.p0)
            if self.p2 is not None: pts.append(self.p2)
            circ = self._circle_from_3pts()
            if circ is not None:
                c,_ = circ; pts.append(c)
            if self.p0 is not None and self.p2 is not None:
                pts.append((self.p0 + self.p2)/2.0)
            return pts
        def draw(self, p: QPainter, view):
            import numpy as _np, math as _m
            if self.p0 is None:
                return
            pen=QPen(QColor(200,240,255)); pen.setWidth(2)
            if getattr(self,'construction',False): pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            if self.p1 is None or self.p2 is None:
                s0=view._world_to_screen(_np.array([self.p0[0], self.p0[1],0.0], _np.float32))
                p.drawPoint(int(s0[0]), int(s0[1]))
                if self.p1 is not None:
                    s1=view._world_to_screen(_np.array([self.p1[0], self.p1[1],0.0], _np.float32))
                    p.drawLine(int(s0[0]), int(s0[1]), int(s1[0]), int(s1[1]))
                return
            circ=self._circle_from_3pts()
            if circ is None:
                s0=view._world_to_screen(_np.array([self.p0[0], self.p0[1],0.0], _np.float32))
                s2=view._world_to_screen(_np.array([self.p2[0], self.p2[1],0.0], _np.float32))
                p.drawLine(int(s0[0]), int(s0[1]), int(s2[0]), int(s2[1]))
                return
            c,r=circ
            a0=_m.atan2(self.p0[1]-c[1], self.p0[0]-c[0])
            a1=_m.atan2(self.p1[1]-c[1], self.p1[0]-c[0])
            a2=_m.atan2(self.p2[1]-c[1], self.p2[0]-c[0])
            def ang_dist(a,b):
                d=(b-a+_m.pi)%(2*_m.pi)-_m.pi
                return d
            d1=abs(ang_dist(a0,a1))+abs(ang_dist(a1,a2))
            d2=abs(ang_dist(a0,a2))
            cw=False if d1<d2 else True
            segs=48; pts=[]
            if not cw:
                step=ang_dist(a0,a2)/segs; k=0
                while k<=segs:
                    ang=a0+step*k; k+=1
                    w=c+r*_np.array([_np.cos(ang), _np.sin(ang)], _np.float32)
                    s=view._world_to_screen(_np.array([w[0],w[1],0.0], _np.float32)); pts.append(s)
            else:
                step=ang_dist(a2,a0)/segs; k=0
                while k<=segs:
                    ang=a2+step*k; k+=1
                    w=c+r*_np.array([_np.cos(ang), _np.sin(ang)], _np.float32)
                    s=view._world_to_screen(_np.array([w[0],w[1],0.0], _np.float32)); pts.append(s)
            for a,b in zip(pts[:-1], pts[1:]): p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            pen_pts=QPen(QColor(255,200,140)); pen_pts.setWidth(6); p.setPen(pen_pts)
            s0=view._world_to_screen(_np.array([self.p0[0], self.p0[1],0.0], _np.float32)); p.drawPoint(int(s0[0]), int(s0[1]))
            s2=view._world_to_screen(_np.array([self.p2[0], self.p2[1],0.0], _np.float32)); p.drawPoint(int(s2[0]), int(s2[1]))
            sc=view._world_to_screen(_np.array([c[0], c[1],0.0], _np.float32)); p.drawPoint(int(sc[0]), int(sc[1]))

    class Line2D(SketchEntity):
        def __init__(self, p0, p1=None):
            import numpy as _np
            super().__init__()
            self.p0 = _np.array(p0, dtype=_np.float32)
            self.p1 = _np.array(p1, dtype=_np.float32) if p1 is not None else None
        def snap_points(self):
            import numpy as _np
            pts = [self.p0]
            if self.p1 is not None:
                pts.append(self.p1)
                pts.append((self.p0 + self.p1)/2.0)
            return pts
        def snap_points_typed(self):
            out=[(self.p0,'end')]
            if self.p1 is not None:
                out.append((self.p1,'end'))
                out.append(((self.p0+self.p1)/2.0,'mid'))
            return out
        def draw(self, p: QPainter, view):
            import numpy as _np
            s0 = view._world_to_screen(_np.array([self.p0[0], self.p0[1], 0.0], _np.float32))
            pen = QPen(QColor(220,220,220)); pen.setWidth(2)
            if getattr(self,'construction',False): pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            if self.p1 is not None:
                s1 = view._world_to_screen(_np.array([self.p1[0], self.p1[1], 0.0], _np.float32))
                p.drawLine(int(s0[0]), int(s0[1]), int(s1[0]), int(s1[1]))
            pen = QPen(QColor(255,200,140)); pen.setWidth(6); p.setPen(pen); p.drawPoint(int(s0[0]), int(s0[1]))
            if self.p1 is not None:
                p.drawPoint(int(s1[0]), int(s1[1]))

    class Arc2D(SketchEntity):
        def __init__(self, p0=None, p1=None, p2=None):
            import numpy as _np
            super().__init__()
            self.p0 = _np.array(p0, dtype=_np.float32) if p0 is not None else None
            self.p1 = _np.array(p1, dtype=_np.float32) if p1 is not None else None
            self.p2 = _np.array(p2, dtype=_np.float32) if p2 is not None else None
        def _circle_from_3pts(self):
            import numpy as _np
            if self.p0 is None or self.p1 is None or self.p2 is None:
                return None
            x1,y1 = self.p0; x2,y2 = self.p1; x3,y3 = self.p2
            a = x1*(y2 - y3) - y1*(x2 - x3) + x2*y3 - x3*y2
            if abs(a) < 1e-9: return None
            b = (x1*x1 + y1*y1)*(y3 - y2) + (x2*x2 + y2*y2)*(y1 - y3) + (x3*x3 + y3*y3)*(y2 - y1)
            c = (x1*x1 + y1*y1)*(x2 - x3) + (x2*x2 + y2*y2)*(x3 - x1) + (x3*x3 + y3*y3)*(x1 - x2)
            cx = -b/(2*a); cy = -c/(2*a)
            r = float(_np.hypot(x1-cx, y1-cy))
            return _np.array([cx,cy], _np.float32), r
        def snap_points(self):
            import numpy as _np
            pts=[]
            if self.p0 is not None: pts.append(self.p0)
            if self.p2 is not None: pts.append(self.p2)
            circ = self._circle_from_3pts()
            if circ is not None:
                c,_ = circ; pts.append(c)
            if self.p0 is not None and self.p2 is not None:
                pts.append((self.p0 + self.p2)/2.0)
            return pts
        def snap_points_typed(self):
            out=[]
            if self.p0 is not None: out.append((self.p0,'end'))
            if self.p2 is not None: out.append((self.p2,'end'))
            circ = self._circle_from_3pts()
            if circ is not None:
                c,_ = circ; out.append((c,'center'))
            if self.p0 is not None and self.p2 is not None:
                out.append(((self.p0+self.p2)/2.0,'mid'))
            return out
        def draw(self, p: QPainter, view):
            import numpy as _np, math as _m
            if self.p0 is None:
                return
            pen = QPen(QColor(200,240,255)); pen.setWidth(2)
            if getattr(self,'construction',False): pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            # if not complete, draw provisional segment(s)
            if self.p1 is None or self.p2 is None:
                s0 = view._world_to_screen(_np.array([self.p0[0], self.p0[1], 0.0], _np.float32))
                p.drawPoint(int(s0[0]), int(s0[1]))
                if self.p1 is not None:
                    s1 = view._world_to_screen(_np.array([self.p1[0], self.p1[1], 0.0], _np.float32))
                    p.drawLine(int(s0[0]), int(s0[1]), int(s1[0]), int(s1[1]))
                return
            circ = self._circle_from_3pts()
            if circ is None:
                # fallback draw polyline
                s0 = view._world_to_screen(_np.array([self.p0[0], self.p0[1], 0.0], _np.float32))
                s2 = view._world_to_screen(_np.array([self.p2[0], self.p2[1], 0.0], _np.float32))
                p.drawLine(int(s0[0]), int(s0[1]), int(s2[0]), int(s2[1]))
                return
            c, r = circ
            # compute angles
            a0 = _m.atan2(self.p0[1]-c[1], self.p0[0]-c[0])
            a1 = _m.atan2(self.p1[1]-c[1], self.p1[0]-c[0])
            a2 = _m.atan2(self.p2[1]-c[1], self.p2[0]-c[0])
            # pick direction that passes near a1 (shorter arc through a1)
            def ang_dist(a,b):
                d = (b - a + _m.pi) % (2*_m.pi) - _m.pi
                return d
            d1 = abs(ang_dist(a0, a1)) + abs(ang_dist(a1, a2))
            d2 = abs(ang_dist(a0, a2))
            cw = False if d1 < d2 else True
            # sample arc
            segs = 48
            pts=[]
            if not cw:
                step = ang_dist(a0, a2)/segs
                k = 0
                while k <= segs:
                    ang = a0 + step*k; k += 1
                    w = c + r * _np.array([_np.cos(ang), _np.sin(ang)], _np.float32)
                    s = view._world_to_screen(_np.array([w[0], w[1], 0.0], _np.float32))
                    pts.append(s)
            else:
                # reverse direction
                step = ang_dist(a2, a0)/segs
                k = 0
                while k <= segs:
                    ang = a2 + step*k; k += 1
                    w = c + r * _np.array([_np.cos(ang), _np.sin(ang)], _np.float32)
                    s = view._world_to_screen(_np.array([w[0], w[1], 0.0], _np.float32))
                    pts.append(s)
            for a,b in zip(pts[:-1], pts[1:]):
                p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            # endpoints & optional center point
            pen_pts = QPen(QColor(255,200,140)); pen_pts.setWidth(6); p.setPen(pen_pts)
            s0 = view._world_to_screen(_np.array([self.p0[0], self.p0[1], 0.0], _np.float32)); p.drawPoint(int(s0[0]), int(s0[1]))
            s2 = view._world_to_screen(_np.array([self.p2[0], self.p2[1], 0.0], _np.float32)); p.drawPoint(int(s2[0]), int(s2[1]))
            sc = view._world_to_screen(_np.array([c[0], c[1], 0.0], _np.float32)); p.drawPoint(int(sc[0]), int(sc[1]))

    class SketchLayer:
        def __init__(self):
            self.entities: list[SketchEntity] = []
            self.active_poly: Polyline2D | None = None
            self.active_shape: SketchEntity | None = None  # circle/rect WIP
            self.hover_snap = None  # (x,y)
            self.dimensions = []  # list of DimOverlay
            self._dim_pick = None  # first ref for dimension tools
            self._dim_preview = None  # transient preview overlay
            self._dim_placing = False  # after picking A and B, placing offset
            self._dim_place_data = None  # {'type': str, 'a': ref, 'b': ref}
        def all_snap_points(self):
            pts = []
            for e in self.entities:
                pts += e.snap_points()
            if self.active_poly:
                pts += self.active_poly.snap_points()
            if self.active_shape and hasattr(self.active_shape, 'snap_points'):
                pts += self.active_shape.snap_points()
            return pts
        def all_snap_points_typed(self):
            pts = []
            for e in self.entities:
                if hasattr(e,'snap_points_typed'):
                    pts += e.snap_points_typed()
                else:
                    pts += [(pt,'other') for pt in e.snap_points()]
            if self.active_poly:
                pts += self.active_poly.snap_points_typed()
            if self.active_shape and hasattr(self.active_shape, 'snap_points_typed'):
                pts += self.active_shape.snap_points_typed()
            return pts
        def draw(self, p: QPainter, view):
            import numpy as _np
            for e in self.entities:
                e.draw(p, view)
            if self.active_poly:
                self.active_poly.draw(p, view)
            if self.active_shape:
                self.active_shape.draw(p, view)
            # draw dimensions
            for d in getattr(self, 'dimensions', []):
                try:
                    d.draw(p, view)
                except Exception:
                    pass
            # draw preview dim if any
            try:
                if self._dim_preview is not None:
                    self._dim_preview.draw(p, view)
            except Exception:
                pass
            if self.hover_snap is not None:
                s = view._world_to_screen(_np.array([self.hover_snap[0], self.hover_snap[1], 0.0], _np.float32))
                pen = QPen(QColor(120,255,160)); pen.setWidth(2); p.setPen(pen)
                p.drawLine(int(s[0]-6), int(s[1]), int(s[0]+6), int(s[1]))
                p.drawLine(int(s[0]), int(s[1]-6), int(s[0]), int(s[1]+6))

    # --- Dimension overlays ---
    class DimBase2D:
        def __init__(self):
            self.label_override = None  # when set, displayed instead of measured
        def _fmt(self, val: float, panel) -> str:
            try:
                prec = int(getattr(panel, '_dim_precision', 2))
            except Exception:
                prec = 2
            return f"{val:.{prec}f}"
        def draw_text(self, p: QPainter, view, pos_xy, text):
            import numpy as _np
            s = view._world_to_screen(_np.array([pos_xy[0], pos_xy[1], 0.0], _np.float32))
            p.setPen(QPen(QColor(250, 250, 210)))
            p.drawText(int(s[0]+6), int(s[1]-6), text)

    class DimLinear2D(DimBase2D):
        def __init__(self, ref_a, ref_b, panel, offset: float = 0.0):
            super().__init__(); self.ref_a = ref_a; self.ref_b = ref_b; self.panel = panel; self.offset = float(offset)
        def _xy(self, ref):
            try:
                view = getattr(self.panel, 'view', None)
                if view is not None and hasattr(view, '_ref_to_xy'):
                    pt = view._ref_to_xy(ref)
                    if pt is not None:
                        return pt
            except Exception:
                pass
            if isinstance(ref, tuple) and len(ref)==2 and isinstance(ref[0], Polyline2D):
                ent, idx = ref
                if isinstance(idx, int) and 0 <= idx < len(ent.pts):
                    return ent.pts[idx]
            if isinstance(ref, tuple) and len(ref)==2 and isinstance(ref[0], Line2D):
                ent, key = ref
                if key == 0 and ent.p0 is not None:
                    return ent.p0
                if key == 1 and ent.p1 is not None:
                    return ent.p1
                if isinstance(key, (tuple, list)) and key and key[0] == 'mid' and ent.p1 is not None:
                    return (ent.p0 + ent.p1) * 0.5
            if isinstance(ref, tuple) and len(ref)==2 and isinstance(ref[0], Rect2D):
                ent, key = ref
                cs = ent.corners()
                if isinstance(key, int):
                    if 0 <= key < len(cs):
                        return cs[key]
                elif isinstance(key, (tuple, list)) and key:
                    tag = key[0]
                    if tag == 'edge_mid' and len(cs) >= 2:
                        try:
                            idx = int(key[1])
                        except Exception:
                            return None
                        if len(cs) == 0:
                            return None
                        a = cs[idx % len(cs)]
                        b = cs[(idx + 1) % len(cs)]
                        return (a + b) * 0.5
                elif key == 'center' and len(cs) == 4:
                    import numpy as _np
                    cx = sum(c[0] for c in cs) / 4.0
                    cy = sum(c[1] for c in cs) / 4.0
                    return _np.array([cx, cy], _np.float32)
            if isinstance(ref, tuple) and ref[0]=='circle' and isinstance(ref[1], Circle2D):
                return ref[1].center
            try:
                import numpy as _np
                if isinstance(ref, (list, tuple)) and len(ref)==2 and all(isinstance(v, (int,float)) for v in ref):
                    return _np.array([float(ref[0]), float(ref[1])], _np.float32)
                if hasattr(ref, 'shape') and getattr(ref, 'shape', None) is not None and len(ref.shape)==1 and ref.shape[0]==2:
                    return ref
            except Exception:
                pass
            return None
        def draw(self, p: QPainter, view):
            import numpy as _np
            a = self._xy(self.ref_a); b = self._xy(self.ref_b)
            if a is None or b is None: return
            # baseline and normal
            v = b - a
            L = float(np.linalg.norm(v))
            if L < 1e-6: return
            n = _np.array([-v[1], v[0]], _np.float32) / L
            # shifted dimension line
            p0 = a + n * self.offset
            p1 = b + n * self.offset
            sa = view._world_to_screen(_np.array([p0[0], p0[1], 0.0], _np.float32))
            sb = view._world_to_screen(_np.array([p1[0], p1[1], 0.0], _np.float32))
            # extension lines from anchors to dim line
            ea0 = view._world_to_screen(_np.array([a[0], a[1], 0.0], _np.float32))
            eb0 = view._world_to_screen(_np.array([b[0], b[1], 0.0], _np.float32))
            pen = QPen(QColor(180, 200, 220)); pen.setWidth(1); p.setPen(pen)
            p.drawLine(int(ea0[0]), int(ea0[1]), int(sa[0]), int(sa[1]))
            p.drawLine(int(eb0[0]), int(eb0[1]), int(sb[0]), int(sb[1]))
            # main dimension line
            pen = QPen(QColor(255, 220, 180)); pen.setWidth(2); p.setPen(pen)
            p.drawLine(int(sa[0]), int(sa[1]), int(sb[0]), int(sb[1]))
            # label
            val = float(np.linalg.norm(b - a))
            text = self.label_override if self.label_override is not None else self._fmt(val, self.panel)
            mid = (p0 + p1) * 0.5
            self.draw_text(p, view, mid, text)

    class DimHorizontal2D(DimLinear2D):
        def draw(self, p: QPainter, view):
            import numpy as _np
            a = self._xy(self.ref_a); b = self._xy(self.ref_b)
            if a is None or b is None: return
            # normal for horizontal is +Y
            n = _np.array([0.0, 1.0], _np.float32)
            p0 = _np.array([a[0], a[1]], _np.float32) + n * self.offset
            p1 = _np.array([b[0], b[1]], _np.float32) + n * self.offset
            sa = view._world_to_screen(_np.array([p0[0], p0[1], 0.0], _np.float32))
            sb = view._world_to_screen(_np.array([p1[0], p1[1], 0.0], _np.float32))
            # extensions
            ea0 = view._world_to_screen(_np.array([a[0], a[1], 0.0], _np.float32))
            eb0 = view._world_to_screen(_np.array([b[0], b[1], 0.0], _np.float32))
            pen = QPen(QColor(180, 200, 220)); pen.setWidth(1); p.setPen(pen)
            p.drawLine(int(ea0[0]), int(ea0[1]), int(sa[0]), int(sa[1]))
            p.drawLine(int(eb0[0]), int(eb0[1]), int(sb[0]), int(sb[1]))
            pen = QPen(QColor(255, 220, 180)); pen.setWidth(2); p.setPen(pen)
            p.drawLine(int(sa[0]), int(sa[1]), int(sb[0]), int(sb[1]))
            val = abs(float(b[0] - a[0]))
            text = self.label_override if self.label_override is not None else self._fmt(val, self.panel)
            mid = (p0 + p1) * 0.5
            self.draw_text(p, view, mid, text)

    class DimVertical2D(DimLinear2D):
        def draw(self, p: QPainter, view):
            import numpy as _np
            a = self._xy(self.ref_a); b = self._xy(self.ref_b)
            if a is None or b is None: return
            # normal for vertical is +X
            n = _np.array([1.0, 0.0], _np.float32)
            p0 = _np.array([a[0], a[1]], _np.float32) + n * self.offset
            p1 = _np.array([b[0], b[1]], _np.float32) + n * self.offset
            sa = view._world_to_screen(_np.array([p0[0], p0[1], 0.0], _np.float32))
            sb = view._world_to_screen(_np.array([p1[0], p1[1], 0.0], _np.float32))
            # extensions
            ea0 = view._world_to_screen(_np.array([a[0], a[1], 0.0], _np.float32))
            eb0 = view._world_to_screen(_np.array([b[0], b[1], 0.0], _np.float32))
            pen = QPen(QColor(180, 200, 220)); pen.setWidth(1); p.setPen(pen)
            p.drawLine(int(ea0[0]), int(ea0[1]), int(sa[0]), int(sa[1]))
            p.drawLine(int(eb0[0]), int(eb0[1]), int(sb[0]), int(sb[1]))
            pen = QPen(QColor(255, 220, 180)); pen.setWidth(2); p.setPen(pen)
            p.drawLine(int(sa[0]), int(sa[1]), int(sb[0]), int(sb[1]))
            val = abs(float(b[1] - a[1]))
            text = self.label_override if self.label_override is not None else self._fmt(val, self.panel)
            mid = (p0 + p1) * 0.5
            self.draw_text(p, view, mid, text)

    class DimRadius2D(DimBase2D):
        def __init__(self, circle_ref, panel):
            super().__init__(); self.circle_ref = circle_ref; self.panel = panel
        def draw(self, p: QPainter, view):
            if not (isinstance(self.circle_ref, tuple) and self.circle_ref[0]=='circle' and isinstance(self.circle_ref[1], Circle2D)):
                return
            c = self.circle_ref[1]
            val = float(c.radius)
            text = self.label_override if self.label_override is not None else self._fmt(val, self.panel)
            # place text slightly above center
            pos = c.center + np.array([0.0, c.radius + 0.0], np.float32)
            pen = QPen(QColor(255, 220, 180)); pen.setWidth(1); p.setPen(pen)
            self.draw_text(p, view, pos, f"R {text}")

    class DimDiameter2D(DimRadius2D):
        def draw(self, p: QPainter, view):
            if not (isinstance(self.circle_ref, tuple) and self.circle_ref[0]=='circle' and isinstance(self.circle_ref[1], Circle2D)):
                return
            c = self.circle_ref[1]
            val = float(c.radius*2.0)
            text = self.label_override if self.label_override is not None else self._fmt(val, self.panel)
            pos = c.center + np.array([0.0, c.radius + 0.0], np.float32)
            pen = QPen(QColor(255, 220, 180)); pen.setWidth(1); p.setPen(pen)
            self.draw_text(p, view, pos, f"âŒ€ {text}")

    class Circle2D(SketchEntity):
        def __init__(self, center, radius=0.0):
            import numpy as _np
            super().__init__()
            self.center = _np.array(center, dtype=_np.float32)
            self.radius = float(radius)
        def snap_points(self):
            import numpy as _np, math as _m
            pts = [self.center]
            if self.radius > 1e-6:
                for ang in (0,90,180,270):
                    a = _m.radians(ang)
                    pts.append(self.center + self.radius * _np.array([_np.cos(a), _np.sin(a)], _np.float32))
            return pts
        def snap_points_typed(self):
            out=[(self.center,'center')]
            return out
        def draw(self, p: QPainter, view):
            import numpy as _np, math as _m
            if self.radius <= 0: return
            segs = 40
            pts = []
            for i in range(segs+1):
                a = 2*_m.pi * i / segs
                w = self.center + self.radius * _np.array([_np.cos(a), _np.sin(a)], _np.float32)
                s = view._world_to_screen(_np.array([w[0], w[1], 0.0], _np.float32))
                pts.append(s)
            pen = QPen(QColor(180,220,255)); pen.setWidth(2)
            if getattr(self,'construction',False): pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            for a,b in zip(pts[:-1], pts[1:]):
                p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            # center point
            c = view._world_to_screen(_np.array([self.center[0], self.center[1], 0.0], _np.float32))
            pen = QPen(QColor(255,180,120)); pen.setWidth(6); p.setPen(pen); p.drawPoint(int(c[0]), int(c[1]))

    class Rect2D(SketchEntity):
        def __init__(self, p0, p1=None):
            import numpy as _np
            super().__init__()
            self.p0 = _np.array(p0, dtype=_np.float32)
            self.p1 = _np.array(p1, dtype=_np.float32) if p1 is not None else None
        def corners(self):
            import numpy as _np
            if self.p1 is None:
                return []
            x0,y0 = self.p0
            x1,y1 = self.p1
            mnx,mxx = min(x0,x1), max(x0,x1)
            mny,mxy = min(y0,y1), max(y0,y1)
            return [ _np.array([mnx,mny], _np.float32), _np.array([mxx,mny], _np.float32), _np.array([mxx,mxy], _np.float32), _np.array([mnx,mxy], _np.float32) ]
        def snap_points(self):
            import numpy as _np
            cs = self.corners()
            pts = cs[:]
            if len(cs)==4:
                # edge midpoints
                for a,b in zip(cs, cs[1:]+cs[:1]):
                    pts.append( (a+b)/2.0 )
                # center
                cx = sum(c[0] for c in cs)/4.0; cy = sum(c[1] for c in cs)/4.0
                pts.append(_np.array([cx,cy], _np.float32))
            return pts
        def snap_points_typed(self):
            import numpy as _np
            cs = self.corners()
            out=[(c,'end') for c in cs]
            if len(cs)==4:
                for a,b in zip(cs, cs[1:]+cs[:1]): out.append(((a+b)/2.0,'mid'))
                cx = sum(c[0] for c in cs)/4.0; cy = sum(c[1] for c in cs)/4.0
                out.append((_np.array([cx,cy], _np.float32),'center'))
            return out
        def draw(self, p: QPainter, view):
            import numpy as _np
            cs = self.corners()
            if len(cs) < 2:
                # just draw p0
                s0 = view._world_to_screen(_np.array([self.p0[0], self.p0[1], 0.0], _np.float32))
                pen = QPen(QColor(255,200,140)); pen.setWidth(6); p.setPen(pen); p.drawPoint(int(s0[0]), int(s0[1]))
                return
            pts2 = [ view._world_to_screen(_np.array([c[0], c[1], 0.0], _np.float32)) for c in cs ]
            pen = QPen(QColor(200,255,180)); pen.setWidth(2)
            if getattr(self,'construction',False): pen.setStyle(Qt.PenStyle.DashLine)
            p.setPen(pen)
            for a,b in zip(pts2, pts2[1:]+pts2[:1]):
                p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            pen = QPen(QColor(255,200,140)); pen.setWidth(6); p.setPen(pen)
            for s in pts2:
                p.drawPoint(int(s[0]), int(s[1]))

# --- Gizmo helper functions (move/rotate/scale snapping) ---
import math
def _deg2rad(d): return d * math.pi / 180.0
def _snap_angle(deg, step_deg):
    if step_deg <= 0: return deg
    return round(deg / step_deg) * step_deg
def _snap_scale(v, step):
    if step <= 0: return v
    return round(v / step) * step
def _make_rot(axis, deg):
    a = _deg2rad(deg)
    c, s = math.cos(a), math.sin(a)
    R = np.eye(4, dtype=np.float32)
    if axis == 'x':
        R[1,1]=c; R[1,2]=-s; R[2,1]=s; R[2,2]=c
    elif axis == 'y':
        R[0,0]=c; R[0,2]=s; R[2,0]=-s; R[2,2]=c
    else: # 'z'
        R[0,0]=c; R[0,1]=-s; R[1,0]=s; R[1,1]=c
    return R
def _make_scale(axis, k):
    S = np.eye(4, dtype=np.float32)
    if axis == 'x': S[0,0] = k
    elif axis == 'y': S[1,1] = k
    elif axis == 'z': S[2,2] = k
    else: S[0,0] = S[1,1] = S[2,2] = k
    return S
def _get_local_axes_from_xform(M):
    rx = M[:3,0]; ry = M[:3,1]; rz = M[:3,2]
    def _norm(v):
        n = np.linalg.norm(v); return v if n < 1e-9 else v / n
    return _norm(rx), _norm(ry), _norm(rz)

_SCALE_LEVELS = [
    ("macro", 1e-3),
    ("micro", 1e-5),
    ("meso", 1e-7),
    ("molecular", 1e-9),
    ("atomic_outer", 1e-10),
    ("atomic_bohr", 5.3e-11),
    ("nuclear", 1e-15),
    ("subnuclear", 1e-20),
    ("deep_quantum", 1e-24),
]
_LEVEL_INDEX = {name: idx for idx, (name, _) in enumerate(_SCALE_LEVELS)}


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge0 == edge1:
        return 0.0
    t = (x - edge0) / (edge1 - edge0)
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def _format_length(meters: float) -> str:
    m = abs(float(meters))
    units = [
        (1.0, "m"),
        (1e-3, "mm"),
        (1e-6, "um"),
        (1e-9, "nm"),
        (1e-12, "pm"),
        (1e-15, "fm"),
        (1e-18, "am"),
        (1e-21, "zm"),
        (1e-24, "ym"),
    ]
    for scale, suffix in units:
        if m >= scale:
            return f"{m / scale:.3g} {suffix}"
    scale, suffix = units[-1]
    return f"{m / scale:.3g} {suffix}"


def _level_activation(level: str, eps: float) -> float:
    threshold = _SCALE_LEVELS[_LEVEL_INDEX[level]][1]
    eps = max(eps, 1e-24)
    hi = max(threshold * 10.0, threshold + 1e-24)
    lo = max(threshold, 1e-24)
    log_eps = math.log10(eps)
    log_hi = math.log10(hi)
    log_lo = math.log10(lo)
    return _smoothstep(log_hi, log_lo, log_eps)


def _lod_state(eps: float):
    eps = max(eps, 1e-24)
    log_eps = math.log10(eps)
    for idx, (name, threshold) in enumerate(_SCALE_LEVELS):
        if eps >= threshold:
            if idx + 1 < len(_SCALE_LEVELS):
                next_name, next_threshold = _SCALE_LEVELS[idx + 1]
                blend = _smoothstep(
                    math.log10(max(threshold, 1e-24)),
                    math.log10(max(next_threshold, 1e-24)),
                    log_eps,
                )
                return name, next_name, blend
            return name, None, 0.0
    last_name, _ = _SCALE_LEVELS[-1]
    return last_name, None, 0.0


def _compute_world_tolerance(view, center: np.ndarray, pixels: float, fov_deg: float) -> tuple[float, float, float]:
    try:
        width = float(view.width())
    except Exception:
        width = 1.0
    try:
        dpr = float(view.devicePixelRatioF())
    except AttributeError:
        try:
            dpr = float(view.devicePixelRatio())
        except Exception:
            dpr = 1.0
    width_px = max(1.0, width * max(1.0, dpr))
    cam_pos = getattr(view, 'cam_pos', np.array([0.0, 0.0, 0.0], np.float32))
    depth = float(np.linalg.norm(cam_pos - center))
    fov_rad = math.radians(float(fov_deg))
    m_per_px = 2.0 * depth * math.tan(fov_rad * 0.5) / width_px
    return pixels * m_per_px, depth, width_px


def _distance_for_epsilon(eps: float, width_px: float, pixels: float, fov_deg: float) -> float:
    fov_rad = math.radians(float(fov_deg))
    denom = 2.0 * max(pixels, 1e-6) * math.tan(fov_rad * 0.5)
    return float(max(0.0, eps) * max(width_px, 1.0) / max(denom, 1e-6))

# --- Ensure Sketch Overlay classes exist even if PIL import succeeded ---
try:
    SketchLayer
except NameError:  # define overlay classes (PIL present path)
    SNAP_PX = 10
    class SketchEntity:
        def __init__(self):
            self.construction = False
        def draw(self, p: QPainter, view): ...
        def snap_points(self): return []
        def snap_points_typed(self):
            return [(pt, 'other') for pt in self.snap_points()]
    class Polyline2D(SketchEntity):
        def __init__(self, pts=None):
            import numpy as _np
            self.pts = [ _np.array(p, dtype=_np.float32) for p in (pts or []) ]
        def snap_points(self):
            import numpy as _np
            out = [] + self.pts
            for a,b in zip(self.pts[:-1], self.pts[1:]):
                out.append((a+b)/2.0)
            return out
        def draw(self, p: QPainter, view):
            import numpy as _np
            if not self.pts: return
            pts2 = [ view._world_to_screen(_np.array([x,y,0.0], _np.float32)) for (x,y) in self.pts ]
            if len(pts2) >= 2:
                pen = QPen(QColor(220,220,220)); pen.setWidth(2); p.setPen(pen)
                for a,b in zip(pts2[:-1], pts2[1:]):
                    p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            pen = QPen(QColor(255,200,120)); pen.setWidth(6); p.setPen(pen)
            for s in pts2: p.drawPoint(int(s[0]), int(s[1]))
    class Line2D(SketchEntity):
        def __init__(self, p0, p1=None):
            import numpy as _np
            self.p0 = _np.array(p0, dtype=_np.float32)
            self.p1 = _np.array(p1, dtype=_np.float32) if p1 is not None else None
        def snap_points(self):
            import numpy as _np
            pts = [self.p0]
            if self.p1 is not None:
                pts.append(self.p1)
                pts.append((self.p0 + self.p1)/2.0)
            return pts
        def snap_points_typed(self):
            out=[(self.p0,'end')]
            if self.p1 is not None:
                out.append((self.p1,'end'))
                out.append(((self.p0+self.p1)/2.0,'mid'))
            return out
        def draw(self, p: QPainter, view):
            import numpy as _np
            s0 = view._world_to_screen(_np.array([self.p0[0], self.p0[1], 0.0], _np.float32))
            pen = QPen(QColor(220,220,220)); pen.setWidth(2); p.setPen(pen)
            if self.p1 is not None:
                s1 = view._world_to_screen(_np.array([self.p1[0], self.p1[1], 0.0], _np.float32))
                p.drawLine(int(s0[0]), int(s0[1]), int(s1[0]), int(s1[1]))
            pen = QPen(QColor(255,200,140)); pen.setWidth(6); p.setPen(pen); p.drawPoint(int(s0[0]), int(s0[1]))
            if self.p1 is not None:
                p.drawPoint(int(s1[0]), int(s1[1]))
    class Circle2D(SketchEntity):
        def __init__(self, center, radius=0.0):
            import numpy as _np
            self.center = _np.array(center, dtype=_np.float32)
            self.radius = float(radius)
        def snap_points(self):
            import numpy as _np, math as _m
            pts = [self.center]
            if self.radius>1e-6:
                for ang in (0,90,180,270):
                    a=_m.radians(ang)
                    pts.append(self.center + self.radius * _np.array([_np.cos(a), _np.sin(a)], _np.float32))
            return pts
        def snap_points_typed(self):
            return [(self.center,'center')]
        def draw(self, p: QPainter, view):
            import numpy as _np, math as _m
            if self.radius <= 0: return
            segs=40; pts=[]
            for i in range(segs+1):
                a=2*_m.pi*i/segs
                w=self.center + self.radius*_np.array([_np.cos(a), _np.sin(a)], _np.float32)
                s=view._world_to_screen(_np.array([w[0],w[1],0.0], _np.float32))
                pts.append(s)
            pen = QPen(QColor(180,220,255)); pen.setWidth(2); p.setPen(pen)
            for a,b in zip(pts[:-1], pts[1:]): p.drawLine(int(a[0]),int(a[1]),int(b[0]),int(b[1]))
            c=view._world_to_screen(_np.array([self.center[0],self.center[1],0.0], _np.float32))
            pen = QPen(QColor(255,180,120)); pen.setWidth(6); p.setPen(pen); p.drawPoint(int(c[0]), int(c[1]))
    class Rect2D(SketchEntity):
        def __init__(self, p0, p1=None):
            import numpy as _np
            self.p0=_np.array(p0, dtype=_np.float32)
            self.p1=_np.array(p1, dtype=_np.float32) if p1 is not None else None
        def corners(self):
            import numpy as _np
            if self.p1 is None: return []
            x0,y0=self.p0; x1,y1=self.p1
            mnx,mxx=min(x0,x1),max(x0,x1); mny,mxy=min(y0,y1),max(y0,y1)
            return [ _np.array([mnx,mny],_np.float32), _np.array([mxx,mny],_np.float32), _np.array([mxx,mxy],_np.float32), _np.array([mnx,mxy],_np.float32) ]
        def snap_points(self):
            import numpy as _np
            cs=self.corners(); pts=cs[:]
            if len(cs)==4:
                for a,b in zip(cs, cs[1:]+cs[:1]): pts.append((a+b)/2.0)
                cx=sum(c[0] for c in cs)/4.0; cy=sum(c[1] for c in cs)/4.0
                pts.append(_np.array([cx,cy], _np.float32))
            return pts
        def snap_points_typed(self):
            import numpy as _np
            cs = self.corners()
            out=[(c,'end') for c in cs]
            if len(cs)==4:
                for a,b in zip(cs, cs[1:]+cs[:1]): out.append(((a+b)/2.0,'mid'))
                cx = sum(c[0] for c in cs)/4.0; cy = sum(c[1] for c in cs)/4.0
                out.append((_np.array([cx,cy], _np.float32),'center'))
            return out
        def draw(self, p: QPainter, view):
            import numpy as _np
            cs=self.corners()
            if len(cs)<2:
                s0=view._world_to_screen(_np.array([self.p0[0], self.p0[1],0.0], _np.float32))
                pen=QPen(QColor(255,200,140)); pen.setWidth(6); p.setPen(pen); p.drawPoint(int(s0[0]), int(s0[1])); return
            pts2=[ view._world_to_screen(_np.array([c[0],c[1],0.0], _np.float32)) for c in cs ]
            pen=QPen(QColor(200,255,180)); pen.setWidth(2); p.setPen(pen)
            for a,b in zip(pts2, pts2[1:]+pts2[:1]): p.drawLine(int(a[0]),int(a[1]),int(b[0]),int(b[1]))
            pen=QPen(QColor(255,200,140)); pen.setWidth(6); p.setPen(pen)
            for s in pts2: p.drawPoint(int(s[0]), int(s[1]))
    class Arc2D(SketchEntity):
        def __init__(self, p0=None, p1=None, p2=None):
            import numpy as _np
            self.p0 = _np.array(p0, dtype=_np.float32) if p0 is not None else None
            self.p1 = _np.array(p1, dtype=_np.float32) if p1 is not None else None
            self.p2 = _np.array(p2, dtype=_np.float32) if p2 is not None else None
        def _circle_from_3pts(self):
            import numpy as _np
            if self.p0 is None or self.p1 is None or self.p2 is None:
                return None
            x1,y1 = self.p0; x2,y2 = self.p1; x3,y3 = self.p2
            a = x1*(y2 - y3) - y1*(x2 - x3) + x2*y3 - x3*y2
            if abs(a) < 1e-9: return None
            b = (x1*x1 + y1*y1)*(y3 - y2) + (x2*x2 + y2*y2)*(y1 - y3) + (x3*x3 + y3*y3)*(y2 - y1)
            c = (x1*x1 + y1*y1)*(x2 - x3) + (x2*x2 + y2*y2)*(x3 - x1) + (x3*x3 + y3*y3)*(x1 - x2)
            cx = -b/(2*a); cy = -c/(2*a)
            r = float(_np.hypot(x1-cx, y1-cy))
            return _np.array([cx,cy], _np.float32), r
        def snap_points(self):
            import numpy as _np
            pts=[]
            if self.p0 is not None: pts.append(self.p0)
            if self.p2 is not None: pts.append(self.p2)
            circ = self._circle_from_3pts()
            if circ is not None:
                c,_ = circ; pts.append(c)
            if self.p0 is not None and self.p2 is not None:
                pts.append((self.p0 + self.p2)/2.0)
            return pts
        def snap_points_typed(self):
            out=[]
            if self.p0 is not None: out.append((self.p0,'end'))
            if self.p2 is not None: out.append((self.p2,'end'))
            circ = self._circle_from_3pts()
            if circ is not None:
                c,_ = circ; out.append((c,'center'))
            if self.p0 is not None and self.p2 is not None:
                out.append(((self.p0+self.p2)/2.0,'mid'))
            return out
        def draw(self, p: QPainter, view):
            import numpy as _np, math as _m
            if self.p0 is None:
                return
            pen=QPen(QColor(200,240,255)); pen.setWidth(2); p.setPen(pen)
            if self.p1 is None or self.p2 is None:
                s0=view._world_to_screen(_np.array([self.p0[0], self.p0[1],0.0], _np.float32))
                p.drawPoint(int(s0[0]), int(s0[1]))
                if self.p1 is not None:
                    s1=view._world_to_screen(_np.array([self.p1[0], self.p1[1],0.0], _np.float32))
                    p.drawLine(int(s0[0]), int(s0[1]), int(s1[0]), int(s1[1]))
                return
            circ=self._circle_from_3pts()
            if circ is None:
                s0=view._world_to_screen(_np.array([self.p0[0], self.p0[1],0.0], _np.float32))
                s2=view._world_to_screen(_np.array([self.p2[0], self.p2[1],0.0], _np.float32))
                p.drawLine(int(s0[0]), int(s0[1]), int(s2[0]), int(s2[1]))
                return
            c,r=circ
            a0=_m.atan2(self.p0[1]-c[1], self.p0[0]-c[0])
            a1=_m.atan2(self.p1[1]-c[1], self.p1[0]-c[0])
            a2=_m.atan2(self.p2[1]-c[1], self.p2[0]-c[0])
            def ang_dist(a,b):
                d=(b-a+_m.pi)%(2*_m.pi)-_m.pi
                return d
            d1=abs(ang_dist(a0,a1))+abs(ang_dist(a1,a2))
            d2=abs(ang_dist(a0,a2))
            cw=False if d1<d2 else True
            segs=48; pts=[]
            if not cw:
                step=ang_dist(a0,a2)/segs; k=0
                while k<=segs:
                    ang=a0+step*k; k+=1
                    w=c+r*_np.array([_np.cos(ang), _np.sin(ang)], _np.float32)
                    s=view._world_to_screen(_np.array([w[0],w[1],0.0], _np.float32)); pts.append(s)
            else:
                step=ang_dist(a2,a0)/segs; k=0
                while k<=segs:
                    ang=a2+step*k; k+=1
                    w=c+r*_np.array([_np.cos(ang), _np.sin(ang)], _np.float32)
                    s=view._world_to_screen(_np.array([w[0],w[1],0.0], _np.float32)); pts.append(s)
            for a,b in zip(pts[:-1], pts[1:]): p.drawLine(int(a[0]), int(a[1]), int(b[0]), int(b[1]))
            pen_pts=QPen(QColor(255,200,140)); pen_pts.setWidth(6); p.setPen(pen_pts)
            s0=view._world_to_screen(_np.array([self.p0[0], self.p0[1],0.0], _np.float32)); p.drawPoint(int(s0[0]), int(s0[1]))
            s2=view._world_to_screen(_np.array([self.p2[0], self.p2[1],0.0], _np.float32)); p.drawPoint(int(s2[0]), int(s2[1]))
            sc=view._world_to_screen(_np.array([c[0], c[1],0.0], _np.float32)); p.drawPoint(int(sc[0]), int(sc[1]))
    # --- Dimension overlays (fallback path) ---
    class DimBase2D:
        def __init__(self):
            self.label_override = None
        def _fmt(self, val: float, panel) -> str:
            try:
                prec = int(getattr(panel, '_dim_precision', 2))
            except Exception:
                prec = 2
            return f"{val:.{prec}f}"
        def draw_text(self, p: QPainter, view, pos_xy, text):
            import numpy as _np
            s = view._world_to_screen(_np.array([pos_xy[0], pos_xy[1], 0.0], _np.float32))
            p.setPen(QPen(QColor(250, 250, 210)))
            p.drawText(int(s[0]+6), int(s[1]-6), text)

    class DimLinear2D(DimBase2D):
        def __init__(self, ref_a, ref_b, panel, offset: float = 0.0):
            super().__init__(); self.ref_a = ref_a; self.ref_b = ref_b; self.panel = panel; self.offset = float(offset)
        def _xy(self, ref):
            if isinstance(ref, tuple) and len(ref)==2 and isinstance(ref[0], Polyline2D):
                ent, idx = ref; return ent.pts[idx]
            if isinstance(ref, tuple) and len(ref)==2 and isinstance(ref[0], Line2D):
                ent, idx = ref
                if idx == 0: return ent.p0
                if idx == 1 and ent.p1 is not None: return ent.p1
                return None
            if isinstance(ref, tuple) and len(ref)==2 and isinstance(ref[0], Rect2D):
                ent, idx = ref
                cs = ent.corners()
                if 0 <= idx < len(cs): return cs[idx]
                return None
            if isinstance(ref, tuple) and ref[0]=='circle' and isinstance(ref[1], Circle2D):
                return ref[1].center
            try:
                import numpy as _np
                if isinstance(ref, (list, tuple)) and len(ref)==2 and all(isinstance(v, (int,float)) for v in ref):
                    return _np.array([float(ref[0]), float(ref[1])], _np.float32)
                if hasattr(ref, 'shape') and getattr(ref, 'shape', None) is not None and len(ref.shape)==1 and ref.shape[0]==2:
                    return ref
            except Exception:
                pass
            return None
        def draw(self, p: QPainter, view):
            import numpy as _np, numpy as np
            a = self._xy(self.ref_a); b = self._xy(self.ref_b)
            if a is None or b is None: return
            v = b - a
            L = float(np.linalg.norm(v))
            if L < 1e-6: return
            n = _np.array([-v[1], v[0]], _np.float32) / L
            p0 = a + n * self.offset
            p1 = b + n * self.offset
            sa = view._world_to_screen(_np.array([p0[0], p0[1], 0.0], _np.float32))
            sb = view._world_to_screen(_np.array([p1[0], p1[1], 0.0], _np.float32))
            ea0 = view._world_to_screen(_np.array([a[0], a[1], 0.0], _np.float32))
            eb0 = view._world_to_screen(_np.array([b[0], b[1], 0.0], _np.float32))
            pen = QPen(QColor(180, 200, 220)); pen.setWidth(1); p.setPen(pen)
            p.drawLine(int(ea0[0]), int(ea0[1]), int(sa[0]), int(sa[1]))
            p.drawLine(int(eb0[0]), int(eb0[1]), int(sb[0]), int(sb[1]))
            pen = QPen(QColor(255, 220, 180)); pen.setWidth(2); p.setPen(pen)
            p.drawLine(int(sa[0]), int(sa[1]), int(sb[0]), int(sb[1]))
            val = float(np.linalg.norm(b - a))
            text = self.label_override if self.label_override is not None else self._fmt(val, self.panel)
            mid = (p0 + p1) * 0.5
            self.draw_text(p, view, mid, text)

    class DimHorizontal2D(DimLinear2D):
        def draw(self, p: QPainter, view):
            import numpy as _np
            a = self._xy(self.ref_a); b = self._xy(self.ref_b)
            if a is None or b is None: return
            n = _np.array([0.0, 1.0], _np.float32)
            p0 = _np.array([a[0], a[1]], _np.float32) + n * self.offset
            p1 = _np.array([b[0], b[1]], _np.float32) + n * self.offset
            sa = view._world_to_screen(_np.array([p0[0], p0[1], 0.0], _np.float32))
            sb = view._world_to_screen(_np.array([p1[0], p1[1], 0.0], _np.float32))
            ea0 = view._world_to_screen(_np.array([a[0], a[1], 0.0], _np.float32))
            eb0 = view._world_to_screen(_np.array([b[0], b[1], 0.0], _np.float32))
            pen = QPen(QColor(180, 200, 220)); pen.setWidth(1); p.setPen(pen)
            p.drawLine(int(ea0[0]), int(ea0[1]), int(sa[0]), int(sa[1]))
            p.drawLine(int(eb0[0]), int(eb0[1]), int(sb[0]), int(sb[1]))
            pen = QPen(QColor(255, 220, 180)); pen.setWidth(2); p.setPen(pen)
            p.drawLine(int(sa[0]), int(sa[1]), int(sb[0]), int(sb[1]))
            val = abs(float(b[0] - a[0]))
            text = self.label_override if self.label_override is not None else self._fmt(val, self.panel)
            mid = (p0 + p1) * 0.5
            self.draw_text(p, view, mid, text)

    class DimVertical2D(DimLinear2D):
        def draw(self, p: QPainter, view):
            import numpy as _np
            a = self._xy(self.ref_a); b = self._xy(self.ref_b)
            if a is None or b is None: return
            n = _np.array([1.0, 0.0], _np.float32)
            p0 = _np.array([a[0], a[1]], _np.float32) + n * self.offset
            p1 = _np.array([b[0], b[1]], _np.float32) + n * self.offset
            sa = view._world_to_screen(_np.array([p0[0], p0[1], 0.0], _np.float32))
            sb = view._world_to_screen(_np.array([p1[0], p1[1], 0.0], _np.float32))
            ea0 = view._world_to_screen(_np.array([a[0], a[1], 0.0], _np.float32))
            eb0 = view._world_to_screen(_np.array([b[0], b[1], 0.0], _np.float32))
            pen = QPen(QColor(180, 200, 220)); pen.setWidth(1); p.setPen(pen)
            p.drawLine(int(ea0[0]), int(ea0[1]), int(sa[0]), int(sa[1]))
            p.drawLine(int(eb0[0]), int(eb0[1]), int(sb[0]), int(sb[1]))
            pen = QPen(QColor(255, 220, 180)); pen.setWidth(2); p.setPen(pen)
            p.drawLine(int(sa[0]), int(sa[1]), int(sb[0]), int(sb[1]))
            val = abs(float(b[1] - a[1]))
            text = self.label_override if self.label_override is not None else self._fmt(val, self.panel)
            mid = (p0 + p1) * 0.5
            self.draw_text(p, view, mid, text)

    class DimRadius2D(DimBase2D):
        def __init__(self, circle_ref, panel):
            super().__init__(); self.circle_ref = circle_ref; self.panel = panel
        def draw(self, p: QPainter, view):
            if not (isinstance(self.circle_ref, tuple) and self.circle_ref[0]=='circle' and isinstance(self.circle_ref[1], Circle2D)):
                return
            c = self.circle_ref[1]
            val = float(c.radius)
            text = self.label_override if self.label_override is not None else self._fmt(val, self.panel)
            pos = c.center + np.array([0.0, c.radius + 0.0], np.float32)
            pen = QPen(QColor(255, 220, 180)); pen.setWidth(1); p.setPen(pen)
            self.draw_text(p, view, pos, f"R {text}")

    class DimDiameter2D(DimRadius2D):
        def draw(self, p: QPainter, view):
            if not (isinstance(self.circle_ref, tuple) and self.circle_ref[0]=='circle' and isinstance(self.circle_ref[1], Circle2D)):
                return
            c = self.circle_ref[1]
            val = float(c.radius*2.0)
            text = self.label_override if self.label_override is not None else self._fmt(val, self.panel)
            pos = c.center + np.array([0.0, c.radius + 0.0], np.float32)
            pen = QPen(QColor(255, 220, 180)); pen.setWidth(1); p.setPen(pen)
            self.draw_text(p, view, pos, f"âŒ€ {text}")

    class SketchLayer:
        def __init__(self):
            self.entities=[]; self.active_poly=None; self.active_shape=None; self.hover_snap=None
            self.dimensions = []
            self._dim_pick = None
            self._dim_preview = None
            self._dim_placing = False
            self._dim_place_data = None
        def all_snap_points(self):
            pts=[]
            for e in self.entities: pts+=e.snap_points()
            if self.active_poly: pts+=self.active_poly.snap_points()
            if self.active_shape and hasattr(self.active_shape,'snap_points'): pts+=self.active_shape.snap_points()
            return pts
        def all_snap_points_typed(self):
            pts=[]
            for e in self.entities:
                if hasattr(e,'snap_points_typed'):
                    pts += e.snap_points_typed()
                else:
                    pts += [(pt,'other') for pt in e.snap_points()]
            if self.active_poly and hasattr(self.active_poly,'snap_points_typed'):
                pts += self.active_poly.snap_points_typed()
            if self.active_shape and hasattr(self.active_shape,'snap_points_typed'):
                pts += self.active_shape.snap_points_typed()
            return pts
        def draw(self, p: QPainter, view):
            for e in self.entities: e.draw(p, view)
            if self.active_poly: self.active_poly.draw(p, view)
            if self.active_shape: self.active_shape.draw(p, view)
            # draw dimensions
            for d in getattr(self, 'dimensions', []):
                try:
                    d.draw(p, view)
                except Exception:
                    pass
            # draw preview dim if any
            try:
                if self._dim_preview is not None:
                    self._dim_preview.draw(p, view)
            except Exception:
                pass
            if self.hover_snap is not None:
                import numpy as _np
                s=view._world_to_screen(_np.array([self.hover_snap[0], self.hover_snap[1],0.0], _np.float32))
                pen=QPen(QColor(120,255,160)); pen.setWidth(2); p.setPen(pen)
                p.drawLine(int(s[0]-6), int(s[1]), int(s[0]+6), int(s[1]))
                p.drawLine(int(s[0]), int(s[1]-6), int(s[0]), int(s[1]+6))

def load_text(p):
    return Path(p).read_text(encoding="utf-8")

class AnalyticViewport(QOpenGLWidget):
    def __init__(self, parent=None, aacore_scene: AACoreScene | None = None):
        super().__init__(parent)
        fmt = QSurfaceFormat()
        fmt.setVersion(3,3); fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
        fmt.setSamples(4)  # 4x MSAA
        self.setFormat(fmt)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Shared AACore scene (may be injected)
        self.scene = aacore_scene if aacore_scene is not None else AACoreScene()
        # camera
        self.cam_target = np.array([0.0,0.0,0.0], np.float32)
        self.distance = 6.0
        self.yaw=0.0; self.pitch=0.0
        self.cam_pos = np.array([0.0,0.0,self.distance], np.float32)
        self._last_mouse = None
        self._last_buttons = Qt.MouseButton.NoButton
        # shader handles
        self.prog = None
        # debug / feature toggles (could later expose via UI)
        self.debug_mode = 0          # 0 beauty
        self.use_analytic_aa = 1
        self.use_toon = 0
        self.toon_levels = 4.0
        self.curv_strength = 1.0
        self.use_foveated = 1
        self.far_plane = 200.0
        self.show_beta_overlay = 0
        self.beta_overlay_intensity = 0.65
        self.beta_scale = 1.0
        self.beta_cmap = 0  # 0 legacy,1 viridis,2 plasma,3 diverge
        self._settings_path = os.path.join(os.path.expanduser('~'), '.adaptivecad_analytic.json')
        self._load_settings()
        self._beta_lut_tex = None
        self._curv_lut_tex = None
        self.use_curv_lut = 1
        self.fractal_color_mode = 1
        self.fractal_orbit_shell = 1.0
        self.fractal_ni_scale = 0.08
        # listen for scene edits (debounced via timer-less simple flag)
        self._scene_dirty = True
        try:
            self.scene.on_changed(self._on_scene_changed)
        except Exception:
            pass
        if aacore_scene is None and len(self.scene.prims) == 0:
            self._demo_scene()
        # selection
        self.selected_index = -1
        self._picking_fbo = None
        self._pick_tex = None
        self._depth_rb = None
        # micro pick FBO
        self._pick_fbo = None
        # translation drag state
        self._drag_move_active = False
        self._drag_last_pos = None
        # Overlay editing state
        self._sk_point_sel = None  # (entity, index) for Polyline2D point or ('circle', entity) for circle center
        self._sk_dragging = False
        # Lightweight 2D polyline overlays (for algorithm visuals)
        # Each entry: { 'pts': [(x,y),...], 'color': (r,g,b), 'width': int, 'scale': (sx,sy), 'offset': (ox,oy) }
        self._poly_overlays = []
        # Triangle mesh overlays (reloaded exports, diagnostics)
        self._mesh_prog = None
        self._mesh_uniforms: dict[str, int] = {}
        self._mesh_overlays: list[dict[str, object]] = []

    # Resolve a sketch reference used by dimension tools into a world XY np.array([x,y], float32)
    def _ref_to_xy(self, ref):
        import numpy as _np
        try:
            if isinstance(ref, tuple) and len(ref)==2 and isinstance(ref[0], Polyline2D):
                ent, idx = ref
                if isinstance(idx, int) and 0 <= idx < len(ent.pts):
                    return ent.pts[idx]
            if isinstance(ref, tuple) and len(ref)==2 and isinstance(ref[0], Line2D):
                ent, key = ref
                if key == 0:
                    return ent.p0
                if key == 1 and ent.p1 is not None:
                    return ent.p1
                if isinstance(key, (tuple, list)) and key and key[0] == 'mid' and ent.p1 is not None:
                    return (ent.p0 + ent.p1) * 0.5
            if isinstance(ref, tuple) and len(ref)==2 and isinstance(ref[0], Rect2D):
                ent, key = ref
                cs = ent.corners()
                if isinstance(key, int):
                    if 0 <= key < len(cs):
                        return cs[key]
                elif isinstance(key, (tuple, list)) and key:
                    tag = key[0]
                    if tag == 'edge_mid' and len(cs) >= 2:
                        try:
                            idx = int(key[1])
                        except Exception:
                            return None
                        if len(cs) == 0:
                            return None
                        a = cs[idx % len(cs)]
                        b = cs[(idx + 1) % len(cs)]
                        return (a + b) * 0.5
                elif key == 'center' and len(cs) == 4:
                    cx = sum(c[0] for c in cs) / 4.0
                    cy = sum(c[1] for c in cs) / 4.0
                    return _np.array([cx, cy], _np.float32)
            if isinstance(ref, tuple) and ref[0]=='circle' and isinstance(ref[1], Circle2D):
                return ref[1].center
            if isinstance(ref, (list, tuple)) and len(ref)==2 and all(isinstance(v, (int,float)) for v in ref):
                return _np.array([float(ref[0]), float(ref[1])], _np.float32)
            if hasattr(ref, 'shape') and getattr(ref, 'shape', None) is not None and len(ref.shape)==1 and ref.shape[0]==2:
                return ref
        except Exception:
            return None
        return None

    def _on_scene_changed(self):
        self._scene_dirty = True
        self.update()

    def _demo_scene(self):
        self.scene.add(Prim(KIND_SPHERE, [1.2,0,0,0], beta=0.12, color=(0.9,0.4,0.3)))
        self.scene.add(Prim(KIND_CAPSULE, [0.4,2.0,0,0], beta=0.0, color=(0.3,0.7,0.9)))
        self.scene.add(Prim(KIND_TORUS, [1.2,0.25,0,0], beta=0.05, color=(0.6,0.9,0.5)))

    def sizeHint(self): return QSize(800,600)

    # --- OpenGL lifecycle ---
    def initializeGL(self):
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_MULTISAMPLE)  # Enable MSAA
        shader_dir = Path(__file__).parent.parent / "analytic" / "shaders"
        vs = load_text(shader_dir / "sdf.vert")
        fs = load_text(shader_dir / "sdf.frag")
        self.prog = glCreateProgram()
        vsh = glCreateShader(GL_VERTEX_SHADER); glShaderSource(vsh, vs); glCompileShader(vsh)
        if not glGetShaderiv(vsh, GL_COMPILE_STATUS): raise RuntimeError(glGetShaderInfoLog(vsh).decode())
        fsh = glCreateShader(GL_FRAGMENT_SHADER); glShaderSource(fsh, fs); glCompileShader(fsh)
        if not glGetShaderiv(fsh, GL_COMPILE_STATUS): raise RuntimeError(glGetShaderInfoLog(fsh).decode())
        glAttachShader(self.prog, vsh); glAttachShader(self.prog, fsh); glLinkProgram(self.prog)
        if not glGetProgramiv(self.prog, GL_LINK_STATUS): raise RuntimeError(glGetProgramInfoLog(self.prog).decode())
        glDeleteShader(vsh); glDeleteShader(fsh)

        # Mesh overlay shader (renders triangle meshes on top of the raymarched scene)
        mesh_vs_src = (
            "#version 330 core\n"
            "layout(location=0) in vec3 a_pos;\n"
            "layout(location=1) in vec3 a_norm;\n"
            "layout(location=2) in vec3 a_color;\n"
            "uniform mat4 u_mvp;\n"
            "uniform mat4 u_model;\n"
            "uniform mat3 u_normal;\n"
            "out vec3 v_normal;\n"
            "out vec3 v_color;\n"
            "out vec3 v_world_pos;\n"
            "void main(){\n"
            "    vec4 world = u_model * vec4(a_pos, 1.0);\n"
            "    v_world_pos = world.xyz;\n"
            "    v_normal = u_normal * a_norm;\n"
            "    v_color = a_color;\n"
            "    gl_Position = u_mvp * vec4(a_pos, 1.0);\n"
            "}\n"
        )
        mesh_fs_src = (
            "#version 330 core\n"
            "in vec3 v_normal;\n"
            "in vec3 v_color;\n"
            "in vec3 v_world_pos;\n"
            "out vec4 FragColor;\n"
            "uniform vec3 u_cam_pos;\n"
            "uniform vec3 u_light_dir;\n"
            "uniform vec3 u_fallback_color;\n"
            "uniform int u_has_vertex_color;\n"
            "void main(){\n"
            "    vec3 N = normalize(v_normal);\n"
            "    vec3 L = normalize(u_light_dir);\n"
            "    vec3 V = normalize(u_cam_pos - v_world_pos);\n"
            "    vec3 base = mix(u_fallback_color, clamp(v_color, 0.0, 1.0), float(u_has_vertex_color));\n"
            "    float diff = max(dot(N, L), 0.0);\n"
            "    vec3 H = normalize(L + V);\n"
            "    float spec = pow(max(dot(N, H), 0.0), 32.0);\n"
            "    vec3 color = base * (0.25 + 0.75 * diff) + spec * 0.2;\n"
            "    FragColor = vec4(color, 1.0);\n"
            "}\n"
        )
        try:
            mesh_prog = glCreateProgram()
            mesh_vs = glCreateShader(GL_VERTEX_SHADER)
            glShaderSource(mesh_vs, mesh_vs_src)
            glCompileShader(mesh_vs)
            if not glGetShaderiv(mesh_vs, GL_COMPILE_STATUS):
                raise RuntimeError(glGetShaderInfoLog(mesh_vs).decode())
            mesh_fs = glCreateShader(GL_FRAGMENT_SHADER)
            glShaderSource(mesh_fs, mesh_fs_src)
            glCompileShader(mesh_fs)
            if not glGetShaderiv(mesh_fs, GL_COMPILE_STATUS):
                raise RuntimeError(glGetShaderInfoLog(mesh_fs).decode())
            glAttachShader(mesh_prog, mesh_vs)
            glAttachShader(mesh_prog, mesh_fs)
            glLinkProgram(mesh_prog)
            if not glGetProgramiv(mesh_prog, GL_LINK_STATUS):
                raise RuntimeError(glGetProgramInfoLog(mesh_prog).decode())
            glDeleteShader(mesh_vs)
            glDeleteShader(mesh_fs)
            self._mesh_prog = mesh_prog
            self._mesh_uniforms = {
                "u_mvp": glGetUniformLocation(mesh_prog, "u_mvp"),
                "u_model": glGetUniformLocation(mesh_prog, "u_model"),
                "u_normal": glGetUniformLocation(mesh_prog, "u_normal"),
                "u_cam_pos": glGetUniformLocation(mesh_prog, "u_cam_pos"),
                "u_light_dir": glGetUniformLocation(mesh_prog, "u_light_dir"),
                "u_fallback_color": glGetUniformLocation(mesh_prog, "u_fallback_color"),
                "u_has_vertex_color": glGetUniformLocation(mesh_prog, "u_has_vertex_color"),
            }
        except Exception as exc:
            log.debug(f"Mesh overlay shader init failed: {exc}")
            try:
                if 'mesh_prog' in locals():
                    glDeleteProgram(mesh_prog)
            except Exception:
                pass
            self._mesh_prog = None
            self._mesh_uniforms = {}

        # fullscreen quad
        self._vao = glGenVertexArrays(1); glBindVertexArray(self._vao)
        v = np.array([-1,-1,  1,-1, -1, 1,   1,1], dtype=np.float32)
        self._vbo = glGenBuffers(1); glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
        glBufferData(GL_ARRAY_BUFFER, v.nbytes, v, GL_STATIC_DRAW)
        glEnableVertexAttribArray(0); glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, None)
        # create simple FBO for ID picking
        self._init_picking()
        # --- 1x1 FBO for micro picking ---
        try:
            self._pick_fbo = glGenFramebuffers(1)
            glBindFramebuffer(GL_FRAMEBUFFER, self._pick_fbo)
            self._pick_tex_micro = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self._pick_tex_micro)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 1, 1, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, self._pick_tex_micro, 0)
            glBindFramebuffer(GL_FRAMEBUFFER, 0)
        except Exception as e:
            log.debug(f"Micro pick FBO init failed: {e}")

    def _init_picking(self):
        try:
            if self._picking_fbo:
                return
            self._picking_fbo = glGenFramebuffers(1)
            glBindFramebuffer(GL_FRAMEBUFFER, self._picking_fbo)
            self._pick_tex = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, self._pick_tex)
            glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,self.width(),self.height(),0,GL_RGBA,GL_UNSIGNED_BYTE,None)
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MIN_FILTER,GL_NEAREST)
            glTexParameteri(GL_TEXTURE_2D,GL_TEXTURE_MAG_FILTER,GL_NEAREST)
            glFramebufferTexture2D(GL_FRAMEBUFFER,GL_COLOR_ATTACHMENT0,GL_TEXTURE_2D,self._pick_tex,0)
            self._depth_rb = glGenRenderbuffers(1)
            glBindRenderbuffer(GL_RENDERBUFFER,self._depth_rb)
            glRenderbufferStorage(GL_RENDERBUFFER,GL_DEPTH24_STENCIL8,self.width(),self.height())
            glFramebufferRenderbuffer(GL_FRAMEBUFFER,GL_DEPTH_ATTACHMENT,GL_RENDERBUFFER,self._depth_rb)
            if glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE:
                log.debug("Picking FBO incomplete")
            glBindFramebuffer(GL_FRAMEBUFFER,0)
        except Exception as e:
            log.debug(f"Picking FBO init failed: {e}")

    def resizeGL(self, w, h):
        # resize picking attachments
        try:
            if self._pick_tex:
                glBindTexture(GL_TEXTURE_2D, self._pick_tex)
                glTexImage2D(GL_TEXTURE_2D,0,GL_RGBA8,w,h,0,GL_RGBA,GL_UNSIGNED_BYTE,None)
            if self._depth_rb:
                glBindRenderbuffer(GL_RENDERBUFFER,self._depth_rb)
                glRenderbufferStorage(GL_RENDERBUFFER,GL_DEPTH24_STENCIL8,w,h)
        except Exception:
            pass

    def _cam_basis(self):
        cy, sy = np.cos(self.yaw), np.sin(self.yaw)
        cp, sp = np.cos(self.pitch), np.sin(self.pitch)
        # forward in -Z
        f = np.array([sy*cp, sp, -cy*cp], np.float32)
        r = np.array([ cy, 0.0,  sy], np.float32)
        u = np.cross(r, f)
        R = np.stack([r,u,-f], axis=1).astype(np.float32)  # columns
        return R

    def _update_camera(self):
        # forward vector points from cam to target, so place camera at target - f*distance
        cy, sy = np.cos(self.yaw), np.sin(self.yaw)
        cp, sp = np.cos(self.pitch), np.sin(self.pitch)
        f = np.array([sy*cp, sp, -cy*cp], np.float32)
        self.cam_pos = self.cam_target - f * self.distance
        self.update()

    def paintGL(self):
        glViewport(0,0,self.width(), self.height())
        glClearColor(*self.scene.bg_color, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        self._render_scene_internal(debug_override=None)
        self._draw_mesh_overlays()
        # Sketch overlay
        try:
            panel = self.parent()
        except Exception:
            panel = None
        if panel is not None and getattr(panel,'_sketch_on',False):
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            # Draw grid if enabled
            try:
                if getattr(panel, '_sketch_grid_on', False):
                    # Draw grid with constant on-screen spacing (pixels) and contrast color
                    self._draw_grid(p, panel)
            except Exception:
                pass
            panel._sketch.draw(p, self)
            p.end()
        # Algorithm overlays (polylines)
        if self._poly_overlays:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            for ov in self._poly_overlays:
                try:
                    pts = ov.get('pts') or []
                    if len(pts) < 2:
                        continue
                    col = ov.get('color', (120,255,160))
                    width = int(ov.get('width', 2))
                    sx, sy = ov.get('scale', (1.0, 1.0))
                    ox, oy = ov.get('offset', (0.0, 0.0))
                    pen = QPen(QColor(int(col[0]), int(col[1]), int(col[2]))); pen.setWidth(width)
                    p.setPen(pen)
                    # world z fixed at 0 for overlay
                    last = None
                    for (x,y) in pts:
                        wx = float(x)*float(sx) + float(ox)
                        wy = float(y)*float(sy) + float(oy)
                        spt = self._world_to_screen(np.array([wx, wy, 0.0], np.float32))
                        if last is not None:
                            p.drawLine(int(last[0]), int(last[1]), int(spt[0]), int(spt[1]))
                        last = spt
                except Exception:
                    continue
            p.end()

    # --- Sketch projection helpers ---
    def _world_to_screen(self, p3):
        # Simple orthographic-ish projection using camera distance for scale
        w,h = float(self.width()), float(self.height())
        # derive right/up from camera basis
        R = self._cam_basis()
        right = R[:,0]; up = R[:,1]
        rel = p3 - self.cam_pos
        x = np.dot(rel, right)
        y = np.dot(rel, up)
        s = 80.0 / max(1e-5, self.distance)
        return np.array([w*0.5 + x*s, h*0.5 - y*s], np.float32)

    def _screen_to_world_grid_snap(self, sx, sy, step):
        wpt = self._screen_to_world_xy(sx, sy)
        if step <= 0:
            return wpt
        wpt_snapped = wpt.copy()
        wpt_snapped[0] = round(wpt[0] / step) * step
        wpt_snapped[1] = round(wpt[1] / step) * step
        return wpt_snapped

    def _grid_step_world_for_panel(self, panel) -> float:
        """Return effective grid step in world units. If panel requests screen-locked grid,
        interpret panel._sketch_grid_step as pixel spacing and convert using current zoom."""
        try:
            step_cfg = float(getattr(panel, '_sketch_grid_step', 10.0))
        except Exception:
            step_cfg = 10.0
        lock_to_screen = bool(getattr(panel, '_sketch_grid_screen_lock', True))
        if lock_to_screen:
            # _world_to_screen uses s = 80 / distance, so 1 world unit = s pixels
            s = 80.0 / max(1e-5, float(self.distance))
            # desired pixel spacing -> world spacing
            return max(1e-8, float(step_cfg) / float(s))
        return max(1e-8, float(step_cfg))

    def _draw_grid(self, painter: QPainter, panel):
        # Compute world step from panel settings (optionally screen-locked)
        step_world = self._grid_step_world_for_panel(panel)
        if step_world <= 0:
            return
        w, h = self.width(), self.height()
        # Compute world bbox corners at Zâ‰ˆ0
        tl = self._screen_to_world_xy(0,0)
        br = self._screen_to_world_xy(w,h)
        xmin, xmax = sorted([tl[0], br[0]])
        ymin, ymax = sorted([tl[1], br[1]])
        import math
        x0 = math.floor(xmin/step_world)*step_world
        y0 = math.floor(ymin/step_world)*step_world
        # Choose grid color as high-contrast inverse of background
        try:
            br_, bg_, bb_ = self.scene.bg_color
        except Exception:
            br_, bg_, bb_ = (0.1, 0.1, 0.12)
        # Luminance to decide black/white, then apply slight transparency
        lum = 0.2126*br_ + 0.7152*bg_ + 0.0722*bb_
        if lum < 0.5:
            # dark background -> light grid
            cr, cg, cb, ca = 240, 240, 240, 110
        else:
            # light background -> dark grid
            cr, cg, cb, ca = 20, 20, 20, 110
        pen = QPen(QColor(int(cr), int(cg), int(cb), int(ca))); pen.setWidth(1)
        painter.setPen(pen)
        # verticals
        x = x0
        while x <= xmax:
            s1 = self._world_to_screen(np.array([x, ymin, 0.0], np.float32))
            s2 = self._world_to_screen(np.array([x, ymax, 0.0], np.float32))
            painter.drawLine(int(s1[0]), int(s1[1]), int(s2[0]), int(s2[1]))
            x += step_world
        # horizontals
        y = y0
        while y <= ymax:
            s1 = self._world_to_screen(np.array([xmin, y, 0.0], np.float32))
            s2 = self._world_to_screen(np.array([xmax, y, 0.0], np.float32))
            painter.drawLine(int(s1[0]), int(s1[1]), int(s2[0]), int(s2[1]))
            y += step_world

    def _screen_to_world_xy(self, sx, sy):
        # Map screen to world on Zâ‰ˆ0 plane
        w,h = float(self.width()), float(self.height())
        R = self._cam_basis(); right = R[:,0]; up = R[:,1]; forward = -R[:,2]
        s = 80.0 / max(1e-5, self.distance)
        dx = (sx - w*0.5)/s
        dy = -(sy - h*0.5)/s
        # construct point relative to camera
        pos = self.cam_pos + right*dx + up*dy
        # project to z=0 along forward
        if abs(forward[2]) > 1e-5:
            t = -pos[2]/forward[2]
            pos = pos + forward*t
        pos[2] = 0.0
        return pos

    def _render_scene_internal(self, debug_override=None):
        if not self.prog:
            return
        glUseProgram(self.prog)
        glUniform3f(glGetUniformLocation(self.prog,"u_cam_pos"), *self.cam_pos)
        R = self._cam_basis(); glUniformMatrix3fv(glGetUniformLocation(self.prog,"u_cam_rot"), 1, GL_FALSE, R.T)
        glUniform2f(glGetUniformLocation(self.prog,"u_res"), float(self.width()), float(self.height()))
        glUniform3f(glGetUniformLocation(self.prog,"u_env"), *self.scene.env_light)
        glUniform3f(glGetUniformLocation(self.prog,"u_bg"), *self.scene.bg_color)
        pack = self.scene.to_gpu_structs(max_prims=MAX_PRIMS)
        n = int(pack['count'])
        U = lambda name: glGetUniformLocation(self.prog, name)
        glUniform1i(U("u_count"), n)
        glUniform1iv(U("u_kind"), n, pack['kind'])
        glUniform1iv(U("u_op"), n, pack['op'])
        glUniform1fv(U("u_beta"), n, pack['beta'])
        glUniform3fv(U("u_color"), n, pack['color'])
        glUniform4fv(U("u_params"), n, pack['params'])
        glUniformMatrix4fv(U("u_xform"), n, GL_FALSE, pack['xform'])
        if 'xform_inv' in pack:
            glUniformMatrix4fv(U("u_xform_inv"), n, GL_FALSE, pack['xform_inv'])
        glUniform1i(U("u_mode"), 0)
        mode_val = self.debug_mode if debug_override is None else debug_override
        glUniform1i(U("u_debug"), int(mode_val))
        glUniform1f(U("u_far"), float(self.far_plane))
        glUniform1i(U("u_use_analytic_aa"), int(self.use_analytic_aa))
        glUniform1i(U("u_use_toon"), int(self.use_toon))
        glUniform1f(U("u_toon_levels"), float(self.toon_levels))
        glUniform1f(U("u_curv_strength"), float(self.curv_strength))
        glUniform1i(U("u_use_foveated"), int(self.use_foveated))
        glUniform1i(U("u_show_beta_overlay"), int(self.show_beta_overlay))
        glUniform1f(U("u_beta_overlay_intensity"), float(self.beta_overlay_intensity))
        glUniform1f(U("u_beta_scale"), float(self.beta_scale))
        glUniform1i(U("u_beta_cmap"), int(self.beta_cmap))
        glUniform1i(U("u_selected"), int(self.selected_index))
        glUniform1i(U("u_fractal_mode"), int(self.fractal_color_mode))
        glUniform1f(U("u_fractal_orbit_shell"), float(self.fractal_orbit_shell))
        glUniform1f(U("u_fractal_ni_scale"), float(self.fractal_ni_scale))
        glBindVertexArray(self._vao)
        glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)

    def _view_matrix(self) -> np.ndarray:
        R = self._cam_basis().astype(np.float32)
        view = np.identity(4, dtype=np.float32)
        rot = R.T
        view[:3, :3] = rot
        view[:3, 3] = -rot @ self.cam_pos.astype(np.float32)
        return view

    def _projection_matrix(self) -> np.ndarray:
        w = max(1, self.width())
        h = max(1, self.height())
        aspect = float(w) / float(h)
        fov = np.radians(45.0)
        f = 1.0 / np.tan(0.5 * fov)
        near = 0.1
        far = float(max(self.distance * 3.0, getattr(self, 'far_plane', 2000.0)))
        proj = np.zeros((4, 4), dtype=np.float32)
        proj[0, 0] = f / aspect
        proj[1, 1] = f
        proj[2, 2] = (far + near) / (near - far)
        proj[2, 3] = (2.0 * far * near) / (near - far)
        proj[3, 2] = -1.0
        return proj

    def _delete_mesh_overlay_gl(self, overlay: dict[str, object]) -> None:
        try:
            vao = int(overlay.get('vao', 0) or 0)
            if vao:
                glDeleteVertexArrays(1, [vao])
        except Exception:
            pass
        try:
            vbo = int(overlay.get('vbo', 0) or 0)
            if vbo:
                glDeleteBuffers(1, [vbo])
        except Exception:
            pass
        try:
            ebo = int(overlay.get('ebo', 0) or 0)
            if ebo:
                glDeleteBuffers(1, [ebo])
        except Exception:
            pass

    def _clear_mesh_overlays_locked(self) -> None:
        if not getattr(self, '_mesh_overlays', None):
            return
        for overlay in list(self._mesh_overlays):
            self._delete_mesh_overlay_gl(overlay)
        self._mesh_overlays = []

    def clear_mesh_overlays(self) -> None:
        if not getattr(self, '_mesh_overlays', None):
            return
        ctx = self.context()
        if ctx is None:
            self._mesh_overlays = []
            return
        try:
            self.makeCurrent()
        except Exception:
            self._mesh_overlays = []
            return
        try:
            self._clear_mesh_overlays_locked()
        finally:
            try:
                self.doneCurrent()
            except Exception:
                pass
        self.update()

    def _build_mesh_overlay(self, mesh, *, source_path: str | None = None) -> dict[str, object]:
        import numpy as _np

        if mesh is None or getattr(mesh, 'vertices', None) is None:
            raise ValueError("Mesh data is empty")

        vertices = _np.asarray(mesh.vertices, dtype=_np.float32)
        if vertices.size == 0:
            raise ValueError("Mesh has no vertices")

        faces = _np.asarray(mesh.faces, dtype=_np.uint32)
        if faces.size == 0:
            raise ValueError("Mesh has no faces")

        try:
            normals = _np.asarray(mesh.vertex_normals, dtype=_np.float32)
        except Exception:
            normals = _np.zeros_like(vertices, dtype=_np.float32)

        if normals.shape != vertices.shape or not _np.isfinite(normals).all():
            try:
                mesh.fix_normals()
                normals = _np.asarray(mesh.vertex_normals, dtype=_np.float32)
            except Exception:
                normals = _np.zeros_like(vertices, dtype=_np.float32)
        normals = _np.nan_to_num(normals, nan=0.0, posinf=0.0, neginf=0.0)

        colors = None
        try:
            vc = getattr(mesh.visual, 'vertex_colors', None)
            if vc is not None and len(vc) == len(vertices):
                colors = _np.asarray(vc, dtype=_np.float32)
        except Exception:
            colors = None

        has_color = False
        if colors is not None and colors.size:
            if colors.shape[1] >= 3:
                colors = colors[:, :3]
            if colors.max() > 1.5:
                colors = colors / 255.0
            colors = _np.clip(colors.astype(_np.float32), 0.0, 1.0)
            has_color = True
        else:
            colors = _np.zeros((vertices.shape[0], 3), dtype=_np.float32)

        interleaved = _np.hstack((vertices, normals, colors)).astype(_np.float32, copy=False)
        stride = interleaved.shape[1] * interleaved.dtype.itemsize
        indices = _np.ascontiguousarray(faces.reshape(-1), dtype=_np.uint32)

        vao = glGenVertexArrays(1)
        vbo = glGenBuffers(1)
        ebo = glGenBuffers(1)
        created = dict(vao=vao, vbo=vbo, ebo=ebo)
        try:
            glBindVertexArray(vao)
            glBindBuffer(GL_ARRAY_BUFFER, vbo)
            glBufferData(GL_ARRAY_BUFFER, interleaved.nbytes, interleaved, GL_STATIC_DRAW)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo)
            glBufferData(GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL_STATIC_DRAW)

            glEnableVertexAttribArray(0)
            glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, ctypes.c_void_p(0))
            glEnableVertexAttribArray(1)
            offset_normals = ctypes.c_void_p(3 * interleaved.dtype.itemsize)
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride, offset_normals)
            glEnableVertexAttribArray(2)
            offset_colors = ctypes.c_void_p(6 * interleaved.dtype.itemsize)
            glVertexAttribPointer(2, 3, GL_FLOAT, GL_FALSE, stride, offset_colors)

            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
        except Exception:
            glBindVertexArray(0)
            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, 0)
            self._delete_mesh_overlay_gl(created)
            raise

        fallback = colors.mean(axis=0).astype(_np.float32) if has_color else _np.array([0.85, 0.75, 0.55], dtype=_np.float32)
        fallback = _np.clip(fallback, 0.0, 1.0)

        overlay = {
            'vao': vao,
            'vbo': vbo,
            'ebo': ebo,
            'count': int(indices.size),
            'has_color': has_color,
            'model': _np.identity(4, dtype=_np.float32),
            'normal': _np.identity(3, dtype=_np.float32),
            'fallback': fallback,
            'path': source_path or "",
        }
        return overlay

    def add_mesh_overlay(self, mesh, *, source_path: str | None = None, replace_existing: bool = True, auto_fit_camera: bool = True) -> tuple[bool, str | None]:
        if self._mesh_prog is None:
            return False, "Mesh overlay shader unavailable"
        if mesh is None:
            return False, "No mesh to add"
        if self.context() is None:
            return False, "OpenGL context not ready"
        try:
            self.makeCurrent()
        except Exception as exc:
            return False, f"Unable to activate GL context: {exc}"
        try:
            if replace_existing:
                self._clear_mesh_overlays_locked()
            overlay = self._build_mesh_overlay(mesh, source_path=source_path)
            self._mesh_overlays.append(overlay)
            
            # Auto-fit camera to mesh bounding box
            if auto_fit_camera:
                try:
                    verts = np.asarray(mesh.vertices, dtype=np.float32)
                    if verts.size > 0:
                        bbox_min = verts.min(axis=0)
                        bbox_max = verts.max(axis=0)
                        bbox_size = np.linalg.norm(bbox_max - bbox_min)
                        center = (bbox_min + bbox_max) / 2.0
                        
                        # Set camera distance to 1.5x the bounding sphere (fits nicely)
                        new_dist = float(max(bbox_size * 1.5, 5.0))
                        self.distance = new_dist
                        
                        # Adjust far plane to see the whole mesh
                        self.far_plane = float(max(new_dist * 3.0, 500.0))
                        
                        # Center the camera target on the mesh center
                        self.cam_target = center.tolist()
                        self._update_camera()
                except Exception:
                    pass
        except Exception as exc:
            return False, str(exc)
        finally:
            try:
                self.doneCurrent()
            except Exception:
                pass
        self.update()
        return True, None

    def _draw_mesh_overlays(self) -> None:
        if not self._mesh_prog or not self._mesh_overlays:
            return
        try:
            glUseProgram(self._mesh_prog)
        except Exception as exc:
            log.debug(f"Mesh overlay program unavailable: {exc}")
            return

        view = self._view_matrix()
        proj = self._projection_matrix()
        mvp_uniform = self._mesh_uniforms.get('u_mvp') if self._mesh_uniforms else None
        if mvp_uniform is None:
            return

        cam_pos = np.array(self.cam_pos, dtype=np.float32)
        light_dir = np.array(self.scene.env_light, dtype=np.float32)
        norm = np.linalg.norm(light_dir)
        if norm < 1e-5:
            light_dir = np.array([0.6, 0.8, 0.9], dtype=np.float32)
        else:
            light_dir = (light_dir / norm).astype(np.float32)

        glUniform3fv(self._mesh_uniforms['u_cam_pos'], 1, cam_pos)
        glUniform3fv(self._mesh_uniforms['u_light_dir'], 1, light_dir)

        glEnable(GL_DEPTH_TEST)
        glDepthFunc(GL_LESS)
        glClear(GL_DEPTH_BUFFER_BIT)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        for overlay in self._mesh_overlays:
            try:
                model = np.array(overlay.get('model'), dtype=np.float32)
                normal = np.array(overlay.get('normal'), dtype=np.float32)
                mvp = proj @ view @ model
                glUniformMatrix4fv(self._mesh_uniforms['u_mvp'], 1, GL_FALSE, mvp.astype(np.float32).T)
                glUniformMatrix4fv(self._mesh_uniforms['u_model'], 1, GL_FALSE, model.astype(np.float32).T)
                glUniformMatrix3fv(self._mesh_uniforms['u_normal'], 1, GL_FALSE, normal.astype(np.float32).T)
                fallback = np.array(overlay.get('fallback', np.array([0.8, 0.7, 0.6], dtype=np.float32)), dtype=np.float32)
                glUniform3fv(self._mesh_uniforms['u_fallback_color'], 1, fallback)
                glUniform1i(self._mesh_uniforms['u_has_vertex_color'], 1 if overlay.get('has_color') else 0)
                glBindVertexArray(int(overlay['vao']))
                glDrawElements(GL_TRIANGLES, int(overlay['count']), GL_UNSIGNED_INT, None)
            except Exception as exc:
                log.debug(f"Mesh overlay draw failed: {exc}")
                continue

        glBindVertexArray(0)
        glDisable(GL_BLEND)
        glDisable(GL_DEPTH_TEST)
        glUseProgram(0)

    def _draw_frame(self, debug_override=None):  # retained for other callers
        glViewport(0,0,self.width(), self.height())
        glClearColor(*self.scene.bg_color, 1.0)
        glClear(GL_COLOR_BUFFER_BIT)
        self._render_scene_internal(debug_override)

    def keyPressEvent(self, event):
        k = event.key()
        changed = False
        # number keys for debug modes
        if k in (Qt.Key_0, Qt.Key.Key_0): self.debug_mode=0; changed=True
        elif k in (Qt.Key_1, Qt.Key.Key_1): self.debug_mode=1; changed=True
        elif k in (Qt.Key_2, Qt.Key.Key_2): self.debug_mode=2; changed=True
        elif k in (Qt.Key_3, Qt.Key.Key_3): self.debug_mode=3; changed=True
        elif k in (Qt.Key_4, Qt.Key.Key_4): self.debug_mode=4; changed=True
        elif k in (Qt.Key_5, Qt.Key.Key_5): self.debug_mode=5; changed=True  # adaptive heatmap
        elif k == Qt.Key_Space:
            self.debug_mode = (self.debug_mode + 1) % 6; changed=True
        elif k == Qt.Key_A: self.use_analytic_aa ^=1; changed=True
        elif k == Qt.Key_F: self.use_foveated ^=1; changed=True
        elif k == Qt.Key_T: self.use_toon ^=1; changed=True
        elif k == Qt.Key_Plus or k == Qt.Key_Equal: # '+' (with shift) or '='
            self.toon_levels = min(self.toon_levels+1.0, 8.0); changed=True
        elif k == Qt.Key_Minus: self.toon_levels = max(self.toon_levels-1.0, 1.0); changed=True
        elif k == Qt.Key_C:
            # cycle curvature strength
            if self.curv_strength < 0.25: self.curv_strength = 0.5
            elif self.curv_strength < 0.75: self.curv_strength = 1.0
            else: self.curv_strength = 0.0
            changed=True
        elif k == Qt.Key_G: self.save_gbuffers(); return
        elif k == Qt.Key_H:
            log.info(self._shortcuts_help())
        elif k == Qt.Key_B:
            self.show_beta_overlay ^=1; changed=True
        elif k == Qt.Key_Period: # increase beta overlay intensity
            self.beta_overlay_intensity = min(1.0, self.beta_overlay_intensity+0.05); changed=True
        elif k == Qt.Key_Comma:  # decrease intensity
            self.beta_overlay_intensity = max(0.0, self.beta_overlay_intensity-0.05); changed=True
        elif k == Qt.Key_Slash:  # increase beta scale
            self.beta_scale = min(8.0, self.beta_scale * 1.25); changed=True
        elif k == Qt.Key_Question: # SHIFT + '/' may map same; ensure alternative
            self.beta_scale = min(8.0, self.beta_scale * 1.25); changed=True
        elif k == Qt.Key_Backslash: # decrease beta scale
            self.beta_scale = max(0.125, self.beta_scale / 1.25); changed=True
        elif k == Qt.Key_V: # cycle beta color map
            self.beta_cmap = (self.beta_cmap + 1) % 4; changed=True
        if changed:
            self._update_title(); self.update(); self._save_settings()
        else:
            try:
                panel = self.parent()
            except Exception:
                panel = None
            # Sketch polyline finalize / undo
            if panel is not None and getattr(panel,'_sketch_on',False) and panel._sketch_mode=='polyline':
                if k in (Qt.Key_Return, Qt.Key_Enter):
                    if panel._sketch.active_poly and len(panel._sketch.active_poly.pts)>=2:
                        panel._sketch.entities.append(panel._sketch.active_poly)
                    panel._sketch.active_poly = None
                    self.update(); return
                elif k == Qt.Key_Escape:
                    if panel._sketch.active_poly and panel._sketch.active_poly.pts:
                        panel._sketch.active_poly.pts.pop()
                        if not panel._sketch.active_poly.pts:
                            panel._sketch.active_poly = None
                        self.update(); return
            # Cancel dimension placing with ESC
            if panel is not None and getattr(panel,'_sketch_on',False) and k == Qt.Key_Escape:
                try:
                    panel._sketch._dim_placing = False; panel._sketch._dim_place_data = None; panel._sketch._dim_preview = None
                except Exception:
                    pass
                self.update(); return
            # Sketch delete selected vertex/entity
            if panel is not None and getattr(panel,'_sketch_on',False) and k in (Qt.Key_Delete, Qt.Key_Backspace):
                if self._delete_selected_sketch():
                    try:
                        if hasattr(panel, '_update_sketch_info'):
                            panel._update_sketch_info(self._sk_point_sel)
                    except Exception:
                        pass
                    self.update(); return
            # Gizmo mode shortcuts
            if panel is not None:
                if k == Qt.Key_R:
                    panel._gizmo_mode = 'rotate'; self.update(); return
                elif k == Qt.Key_S and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                    panel._gizmo_mode = 'scale'; self.update(); return
                elif k == Qt.Key_M:
                    panel._gizmo_mode = 'move'; self.update(); return
                elif k == Qt.Key_X:
                    panel._axis_lock = 'x'; return
                elif k == Qt.Key_Y:
                    panel._axis_lock = 'y'; return
                elif k == Qt.Key_Z:
                    panel._axis_lock = 'z'; return
                elif k == Qt.Key_Escape and not (getattr(panel,'_sketch_on',False) and panel._sketch_mode=='polyline'):
                    panel._axis_lock = None; return
            # --- Keyboard nudges (view-aligned + world-aligned) ---
            pr = self._current_prim()
            if pr is not None:
                # determine step
                step_widget = getattr(self.parent(), '_nudge_step', None)
                try:
                    step = float(step_widget.value()) if step_widget is not None else 1.0
                except Exception:
                    step = 1.0
                moved = False
                basis = self._cam_basis()
                pos_vec = pr.xform.M[:3,3].astype(np.float32)
                # View-aligned (WASD + Q/E)
                if k == Qt.Key_W: pos_vec += basis[:,1]*step; moved=True
                elif k == Qt.Key_S: pos_vec -= basis[:,1]*step; moved=True
                elif k == Qt.Key_D: pos_vec += basis[:,0]*step; moved=True
                elif k == Qt.Key_A: pos_vec -= basis[:,0]*step; moved=True
                elif k == Qt.Key_E: pos_vec -= basis[:,2]*step; moved=True  # forward (-Z in basis third column sign depending)
                elif k == Qt.Key_Q: pos_vec += basis[:,2]*step; moved=True
                # World-aligned (arrows + PgUp/PgDn)
                elif k == Qt.Key_Up: pos_vec += np.array([0,step,0], np.float32); moved=True
                elif k == Qt.Key_Down: pos_vec -= np.array([0,step,0], np.float32); moved=True
                elif k == Qt.Key_Right: pos_vec += np.array([step,0,0], np.float32); moved=True
                elif k == Qt.Key_Left: pos_vec -= np.array([step,0,0], np.float32); moved=True
                elif k == Qt.Key_PageUp: pos_vec += np.array([0,0,step], np.float32); moved=True
                elif k == Qt.Key_PageDown: pos_vec -= np.array([0,0,step], np.float32); moved=True
                if moved:
                    self._apply_panel_move(pos_vec)
                    return
            super().keyPressEvent(event)

    # --- Polyline overlay API ---
    def clear_polyline_overlays(self):
        try:
            self._poly_overlays.clear()
        except Exception:
            self._poly_overlays = []
        self.update()

    def add_polyline_overlay(self, pts, color=(120,255,160), width=3, scale=(1.0,1.0), offset=(0.0,0.0)):
        try:
            self._poly_overlays.append({
                'pts': list(pts) if pts is not None else [],
                'color': tuple(color),
                'width': int(width),
                'scale': tuple(scale),
                'offset': tuple(offset),
            })
        except Exception:
            pass
        self.update()

    # --- Mouse Interaction ---
    def mousePressEvent(self, event: QMouseEvent):
        self._last_mouse = event.position()
        self._last_buttons = event.buttons()
        mods = event.modifiers()
        move_shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        move_ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        try:
            panel = self.parent()
        except Exception:
            panel = None
        gizmo_move = bool(panel is not None and getattr(panel, '_move_drag_free', False))
        # Plain LMB (no modifiers) -> pick
        if event.button() == Qt.MouseButton.LeftButton and mods == Qt.KeyboardModifier.NoModifier:
            # Use full-resolution FBO picking for accurate coordinate-based selection.
            try:
                self._perform_pick(int(event.position().x()), int(event.position().y()))
                pid = self.selected_index
                if pid >= 0:
                    try:
                        if hasattr(self.parent(), '_select_prim'):
                            self.parent()._select_prim(pid)
                    except Exception:
                        pass
                self.update()
            except Exception as e:
                log.debug(f"mousePressEvent pick failed: {e}")
        # Shift + LMB -> begin move-drag if a primitive selected
        if (event.button() == Qt.MouseButton.LeftButton and
            self._current_prim() is not None and
            (move_shift or move_ctrl or gizmo_move)):
            self._drag_move_active = True
            self._drag_last_pos = event.position()
        # Sketch polyline placement (before default)
        if panel is None:
            try:
                panel = self.parent()
            except Exception:
                panel = None
        if panel is not None and getattr(panel,'_sketch_on',False) and event.button()==Qt.MouseButton.LeftButton:
            mode = panel._sketch_mode
            if getattr(panel, '_sketch_snap_grid', False):
                step = self._grid_step_world_for_panel(panel)
                w3 = self._screen_to_world_grid_snap(event.position().x(), event.position().y(), step)
            else:
                w3 = self._screen_to_world_xy(event.position().x(), event.position().y())
            pt_world2 = panel._sketch.hover_snap if panel._sketch.hover_snap is not None else w3[:2]
            if mode=='polyline':
                if panel._sketch.active_poly is None:
                    panel._sketch.active_poly = Polyline2D([])
                panel._sketch.active_poly.pts.append(np.array([pt_world2[0],pt_world2[1]], np.float32))
                self.update(); return
            elif mode=='circle':
                if panel._sketch.active_shape is None:
                    panel._sketch.active_shape = Circle2D(pt_world2, 0.0)
                else:
                    # finalize
                    if isinstance(panel._sketch.active_shape, Circle2D) and panel._sketch.active_shape.radius>0:
                        panel._sketch.entities.append(panel._sketch.active_shape)
                        # Optional kernel sync: add a thin torus ring at same center/radius
                        try:
                            if bool(getattr(panel, '_sketch_circle_to_ring', False)):
                                c = panel._sketch.active_shape
                                R = float(max(1e-6, c.radius))
                                r = max(0.01, R * 0.05)
                                pr = Prim(KIND_TORUS, [R, r, 0.0, 0.0], beta=0.0, color=(0.9,0.7,0.3))
                                if hasattr(pr, 'set_transform'):
                                    pr.set_transform(pos=[float(c.center[0]), float(c.center[1]), 0.0], euler=[0.0,0.0,0.0], scale=[1.0,1.0,1.0])
                                else:
                                    pr.xform.M[:3,3] = np.array([float(c.center[0]), float(c.center[1]), 0.0], np.float32)
                                self.scene.add(pr)
                        except Exception as _e:
                            try:
                                log.debug(f"circleâ†’kernel sync failed: {_e}")
                            except Exception:
                                pass
                    panel._sketch.active_shape = None
                self.update(); return
            elif mode=='rect':
                if panel._sketch.active_shape is None:
                    panel._sketch.active_shape = Rect2D(pt_world2)
                else:
                    if isinstance(panel._sketch.active_shape, Rect2D):
                        panel._sketch.active_shape.p1 = np.array([pt_world2[0],pt_world2[1]], np.float32)
                        if panel._sketch.active_shape.p1 is not None:
                            panel._sketch.entities.append(panel._sketch.active_shape)
                    panel._sketch.active_shape = None
                self.update(); return
            elif mode=='line':
                if panel._sketch.active_shape is None:
                    panel._sketch.active_shape = Line2D(pt_world2)
                else:
                    if isinstance(panel._sketch.active_shape, Line2D):
                        panel._sketch.active_shape.p1 = np.array([pt_world2[0],pt_world2[1]], np.float32)
                        panel._sketch.entities.append(panel._sketch.active_shape)
                    panel._sketch.active_shape = None
                self.update(); return
            elif mode=='arc3':
                if panel._sketch.active_shape is None:
                    panel._sketch.active_shape = Arc2D(pt_world2, None, None)
                elif isinstance(panel._sketch.active_shape, Arc2D) and panel._sketch.active_shape.p1 is None:
                    panel._sketch.active_shape.p1 = np.array([pt_world2[0],pt_world2[1]], np.float32)
                else:
                    if isinstance(panel._sketch.active_shape, Arc2D):
                        panel._sketch.active_shape.p2 = np.array([pt_world2[0],pt_world2[1]], np.float32)
                        panel._sketch.entities.append(panel._sketch.active_shape)
                    panel._sketch.active_shape = None
                self.update(); return
            elif mode=='dimension':
                # Typed placement: Linear/H/V = pick A, pick B, then click to set offset; Radius/Diameter use circle center
                # If we are in placing phase, compute offset and finalize
                if panel._sketch._dim_placing and isinstance(panel._sketch._dim_place_data, dict):
                    dt = panel._sketch._dim_place_data.get('type','linear')
                    a = panel._sketch._dim_place_data.get('a'); b = panel._sketch._dim_place_data.get('b')
                    # current mouse world point
                    hit = self._screen_to_world_xy(event.position().x(), event.position().y())
                    wpt = np.array([hit[0], hit[1]], np.float32)
                    # derive offset along normal
                    if dt == 'horizontal':
                        pa = self._ref_to_xy(a); pb = self._ref_to_xy(b)
                        if pa is None or pb is None:
                            panel._sketch._dim_placing = False; panel._sketch._dim_place_data = None; return
                        off = float(wpt[1] - pa[1])
                        panel._sketch.dimensions.append(DimHorizontal2D(a, b, panel, offset=off))
                    elif dt == 'vertical':
                        pa = self._ref_to_xy(a); pb = self._ref_to_xy(b)
                        if pa is None or pb is None:
                            panel._sketch._dim_placing = False; panel._sketch._dim_place_data = None; return
                        off = float(wpt[0] - pa[0])
                        panel._sketch.dimensions.append(DimVertical2D(a, b, panel, offset=off))
                    else:
                        # general: offset is signed distance from mouse to AB line along its normal
                        pa = self._ref_to_xy(a); pb = self._ref_to_xy(b)
                        if pa is None or pb is None:
                            panel._sketch._dim_placing = False; panel._sketch._dim_place_data = None; return
                        v = pb - pa; L = float(np.linalg.norm(v))
                        if L < 1e-6:
                            panel._sketch._dim_placing = False; panel._sketch._dim_place_data = None; return
                        n = np.array([-v[1], v[0]], np.float32) / L
                        off = float(np.dot(wpt - pa, n))
                        panel._sketch.dimensions.append(DimLinear2D(a, b, panel, offset=off))
                    # reset state
                    panel._sketch._dim_pick = None; panel._sketch._dim_preview = None
                    panel._sketch._dim_placing = False; panel._sketch._dim_place_data = None
                    self.update(); return
                # Otherwise proceed with picking references
                sel = self._pick_nearest_sketch_vertex(event.position().x(), event.position().y())
                if sel is None:
                    return
                dt = getattr(panel, '_dim_type', 'linear')
                if dt in ('radius','diameter'):
                    if isinstance(sel, tuple) and sel[0]=='circle' and isinstance(sel[1], Circle2D):
                        if dt=='radius':
                            panel._sketch.dimensions.append(DimRadius2D(('circle', sel[1]), panel))
                        else:
                            panel._sketch.dimensions.append(DimDiameter2D(('circle', sel[1]), panel))
                        self.update(); return
                    else:
                        return
                # two-point dims: pick A then B, then enter placing phase
                if panel._sketch._dim_pick is None:
                    panel._sketch._dim_pick = sel
                else:
                    a = panel._sketch._dim_pick; b = sel
                    panel._sketch._dim_place_data = {'type': dt, 'a': a, 'b': b}
                    panel._sketch._dim_placing = True
                    # create a preview with zero offset first
                    if dt=='horizontal':
                        panel._sketch._dim_preview = DimHorizontal2D(a, b, panel, offset=0.0)
                    elif dt=='vertical':
                        panel._sketch._dim_preview = DimVertical2D(a, b, panel, offset=0.0)
                    else:
                        panel._sketch._dim_preview = DimLinear2D(a, b, panel, offset=0.0)
                    self.update(); return
            elif mode=='insert_vertex':
                # Insert on nearest polyline segment or split a line
                try:
                    w2 = np.array([pt_world2[0], pt_world2[1]], np.float32)
                    best_px = 1e9; best_ent = None; best_idx = -1; best_point = None
                    for ent in panel._sketch.entities:
                        if isinstance(ent, Polyline2D) and len(ent.pts) >= 2:
                            for i in range(len(ent.pts)-1):
                                a = ent.pts[i]; b = ent.pts[i+1]
                                ab = b - a; t = 0.0
                                denom = float(np.dot(ab, ab));
                                if denom > 1e-9:
                                    t = max(0.0, min(1.0, float(np.dot(w2 - a, ab) / denom)))
                                p = a + t*ab
                                s = self._world_to_screen(np.array([p[0], p[1], 0.0], np.float32))
                                dpx = float(np.hypot(s[0]-event.position().x(), s[1]-event.position().y()))
                                if dpx < best_px:
                                    best_px = dpx; best_ent = ent; best_idx = i+1; best_point = p
                        elif isinstance(ent, Line2D) and ent.p1 is not None:
                            a = ent.p0; b = ent.p1
                            ab = b - a; t = 0.0
                            denom = float(np.dot(ab, ab));
                            if denom > 1e-9:
                                t = max(0.0, min(1.0, float(np.dot(w2 - a, ab) / denom)))
                            p = a + t*ab
                            s = self._world_to_screen(np.array([p[0], p[1], 0.0], np.float32))
                            dpx = float(np.hypot(s[0]-event.position().x(), s[1]-event.position().y()))
                            if dpx < best_px:
                                best_px = dpx; best_ent = ent; best_idx = 1; best_point = p
                    # threshold in pixels
                    if best_ent is None or best_px > 12.0:
                        return
                    if isinstance(best_ent, Polyline2D):
                        ins = best_point if getattr(panel, '_insert_midpoint', False) else w2
                        best_ent.pts.insert(best_idx, ins.astype(np.float32))
                    elif isinstance(best_ent, Line2D):
                        # split into two lines
                        a = best_ent.p0; b = best_ent.p1
                        mid = (best_point if getattr(panel, '_insert_midpoint', False) else w2).copy()
                        panel._sketch.entities.remove(best_ent)
                        panel._sketch.entities.append(Line2D(a, mid))
                        panel._sketch.entities.append(Line2D(mid, b))
                    self.update(); return
                except Exception:
                    return
            # Selection of nearest sketch vertex (Ctrl+Click)
            if mods & Qt.KeyboardModifier.ControlModifier:
                sel = self._pick_nearest_sketch_vertex(event.position().x(), event.position().y())
                self._sk_point_sel = sel
                self._sk_dragging = sel is not None
                try:
                    if hasattr(panel, '_update_sketch_info'):
                        panel._update_sketch_info(sel)
                except Exception:
                    pass
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._last_mouse is None:
            self._last_mouse = event.position()
        dx = event.position().x() - self._last_mouse.x()
        dy = event.position().y() - self._last_mouse.y()
        mods = event.modifiers()
        move_shift = bool(mods & Qt.KeyboardModifier.ShiftModifier)
        move_ctrl = bool(mods & Qt.KeyboardModifier.ControlModifier)
        alt_mask = Qt.KeyboardModifier.AltModifier
        try:
            panel = self.parent()
        except Exception:
            panel = None
        gizmo_move = bool(panel is not None and getattr(panel, '_move_drag_free', False))
        if (not self._drag_move_active and (event.buttons() & Qt.MouseButton.LeftButton) and
                self._current_prim() is not None and (move_shift or move_ctrl or gizmo_move)):
            self._drag_move_active = True
            self._drag_last_pos = event.position()
        # Sketch hover snapping
        if panel is not None and getattr(panel,'_sketch_on',False):
            hit = self._screen_to_world_xy(event.position().x(), event.position().y())
            wpt = np.array([hit[0], hit[1]], np.float32)
            snap = None; best = 1e9
            for sp in panel._sketch.all_snap_points():
                scr_sp = self._world_to_screen(np.array([sp[0],sp[1],0.0], np.float32))
                dpx = float(np.hypot(scr_sp[0]-event.position().x(), scr_sp[1]-event.position().y()))
                if dpx < SNAP_PX and dpx < best:
                    best = dpx; snap = sp
            panel._sketch.hover_snap = snap if snap is not None else wpt
            # live update active shape dimensions
            if panel._sketch_mode=='circle' and isinstance(panel._sketch.active_shape, Circle2D):
                c = panel._sketch.active_shape.center
                panel._sketch.active_shape.radius = float(np.linalg.norm(wpt - c))
            elif panel._sketch_mode=='rect' and isinstance(panel._sketch.active_shape, Rect2D):
                panel._sketch.active_shape.p1 = wpt.copy()
            elif panel._sketch_mode=='line' and isinstance(panel._sketch.active_shape, Line2D):
                panel._sketch.active_shape.p1 = wpt.copy()
            elif panel._sketch_mode=='arc3' and isinstance(panel._sketch.active_shape, Arc2D):
                if panel._sketch.active_shape.p1 is None:
                    panel._sketch.active_shape.p1 = wpt.copy()
                else:
                    panel._sketch.active_shape.p2 = wpt.copy()
            # dimension live preview
            if panel._sketch_mode=='dimension':
                # If in placing phase, update preview offset dynamically
                if panel._sketch._dim_placing and isinstance(panel._sketch._dim_place_data, dict):
                    hit = self._screen_to_world_xy(event.position().x(), event.position().y())
                    wpt2 = np.array([hit[0], hit[1]], np.float32)
                    dt = panel._sketch._dim_place_data.get('type','linear')
                    a = panel._sketch._dim_place_data.get('a'); b = panel._sketch._dim_place_data.get('b')
                    if dt == 'horizontal':
                        pa = self._ref_to_xy(a)
                        off = float(wpt2[1] - (pa[1] if pa is not None else wpt2[1]))
                        panel._sketch._dim_preview = DimHorizontal2D(a, b, panel, offset=off)
                    elif dt == 'vertical':
                        pa = self._ref_to_xy(a)
                        off = float(wpt2[0] - (pa[0] if pa is not None else wpt2[0]))
                        panel._sketch._dim_preview = DimVertical2D(a, b, panel, offset=off)
                    else:
                        pa = self._ref_to_xy(a); pb = self._ref_to_xy(b)
                        if pa is not None and pb is not None:
                            v = pb - pa; L = float(np.linalg.norm(v))
                            if L > 1e-6:
                                n = np.array([-v[1], v[0]], np.float32) / L
                                off = float(np.dot(wpt2 - pa, n))
                                panel._sketch._dim_preview = DimLinear2D(a, b, panel, offset=off)
                else:
                    sel = self._pick_nearest_sketch_vertex(event.position().x(), event.position().y())
                    dt = getattr(panel, '_dim_type', 'linear')
                    panel._sketch._dim_preview = None
                    if dt in ('radius','diameter'):
                        if isinstance(sel, tuple) and sel[0]=='circle' and isinstance(sel[1], Circle2D):
                            if dt=='radius':
                                panel._sketch._dim_preview = DimRadius2D(('circle', sel[1]), panel)
                            else:
                                panel._sketch._dim_preview = DimDiameter2D(('circle', sel[1]), panel)
                    else:
                        a = panel._sketch._dim_pick
                        b = sel if sel is not None else (panel._sketch.hover_snap if panel._sketch.hover_snap is not None else wpt)
                        if a is not None and b is not None:
                            if dt=='horizontal':
                                panel._sketch._dim_preview = DimHorizontal2D(a, b, panel)
                            elif dt=='vertical':
                                panel._sketch._dim_preview = DimVertical2D(a, b, panel)
                            else:
                                panel._sketch._dim_preview = DimLinear2D(a, b, panel)
            self.update()
            # Drag selected vertex (if any)
            if self._sk_dragging and self._sk_point_sel is not None and (event.buttons() & Qt.MouseButton.LeftButton):
                if getattr(panel, '_sketch_snap_grid', False):
                    step = self._grid_step_world_for_panel(panel)
                    w3 = self._screen_to_world_grid_snap(event.position().x(), event.position().y(), step)
                else:
                    w3 = self._screen_to_world_xy(event.position().x(), event.position().y())
                self._move_selected_sketch_vertex(np.array([w3[0], w3[1]], np.float32))
                try:
                    if hasattr(panel, '_update_sketch_info'):
                        panel._update_sketch_info(self._sk_point_sel)
                except Exception:
                    pass
                self.update()
        # Gizmo rotate / scale (invisible gizmo) using horizontal drag
        try:
            panel = self.parent()
        except Exception:
            panel = None
        if panel is not None and hasattr(panel, '_gizmo_mode') and panel._gizmo_mode in ("rotate","scale") and panel._current_sel >= 0:
            if event.buttons() & Qt.MouseButton.LeftButton:  # require LMB drag
                pr = self.scene.prims[panel._current_sel]
                axis = panel._axis_lock or 'z'
                local_space = bool(getattr(panel, '_space_local', True))
                if panel._gizmo_mode == 'rotate':
                    sens_rot = 0.25  # degrees per pixel
                    raw_deg = dx * sens_rot
                    use_snap = not bool(mods & alt_mask)
                    deg = _snap_angle(raw_deg, panel._snap_angle_deg) if use_snap else raw_deg
                    R = _make_rot(axis, deg)
                    if local_space:
                        pr.xform.M = pr.xform.M @ R
                    else:
                        T = np.eye(4, dtype=np.float32); T[:3,3] = pr.xform.M[:3,3]
                        Tinv = np.eye(4, dtype=np.float32); Tinv[:3,3] = -pr.xform.M[:3,3]
                        pr.xform.M = T @ R @ Tinv @ pr.xform.M
                    try: self.scene._notify()
                    except Exception: pass
                    try: panel._select_prim(panel._current_sel)
                    except Exception: pass
                    self.update(); self._last_mouse = event.position(); return
                elif panel._gizmo_mode == 'scale':
                    sens_scl = 0.005  # scale factor per pixel
                    raw = 1.0 + dx * sens_scl
                    raw = max(0.01, raw)
                    use_snap = not bool(mods & alt_mask)
                    k = _snap_scale(raw, panel._snap_scale_step) if use_snap else raw
                    S = _make_scale(axis, k)
                    if local_space:
                        pr.xform.M = pr.xform.M @ S
                    else:
                        T = np.eye(4, dtype=np.float32); T[:3,3] = pr.xform.M[:3,3]
                        Tinv = np.eye(4, dtype=np.float32); Tinv[:3,3] = -pr.xform.M[:3,3]
                        pr.xform.M = T @ S @ Tinv @ pr.xform.M
                    try: self.scene._notify()
                    except Exception: pass
                    try: panel._select_prim(panel._current_sel)
                    except Exception: pass
                    self.update(); self._last_mouse = event.position(); return
        # Screen-plane translate when active
        if self._drag_move_active and self._drag_last_pos is not None:
            dx2 = event.position().x() - self._drag_last_pos.x()
            dy2 = event.position().y() - self._drag_last_pos.y()
            R = self._cam_basis(); right = R[:,0]; up = R[:,1]
            step = self.distance * 0.0015
            dp = right * dx2 * step - up * dy2 * step
            pr = self._current_prim()
            if pr is not None:
                prev_pos = pr.xform.M[:3,3].copy()
                new_pos = prev_pos + dp.astype(np.float32)
                pr.xform.M[:3,3] = new_pos
                try:
                    self.scene._notify()
                except Exception:
                    pass
                self._apply_panel_move(new_pos)
            self._drag_last_pos = event.position()
            return
        buttons = event.buttons() or self._last_buttons
        updated = False
        # Orbit (LMB) â€” disabled if sketch lock top is enabled
        lock_top = False
        try:
            panel = self.parent()
            lock_top = bool(getattr(panel, '_sketch_on', False) and getattr(panel, '_sketch_lock_top', False))
        except Exception:
            lock_top = False
        if (buttons & Qt.MouseButton.LeftButton) and not lock_top:
            sens = 0.005
            self.yaw   += dx * sens
            self.pitch += dy * sens
            # clamp pitch to avoid gimbal flip
            self.pitch = float(np.clip(self.pitch, -1.45, 1.45))
            self._update_camera()
            updated = True
        # Pan (RMB) â€” disabled if sketch lock top is enabled
        if (buttons & Qt.MouseButton.RightButton) and not lock_top:
            # derive right/up from current basis
            R = self._cam_basis()
            right = R[:,0]; up = R[:,1]
            pan_sens = self.distance * 0.0015
            self.cam_target -= right * dx * pan_sens
            self.cam_target += up * dy * pan_sens
            self._update_camera()
            updated = True
        self._last_mouse = event.position()
        if not updated:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_move_active = False
            self._drag_last_pos = None
            self._sk_dragging = False
        super().mouseReleaseEvent(event)

    def _pick_nearest_sketch_vertex(self, sx: float, sy: float):
        try:
            panel = self.parent()
        except Exception:
            return None
        if panel is None:
            return None
        best = 1e9; best_key = None
        # Search polyline points, line endpoints/midpoints, rect corners/edges/center, circle centers
        for ent in getattr(panel, '_sketch').entities:
            if isinstance(ent, Polyline2D):
                for idx, pt in enumerate(ent.pts):
                    s = self._world_to_screen(np.array([pt[0], pt[1], 0.0], np.float32))
                    d = float(np.hypot(s[0]-sx, s[1]-sy))
                    if d < best and d <= 12.0:
                        best = d; best_key = (ent, idx)
            elif isinstance(ent, Line2D):
                pts = [ent.p0] + ([ent.p1] if ent.p1 is not None else [])
                for idx, pt in enumerate(pts):
                    s = self._world_to_screen(np.array([pt[0], pt[1], 0.0], np.float32))
                    d = float(np.hypot(s[0]-sx, s[1]-sy))
                    if d < best and d <= 12.0:
                        best = d; best_key = (ent, idx)
                if ent.p1 is not None:
                    mid = (ent.p0 + ent.p1) * 0.5
                    s = self._world_to_screen(np.array([mid[0], mid[1], 0.0], np.float32))
                    d = float(np.hypot(s[0]-sx, s[1]-sy))
                    if d < best and d <= 12.0:
                        best = d; best_key = (ent, ('mid', 0))
            elif isinstance(ent, Rect2D):
                corners = ent.corners()
                for idx, pt in enumerate(corners):
                    s = self._world_to_screen(np.array([pt[0], pt[1], 0.0], np.float32))
                    d = float(np.hypot(s[0]-sx, s[1]-sy))
                    if d < best and d <= 12.0:
                        best = d; best_key = (ent, idx)
                if len(corners) >= 2:
                    for edge_idx, (a, b) in enumerate(zip(corners, corners[1:]+corners[:1])):
                        mid = (a + b) * 0.5
                        s = self._world_to_screen(np.array([mid[0], mid[1], 0.0], np.float32))
                        d = float(np.hypot(s[0]-sx, s[1]-sy))
                        if d < best and d <= 12.0:
                            best = d; best_key = (ent, ('edge_mid', edge_idx))
                if len(corners) == 4:
                    cx = sum(c[0] for c in corners) / 4.0
                    cy = sum(c[1] for c in corners) / 4.0
                    s = self._world_to_screen(np.array([cx, cy, 0.0], np.float32))
                    d = float(np.hypot(s[0]-sx, s[1]-sy))
                    if d < best and d <= 12.0:
                        best = d; best_key = (ent, 'center')
            elif isinstance(ent, Circle2D):
                c = ent.center
                s = self._world_to_screen(np.array([c[0], c[1], 0.0], np.float32))
                d = float(np.hypot(s[0]-sx, s[1]-sy))
                if d < best and d <= 12.0:
                    best = d; best_key = ('circle', ent)
        return best_key

    def _move_selected_sketch_vertex(self, new_xy: np.ndarray):
        key = self._sk_point_sel
        if key is None:
            return
        if isinstance(key, tuple) and len(key)==2 and isinstance(key[0], Polyline2D):
            ent, idx = key
            if 0 <= idx < len(ent.pts):
                ent.pts[idx] = new_xy.copy()
        elif isinstance(key, tuple) and key[0] == 'circle' and isinstance(key[1], Circle2D):
            key[1].center = new_xy.copy()

    def _delete_selected_sketch(self) -> bool:
        try:
            panel = self.parent()
        except Exception:
            panel = None
        if panel is None or not getattr(panel, '_sketch_on', False):
            return False
        key = self._sk_point_sel
        # Delete logic: if a polyline vertex is selected, remove it; drop entity if < 2 pts.
        # If a circle center selected, remove the circle entity.
        if key is None:
            # fallback: delete last entity if any
            if panel._sketch.entities:
                panel._sketch.entities.pop()
                return True
            return False
        if isinstance(key, tuple) and len(key)==2 and isinstance(key[0], Polyline2D):
            ent, idx = key
            try:
                if 0 <= idx < len(ent.pts):
                    ent.pts.pop(idx)
                    if len(ent.pts) < 2 and ent in panel._sketch.entities:
                        panel._sketch.entities.remove(ent)
                    self._sk_point_sel = None
                    return True
            except Exception:
                return False
        elif isinstance(key, tuple) and key[0] == 'circle' and isinstance(key[1], Circle2D):
            ent = key[1]
            try:
                if ent in panel._sketch.entities:
                    panel._sketch.entities.remove(ent)
                self._sk_point_sel = None
                return True
            except Exception:
                return False
        return False

    # --- Selection + panel sync helpers ---
    def _current_prim(self):
        try:
            panel = self.parent()
            if hasattr(panel, '_current_sel') and 0 <= panel._current_sel < len(self.scene.prims):
                return self.scene.prims[panel._current_sel]
        except Exception:
            return None
        return None

    def _apply_panel_move(self, new_pos):
        panel = self.parent()
        try:
            if hasattr(panel, '_sp_move'):
                for i,v in enumerate(new_pos):
                    panel._sp_move[i].blockSignals(True)
                    panel._sp_move[i].setValue(float(v))
                    panel._sp_move[i].blockSignals(False)
                if hasattr(panel, '_apply_edit'):
                    panel._apply_edit()
                # Surface position feedback (if main window status bar exists)
                try:
                    mw = panel.window()
                    if hasattr(mw, 'statusBar') and mw.statusBar():
                        mw.statusBar().showMessage(f"Moved prim {getattr(panel,'_current_sel',-1)} to ("+
                            ", ".join(f"{panel._sp_move[i].value():.3f}" for i in range(3))+")", 1500)
                except Exception:
                    pass
        except Exception:
            pass

    def _perform_pick(self, x:int, y:int):
        if not self.prog or self._picking_fbo is None:
            return
        try:
            # Ensure GL context is current for FBO operations outside paintGL
            try:
                self.makeCurrent()
            except Exception:
                pass
            dpr = self.devicePixelRatio() if hasattr(self, 'devicePixelRatio') else 1
            sx = int(x * dpr); sy = int(y * dpr)
            glBindFramebuffer(GL_FRAMEBUFFER, self._picking_fbo)
            glViewport(0,0,self.width(), self.height())
            glClearColor(0,0,0,0); glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
            glUseProgram(self.prog)
            # draw IDs
            glUniform3f(glGetUniformLocation(self.prog,"u_cam_pos"), *self.cam_pos)
            R = self._cam_basis(); glUniformMatrix3fv(glGetUniformLocation(self.prog,"u_cam_rot"), 1, GL_FALSE, R.T)
            glUniform2f(glGetUniformLocation(self.prog,"u_res"), float(self.width()), float(self.height()))
            glUniform3f(glGetUniformLocation(self.prog,"u_env"), *self.scene.env_light)
            glUniform3f(glGetUniformLocation(self.prog,"u_bg"), 0,0,0)
            pack = self.scene.to_gpu_structs(max_prims=MAX_PRIMS)
            n = int(pack['count'])
            glUniform1i(glGetUniformLocation(self.prog,"u_count"), n)
            def U(name): return glGetUniformLocation(self.prog, name)
            glUniform1iv(U("u_kind"), n, pack['kind'])
            glUniform1iv(U("u_op"),   n, pack['op'])
            glUniform1fv(U("u_beta"), n, pack['beta'])
            glUniform3fv(U("u_color"), n, pack['color'])
            glUniform4fv(U("u_params"), n, pack['params'])
            glUniformMatrix4fv(U("u_xform"), n, GL_FALSE, pack['xform'])
            if 'xform_inv' in pack:
                glUniformMatrix4fv(U("u_xform_inv"), n, GL_FALSE, pack['xform_inv'])
            glUniform1i(glGetUniformLocation(self.prog, "u_mode"), 0)
            glUniform1i(glGetUniformLocation(self.prog, "u_debug"), 2)  # ID mode
            glUniform1i(glGetUniformLocation(self.prog, "u_use_analytic_aa"), 0)
            glUniform1i(glGetUniformLocation(self.prog, "u_use_toon"), 0)
            glUniform1f(glGetUniformLocation(self.prog, "u_toon_levels"), 1.0)
            glUniform1f(glGetUniformLocation(self.prog, "u_curv_strength"), 0.0)
            glUniform1i(glGetUniformLocation(self.prog, "u_use_foveated"), 0)
            glUniform1i(glGetUniformLocation(self.prog, "u_show_beta_overlay"), 0)
            glUniform1f(glGetUniformLocation(self.prog, "u_beta_overlay_intensity"), 0.0)
            glUniform1f(glGetUniformLocation(self.prog, "u_beta_scale"), 1.0)
            glUniform1i(glGetUniformLocation(self.prog, "u_beta_cmap"), 0)
            glUniform1i(glGetUniformLocation(self.prog, "u_selected"), -1)
            glBindVertexArray(self._vao); glDrawArrays(GL_TRIANGLE_STRIP, 0, 4)
            px = np.zeros((1,1,4), dtype=np.uint8)
            ry = self.height() - 1 - (sy if dpr!=1 else y)
            glReadPixels(sx if dpr!=1 else x, ry, 1,1, GL_RGBA, GL_UNSIGNED_BYTE, px)
            enc = int(px[0,0,0]) | (int(px[0,0,1])<<8) | (int(px[0,0,2])<<16)
            if enc==0:
                self.selected_index = -1
            else:
                self.selected_index = enc-1
            glBindFramebuffer(GL_FRAMEBUFFER,0)
            self.update()
            log.debug(f"pick raw={px[0,0].tolist()} enc={enc} sel={self.selected_index} at ({x},{y}) dpr={dpr}")
        except Exception as e:
            log.debug(f"pick failed (full-res) falling back to micro pick: {e}")
            try:
                pid = self._pick_id_at(x,y)
                self.selected_index = pid
            except Exception:
                pass

    def _pick_id_at(self, x:int, y:int) -> int:
        if not self.prog or self._pick_fbo is None:
            return -1
        try:
            # simplistic: render full scene in ID mode into 1x1 buffer (center ray)
            glBindFramebuffer(GL_FRAMEBUFFER, self._pick_fbo)
            glViewport(0,0,1,1)
            glClearColor(0,0,0,1)
            glClear(GL_COLOR_BUFFER_BIT)
            self._render_scene_internal(debug_override=2)
            data = glReadPixels(0,0,1,1,GL_RGBA,GL_UNSIGNED_BYTE)
            import numpy as _np
            px = _np.frombuffer(data, dtype=_np.uint8)
            enc = int(px[0])
            pid = enc-1
            glBindFramebuffer(GL_FRAMEBUFFER,0)
            return pid if 0 <= pid < len(self.scene.prims) else -1
        except Exception as e:
            log.debug(f"micro pick failed: {e}")
            try: glBindFramebuffer(GL_FRAMEBUFFER,0)
            except Exception: pass
            return -1

    def wheelEvent(self, event: QWheelEvent):
        delta = event.angleDelta().y() / 120.0  # 1 per notch
        zoom_factor = 1.0 - delta * 0.1
        zoom_factor = max(0.1, min(2.0, zoom_factor))
        self.distance *= zoom_factor
        self.distance = float(np.clip(self.distance, 0.5, 1000.0))
        self._update_camera()
        super().wheelEvent(event)

    def _update_title(self):
        try:
            mode_names = ['beauty','normals','id','depth','thickness']
            m = mode_names[self.debug_mode] if 0<=self.debug_mode < len(mode_names) else str(self.debug_mode)
            cmap_names = ['legacy','viridis','plasma','diverge']
            cm = cmap_names[self.beta_cmap]
            self.window().setWindowTitle(
                f"Analytic Viewport - {m} | AA={'on' if self.use_analytic_aa else 'off'} Toon={'on' if self.use_toon else 'off'} Lvl={int(self.toon_levels)} Curv={self.curv_strength:.1f} FovStep={'on' if self.use_foveated else 'off'} Î²={'on' if self.show_beta_overlay else 'off'} Î²I={self.beta_overlay_intensity:.2f} Î²S={self.beta_scale:.2f} {cm}"
            )
        except Exception:
            pass

    def _shortcuts_help(self):
        return (
            "Shortcuts:\n"
            "0..4 : debug modes (beauty,normals,id,depth,thickness)\n"
            "Space : cycle debug mode\n"
            "A : toggle analytic AA\n"
            "F : toggle foveated steps\n"
            "T : toggle toon\n"
            "+ / - : toon levels up/down\n"
            "C : cycle curvature strength (0,0.5,1.0,0)\n"
            "G : save G-buffers (beauty + normals/id/depth/thickness)\n"
            "Click : select primitive (highlight)\n"
            "H : print this help"
        )

    def save_gbuffers(self):
        # Ensure context current
        self.makeCurrent()
        out_dir = os.path.join(os.getcwd(), 'gbuffers')
        os.makedirs(out_dir, exist_ok=True)
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        targets = [(-1,'beauty'), (1,'normals'), (2,'id'), (3,'depth'), (4,'thickness')]
        w,h = self.width(), self.height()
        prev_mode = self.debug_mode
        # Render beauty first (override debug to 0 by setting debug_override=None with debug_mode=0)
        for mode,label in targets:
            if mode==-1:
                # beauty
                self.debug_mode=0
                self._draw_frame(debug_override=0)
            else:
                self._draw_frame(debug_override=mode)
            glFinish()
            data = glReadPixels(0,0,w,h, GL_RGBA, GL_UNSIGNED_BYTE)
            import numpy as _np
            img = _np.frombuffer(data, dtype=_np.uint8).reshape(h, w, 4)
            img = img[::-1,:,:]  # flip vertically
            path = os.path.join(out_dir, f"{timestamp}_{label}.png")
            if _HAVE_PIL:
                Image.fromarray(img, 'RGBA').save(path)
            else:
                # fallback raw dump
                img.tofile(path + '.raw')
            log.info(f"Saved {label} -> {path}")
        self.debug_mode = prev_mode
        self.update()


class AnalyticViewportPanel(QWidget):
    """Composite widget: analytic SDF viewport + control panel."""

    class _AIPromptWorker(QThread):
        finished_text = Signal(str)

        def __init__(
            self,
            text: str,
            *,
            tools: list[str],
            bus: "CADActionBus | None",
            model: str,
            prior: list[dict[str, str]] | None = None,
            registry: "ToolRegistry | None" = None,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self._text = text
            self._tools = tools
            self._bus = bus
            self._model = model
            self._prior = prior[:] if prior else []
            self._registry = registry

        def run(self) -> None:
            if not (_HAVE_AI and chat_with_tools is not None and hasattr(self._bus, "call")):
                self.finished_text.emit("AI copilot unavailable.")
                return
            try:
                output = chat_with_tools(
                    self._text,
                    available_tools=self._tools,
                    bus=self._bus,
                    model=self._model,
                    prior_messages=self._prior,
                    registry=self._registry,
                )
            except Exception as exc:  # pragma: no cover - network/runtime errors
                output = f"LLM error: {exc}"
            self.finished_text.emit(output)

    class _MandelbulbExportWorker(QThread):
        progress = Signal(str)
        finished = Signal(bool, str, str, str)

        def __init__(
            self,
            *,
            resolution: int,
            extent: float,
            power: float,
            bailout: float,
            max_iter: int,
            color_mode_index: int,
            pi_mode: str,
            pi_base: float,
            pi_alpha: float,
            pi_mu: float,
            norm_mode: str,
            norm_k: float,
            norm_r0: float,
            norm_sigma: float,
            step_scale: float,
            use_gpu_colors: bool,
            outfile: str,
            transform: np.ndarray | None,
            scale: float,
            orbit_shell: float,
            ni_scale: float,
            use_gpu: bool,
            compute_colors: bool,
            parent: QWidget | None = None,
        ) -> None:
            super().__init__(parent)
            self._resolution = int(max(8, resolution))
            self._extent = float(max(0.1, extent))
            self._power = float(max(2.0, power))
            self._bailout = float(max(1.0, bailout))
            self._max_iter = int(max(4, max_iter))
            self._color_mode_index = int(max(0, min(2, color_mode_index)))
            self._pi_mode = pi_mode if pi_mode in ("fixed", "adaptive") else "fixed"
            self._pi_base = float(pi_base)
            self._pi_alpha = float(max(0.0, pi_alpha))
            self._pi_mu = float(max(0.0, pi_mu))
            self._norm_mode = norm_mode if norm_mode in ("euclid", "adaptive") else "euclid"
            self._norm_k = float(max(0.0, norm_k))
            self._norm_r0 = float(max(0.1, norm_r0))
            self._norm_sigma = float(max(0.01, norm_sigma))
            self._step_scale = float(max(0.1, step_scale))
            self._use_gpu_colors = bool(use_gpu_colors)
            self._outfile = outfile
            self._transform = transform.copy() if transform is not None else None
            self._scale = float(scale if scale != 0.0 else 1.0)
            self._orbit_shell = float(max(0.0, orbit_shell))
            self._ni_scale = float(max(0.001, ni_scale))
            self._use_gpu = bool(use_gpu)
            self._compute_colors = bool(compute_colors)

        def run(self) -> None:  # pragma: no cover - long-running worker
            try:
                from mandelbulb_make import field_sample
                from skimage.measure import marching_cubes
                from adaptivecad.aacore.sdf import mandelbulb_color_cpu
                import numpy as _np

                bounds = (
                    -self._extent,
                    self._extent,
                    -self._extent,
                    self._extent,
                    -self._extent,
                    self._extent,
                )

                requested_gpu = self._use_gpu
                mode = "GPU" if requested_gpu else "CPU"
                self.progress.emit(
                    f"Sampling field @ res={self._resolution} in bounds={bounds} [{mode}]"
                )
                sample_start = time.perf_counter()
                used_gpu = requested_gpu
                try:
                    field, axes = field_sample(
                        bounds,
                        self._resolution,
                        self._power,
                        self._bailout,
                        self._max_iter,
                        self._pi_mode,
                        self._pi_base,
                        self._pi_alpha,
                        self._pi_mu,
                        use_gpu=self._use_gpu,
                    )
                except Exception as exc:
                    if self._use_gpu:
                        self.progress.emit("GPU sampling failed; falling back to CPU."
                                            " (see console for details)")
                        used_gpu = False
                        field, axes = field_sample(
                            bounds,
                            self._resolution,
                            self._power,
                            self._bailout,
                            self._max_iter,
                            self._pi_mode,
                            self._pi_base,
                            self._pi_alpha,
                            self._pi_mu,
                            use_gpu=False,
                        )
                    else:
                        raise

                xs, ys, zs = axes
                sample_elapsed = time.perf_counter() - sample_start
                if used_gpu:
                    detail = ""
                    try:
                        import cupy as _cp  # type: ignore

                        dev_id = _cp.cuda.runtime.getDevice()
                        props = _cp.cuda.runtime.getDeviceProperties(dev_id)
                        name = props.get("name", b"")
                        if isinstance(name, bytes):
                            name = name.decode("utf-8", "ignore")
                        mem_free, mem_total = _cp.cuda.runtime.memGetInfo()
                        detail = (
                            f" on {name.strip()} (free {mem_free / 1e9:.1f}/"
                            f"{mem_total / 1e9:.1f} GB)"
                        )
                    except Exception:
                        detail = ""
                    self.progress.emit(
                        f"Field sampling (GPU) finished in {sample_elapsed:.1f}s{detail}."
                    )
                else:
                    self.progress.emit(
                        f"Field sampling (CPU) finished in {sample_elapsed:.1f}s."
                    )

                self.progress.emit("Building mesh from field…")
                mesh_start = time.perf_counter()
                
                # Try using the new build_mesh function with adaptive parameters
                try:
                    from mandelbulb_make import build_mesh
                    color_mode_str = ["ni", "orbit", "angle"][self._color_mode_index]
                    verts_world, faces, colors = build_mesh(
                        field, 
                        (xs, ys, zs), 
                        color_mode_str, 
                        self._power, 
                        self._bailout, 
                        self._max_iter,
                        self._pi_mode, 
                        self._pi_base, 
                        self._pi_alpha, 
                        self._pi_mu,
                        norm_mode=self._norm_mode,
                        norm_k=self._norm_k,
                        norm_r0=self._norm_r0,
                        norm_sigma=self._norm_sigma,
                        orbit_shell=self._orbit_shell,
                        use_gpu_colors=self._use_gpu_colors and self._use_gpu
                    )
                    mesh_elapsed = time.perf_counter() - mesh_start
                    
                    # Apply scale and transform
                    scale = self._scale if abs(self._scale) > 1e-9 else 1.0
                    if abs(scale - 1.0) > 1e-9:
                        verts_world = verts_world / scale
                        
                    if self._transform is not None:
                        verts_h = _np.concatenate(
                            [verts_world, _np.ones((verts_world.shape[0], 1), dtype=_np.float64)],
                            axis=1,
                        )
                        verts_world = (verts_h @ self._transform.T)[:, :3]
                    
                    if self._compute_colors and colors is not None:
                        colors = (_np.clip(colors, 0.0, 1.0) * 255.0).astype(_np.uint8)
                    else:
                        colors = _np.full((len(verts_world), 3), 255, dtype=_np.uint8)
                        
                    gpu_status = " (GPU colors)" if (self._use_gpu_colors and self._use_gpu) else ""
                    self.progress.emit(f"Mesh built in {mesh_elapsed:.1f}s{gpu_status}")
                    
                except Exception as e:
                    # Fallback to original marching cubes approach
                    self.progress.emit(f"build_mesh failed ({e}), using fallback...")
                    
                    vol = _np.transpose(field, (2, 1, 0))
                    dx = (xs[-1] - xs[0]) / (len(xs) - 1) if len(xs) > 1 else 1.0
                    dy = (ys[-1] - ys[0]) / (len(ys) - 1) if len(ys) > 1 else 1.0
                    dz = (zs[-1] - zs[0]) / (len(zs) - 1) if len(zs) > 1 else 1.0

                    self.progress.emit("Running marching cubes …")
                    verts, faces, _norms, _ = marching_cubes(
                        vol, level=0.0, spacing=(dz, dy, dx)
                    )

                    verts_local = _np.zeros((verts.shape[0], 3), dtype=_np.float64)
                    verts_local[:, 0] = xs[0] + verts[:, 2]
                    verts_local[:, 1] = ys[0] + verts[:, 1]
                    verts_local[:, 2] = zs[0] + verts[:, 0]

                    scale = self._scale if abs(self._scale) > 1e-9 else 1.0

                    if self._compute_colors:
                        if used_gpu:
                            self.progress.emit(
                                "Vertex color baking runs on CPU; disable 'Bake Vertex Colors'"
                                " to skip this step."
                            )
                        self.progress.emit("Colorizing vertices …")
                        colors = _np.zeros((verts_local.shape[0], 3), dtype=_np.uint8)
                        for i, v in enumerate(verts_local):
                            if i % 2000 == 0:
                                self.progress.emit(
                                    f"Colorizing vertices … ({i}/{len(verts_local)})"
                                )
                            col = mandelbulb_color_cpu(
                                v * scale,
                                self._power,
                                self._bailout,
                                self._max_iter,
                                self._color_mode_index,
                                self._ni_scale,
                                self._orbit_shell,
                            )
                            colors[i] = (_np.clip(col, 0.0, 1.0) * 255.0).astype(_np.uint8)
                    else:
                        colors = _np.full((verts_local.shape[0], 3), 255, dtype=_np.uint8)

                    if abs(scale - 1.0) > 1e-9:
                        verts_local = verts_local / scale

                    if self._transform is not None:
                        verts_h = _np.concatenate(
                            [verts_local, _np.ones((verts_local.shape[0], 1), dtype=_np.float64)],
                            axis=1,
                        )
                        verts_world = (verts_h @ self._transform.T)[:, :3]
                    else:
                        verts_world = verts_local

                self.progress.emit("Saving meshes …")
                import trimesh as _trimesh

                mesh = _trimesh.Trimesh(
                    vertices=verts_world.astype(_np.float32),
                    faces=faces.astype(_np.int64),
                    process=False,
                )

                stl_path = f"{self._outfile}.stl"
                mesh.export(stl_path)

                mesh_vc = mesh.copy()
                alpha = _np.full(len(colors), 255, dtype=_np.uint8)
                mesh_vc.visual.vertex_colors = _np.column_stack((colors, alpha))
                ply_path = f"{self._outfile}_color.ply"
                mesh_vc.export(ply_path)

                self.finished.emit(True, stl_path, ply_path, "")
            except Exception as exc:  # pragma: no cover - runtime failure path
                import traceback

                self.finished.emit(False, "", "", traceback.format_exc())

    def __init__(self, parent=None, aacore_scene: AACoreScene | None = None, *, ui_layout: str = "panel"):
        super().__init__(parent)
        self._ui_layout = str(ui_layout or "panel").strip().lower()
        # Radial wheel defaults (updated before controls are created)
        self._wheel_enabled: bool = True
        self._wheel_edge_fit: bool = True
        self._wheel_edge_overshoot: int = 14
        self._wheel_thickness: float = 0.10
        self._wheel_opacity: float = 1.0
        self._wheel_text_scale: float = 1.0
        self._wheel_auto_spin: bool = False
        self._wheel_auto_spin_speed: float = 0.0
        self._radial_wheel = None
        self._cb_wheel_enabled = None
        self._cb_wheel_edge_fit = None
        self._spin_wheel_overshoot = None
        self._slider_wheel_thickness = None
        self._label_wheel_thickness = None
        self._slider_wheel_opacity = None
        self._label_wheel_opacity = None
        self._slider_wheel_text = None
        self._label_wheel_text = None
        self._cb_wheel_autospin = None
        self._slider_wheel_spin = None
        self._label_wheel_spin = None
        self._radial_wheel_base_tools: list["ToolSpec"] = []

        # AI copilot state (initialized before building UI)
        self._ai_model = os.getenv("ADCAD_OPENAI_MODEL", "gpt-4o-mini")
        self._ai_available_tools = [
            "select_tool",
            "create_line",
            "create_circle",
            "create_pi_circle",
            "upgrade_profile_to_pi_a",
            "extrude",
        ]
        self._ai_bus: "CADActionBus | None" = None
        self._ai_history: list[dict[str, str]] = []
        self._ai_worker = None
        self._ai_last_profile_meta = None
        self._ai_pending_circle = None
        self._tool_registry: "ToolRegistry | None" = None

        # AI UI references (populated in _populate_side_panel_controls)
        self._ai_group = None
        self._ai_transcript = None
        self._ai_input = None
        self._ai_send_btn = None
        self._ai_model_label = None
        self._ai_tools_group = None
        self._ai_tools_list = None
        self._ai_tools_run_btn = None
        self._ai_tools_delete_btn = None
        self._ai_tools_pin_chk = None

        self._scale_rig_ref = None
        self._scale_pixels = None
        self._scale_duration = None
        self._scale_fov = None
        self._scale_status = None

        # Fractal coloring controls
        self._fractal_mode_box: QComboBox | None = None
        self._fractal_shell_spin: QDoubleSpinBox | None = None
        self._fractal_ni_spin: QDoubleSpinBox | None = None

        # Mandelbulb export controls / workers
        self._mandelbulb_worker: "AnalyticViewportPanel._MandelbulbExportWorker | None" = None
        self._mb_progress_dialog: QProgressDialog | None = None
        self._mb_res_spin: QSpinBox | None = None
        self._mb_extent_spin: QDoubleSpinBox | None = None
        self._mb_power_spin: QDoubleSpinBox | None = None
        self._mb_bailout_spin: QDoubleSpinBox | None = None
        self._mb_iter_spin: QSpinBox | None = None
        self._mb_scale_spin: QDoubleSpinBox | None = None
        self._mb_color_box: QComboBox | None = None
        self._mb_pi_mode_box: QComboBox | None = None
        self._mb_pi_base_spin: QDoubleSpinBox | None = None
        self._mb_pi_alpha_spin: QDoubleSpinBox | None = None
        self._mb_pi_mu_spin: QDoubleSpinBox | None = None
        self._mb_export_btn: QPushButton | None = None
        self._mb_pull_btn: QPushButton | None = None
        self._mb_status_label: QLabel | None = None
        self._mb_use_gpu_chk: QCheckBox | None = None
        self._mb_reload_btn: QPushButton | None = None
        self._mb_clear_overlay_btn: QPushButton | None = None
        self._mb_last_export: tuple[str, str] | None = None
        self._mb_overlay_loaded: bool = False
        self._mb_colors_chk: QCheckBox | None = None

        # Field overlay (AMA/NDField) state for viewer-side threshold clipping
        self._field_overlay_source_mesh = None
        self._field_overlay_source_path: str | None = None
        self._field_layer_box: QComboBox | None = None
        self._field_layer_populating: bool = False
        self._field_layers: dict[str, dict[str, object]] = {}
        self._field_ama_path: str | None = None
        self._field_ama_scene: dict | None = None
        self._field_ama_scale_xy: float | None = None
        self._field_ama_scale_z: float | None = None
        self._field_current_colormap: str | None = None
        self._field_contour_chk: QCheckBox | None = None
        self._field_contour_bands: QSpinBox | None = None
        self._field_contour_width: QDoubleSpinBox | None = None
        self._field_clip_chk: QCheckBox | None = None
        self._field_clip_spin: QDoubleSpinBox | None = None

        # Dashboard (docked layout) widgets
        self._dock_left_scroll: QScrollArea | None = None
        self._dock_right_scroll: QScrollArea | None = None
        self._dock_bottom_widget: QWidget | None = None
        self._dashboard_console: QPlainTextEdit | None = None
        self._dashboard_metrics: QTableWidget | None = None

        self.view = AnalyticViewport(self, aacore_scene=aacore_scene)
        # --- Sketch layer state (overlay) ---
        self._sketch_on: bool = False
        self._sketch_mode: str | None = None  # 'polyline' or None
        self._sketch = SketchLayer()
        self._sketch_lock_top: bool = True
        # Gizmo / transform state
        self._gizmo_mode = 'move'   # 'move' | 'rotate' | 'scale'
        self._axis_lock = None      # 'x' | 'y' | 'z' | None
        self._space_local = True    # True local, False world
        self._snap_angle_deg = 5.0
        self._snap_scale_step = 0.1
        self._move_drag_free: bool = False  # require modifier unless explicitly toggled
        # References to select UI controls we want to drive programmatically
        self._cb_sketch = None
        self._btn_showcase = None
        self._btn_clear_scene = None
        self._btn_sketch_poly = None
        self._btn_sketch_line = None
        self._btn_sketch_arc3 = None
        self._btn_sketch_circle = None
        self._btn_sketch_rect = None
        self._btn_sketch_insert = None
        self._btn_sketch_dim = None
        self._chk_sketch_midpoint = None
        self._build_ui()
        self.setWindowTitle("Analytic Viewport" if self._ui_layout == "docked" else "Analytic Viewport (Panel)")
        self.view.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # Ensure the analytic panel is visible on at least one screen.
        # Run after a short delay so top-level windows have a chance to map.
        try:
            QTimer.singleShot(150, self._ensure_on_screen)
        except Exception:
            pass

        # --- Radial Tool Wheel (overlay) ---
        if _HAVE_WHEEL:
            try:
                tools = [
                    ToolSpec("File", children=[
                        ToolSpec("New", "file_new"),
                        ToolSpec("Open...", "file_open"),
                        ToolSpec("Save", "file_save"),
                        ToolSpec("Clear Scene", "clear"),
                    ]),
                    ToolSpec("Sketch", children=[
                        ToolSpec("Polyline", "polyline"),
                        ToolSpec("Line", "line"),
                        ToolSpec("Arc 3pt", "arc3"),
                        ToolSpec("Circle", "circle"),
                        ToolSpec("Rectangle", "rect"),
                        ToolSpec("Insert Vertex", "insert_vertex"),
                        ToolSpec("Dimension", "dimension"),
                        ToolSpec("Undo Last", "delete_last"),
                    ]),
                    ToolSpec("Transform", children=[
                        ToolSpec("Move", "move"),
                        ToolSpec("Rotate", "rotate"),
                        ToolSpec("Scale", "scale"),
                        ToolSpec("Center", "center_selected"),
                    ]),
                    ToolSpec("View", children=[
                        ToolSpec("Reset View", "reset_camera"),
                        ToolSpec("Showcase", "showcase"),
                    ]),
                    ToolSpec("Primitives", children=[
                        ToolSpec("Sphere", "prim:sphere"),
                        ToolSpec("Box", "prim:box"),
                        ToolSpec("Capsule", "prim:capsule"),
                        ToolSpec("Torus", "prim:torus"),
                        ToolSpec("Mobius", "prim:mobius"),
                        ToolSpec("Superellipsoid", "prim:superellipsoid"),
                        ToolSpec("Quasicrystal", "prim:quasicrystal"),
                        ToolSpec("Mandelbulb", "prim:mandelbulb"),
                    ]),
                    ToolSpec("Custom", children=[]),
                ]
                self._radial_wheel_base_tools = [spec.clone() for spec in tools]
                self._radial_wheel = RadialToolWheelOverlay(
                    self.view,
                    tools=tools,
                    outer_radius_ratio=0.46,  # used when fit_to_viewport_edge=False
                    thickness_ratio=0.10,
                    fade_full_at_center_ratio=0.06,
                    fade_full_at_edge_ratio=0.48,
                    idle_rotate_deg_per_sec=0.0,
                    # New: expand diameter so the outer edge sits just
                    # beyond the viewport and is nicely clipped by it.
                    fit_to_viewport_edge=True,
                    edge_overshoot_px=14,
                    min_visible_alpha=0.20,
                )
                self._radial_wheel.toolActivated.connect(self._on_wheel_tool)
                self._rebuild_wheel_tools()
                self._apply_wheel_settings()
                self._sync_wheel_controls()
            except Exception as e:
                try:
                    log.debug(f"radial wheel init failed: {e}")
                except Exception:
                    pass

        self._setup_ai()

    def _build_ui(self):
        docked = bool(getattr(self, "_ui_layout", "panel") == "docked")
        root = None
        if not docked:
            root = QHBoxLayout(self)
            root.setContentsMargins(4, 4, 4, 4)
            root.addWidget(self.view, 1)
        # Put the side controls into a dedicated widget so we can wrap
        # them with a QScrollArea to provide vertical scrolling when
        # the panel is taller than the available window height.
        if docked:
            left_widget = QWidget()
            left = QVBoxLayout(left_widget)
            left.setContentsMargins(0, 0, 0, 0)
            left.setSpacing(6)

            right_widget = QWidget()
            right = QVBoxLayout(right_widget)
            right.setContentsMargins(0, 0, 0, 0)
            right.setSpacing(6)
        else:
            side_widget = QWidget()
            side = QVBoxLayout(side_widget)
            side.setContentsMargins(0, 0, 0, 0)
            side.setSpacing(6)
            left = side
            right = side

        # Section toggles (visibility controls)
        if not hasattr(self, '_section_vis') or not isinstance(self._section_vis, dict):
            self._section_vis = {}
        self._section_groups = {}
        self._section_toggles = {}
        self._section_toggle_columns = 3
        toggle_box = QGroupBox("Sections")
        toggle_layout = QGridLayout()
        toggle_layout.setContentsMargins(6, 4, 6, 4)
        toggle_layout.setHorizontalSpacing(6)
        toggle_layout.setVerticalSpacing(4)
        toggle_box.setLayout(toggle_layout)
        self._section_toggle_layout = toggle_layout
        self._section_toggle_count = 0
        self._section_toggle_container = toggle_box
        left.addWidget(toggle_box)


        # --- Debug Modes ---
        gb_modes = QGroupBox("Debug / Modes"); fm = QFormLayout(); gb_modes.setLayout(fm)
        self.mode_box = QComboBox(); self.mode_box.addItems(["Beauty","Normals","ID","Depth","Thickness"])
        self.mode_box.currentIndexChanged.connect(self._on_mode); fm.addRow("Mode", self.mode_box)

        # Field overlay layer selector (AMA analytic payload)
        self._field_layer_box = QComboBox()
        self._field_layer_box.setEnabled(False)
        self._field_layer_box.currentIndexChanged.connect(self._on_field_layer_changed)
        fm.addRow("Field Layer", self._field_layer_box)

        # Field overlay iso-contours (topographic bands)
        self._field_contour_chk = QCheckBox("Field: Contour Bands")
        self._field_contour_chk.setChecked(False)
        self._field_contour_chk.stateChanged.connect(self._on_field_contour_changed)
        self._field_contour_bands = QSpinBox()
        self._field_contour_bands.setRange(2, 128)
        self._field_contour_bands.setValue(12)
        self._field_contour_bands.valueChanged.connect(self._on_field_contour_changed)
        self._field_contour_width = QDoubleSpinBox()
        self._field_contour_width.setRange(0.01, 0.50)
        self._field_contour_width.setDecimals(3)
        self._field_contour_width.setSingleStep(0.01)
        self._field_contour_width.setValue(0.12)
        self._field_contour_width.valueChanged.connect(self._on_field_contour_changed)
        fm.addRow(self._field_contour_chk)
        fm.addRow("Contour Bands", self._field_contour_bands)
        fm.addRow("Contour Width", self._field_contour_width)

        # Field overlay clip (iso-threshold style) for AMA-loaded NDField meshes
        self._field_clip_chk = QCheckBox("Field: Clip by Height")
        self._field_clip_chk.setChecked(False)
        self._field_clip_chk.stateChanged.connect(self._on_field_clip_changed)
        self._field_clip_spin = QDoubleSpinBox()
        self._field_clip_spin.setRange(0.0, 1.0)
        self._field_clip_spin.setDecimals(3)
        self._field_clip_spin.setSingleStep(0.02)
        self._field_clip_spin.setValue(0.50)
        self._field_clip_spin.setEnabled(False)
        self._field_clip_spin.valueChanged.connect(self._on_field_clip_changed)
        fm.addRow(self._field_clip_chk)
        fm.addRow("Field Threshold", self._field_clip_spin)

        right.addWidget(gb_modes)
        self._register_section("debug_modes", "Debug", gb_modes)

        # --- Compute / Export ---
        gb_tools = QGroupBox("Compute / Export")
        ft = QFormLayout()
        gb_tools.setLayout(ft)

        self._tool_use_api_chk = QCheckBox("Use API Server")
        try:
            self._tool_use_api_chk.setChecked(False)
        except Exception:
            pass

        self._tool_api_url = QLineEdit()
        try:
            default_api = os.environ.get("ADAPTIVECAD_API_URL", "http://localhost:8787")
            self._tool_api_url.setText(str(default_api))
        except Exception:
            pass

        self._tool_pr_size = QSpinBox(); self._tool_pr_size.setRange(8, 512); self._tool_pr_size.setValue(64)
        self._tool_pr_steps = QSpinBox(); self._tool_pr_steps.setRange(1, 20000); self._tool_pr_steps.setValue(200)
        self._tool_pr_dt = QDoubleSpinBox(); self._tool_pr_dt.setRange(0.001, 5.0); self._tool_pr_dt.setDecimals(4); self._tool_pr_dt.setValue(0.15)
        self._tool_pr_diff = QDoubleSpinBox(); self._tool_pr_diff.setRange(0.0, 10.0); self._tool_pr_diff.setDecimals(4); self._tool_pr_diff.setValue(0.35)
        self._tool_pr_coup = QDoubleSpinBox(); self._tool_pr_coup.setRange(0.0, 10.0); self._tool_pr_coup.setDecimals(4); self._tool_pr_coup.setValue(0.25)
        self._tool_pr_phase_dim = QSpinBox(); self._tool_pr_phase_dim.setRange(1, 8); self._tool_pr_phase_dim.setValue(2)
        self._tool_pr_phase_space = QComboBox(); self._tool_pr_phase_space.addItems(["unwrapped", "wrapped"])
        self._tool_pr_coupling_mode = QComboBox(); self._tool_pr_coupling_mode.addItems(["geom_target", "none"])

        # --- Geometry proxy tuning ("frequency" knobs) ---
        self._tool_pr_geom_mode = QComboBox(); self._tool_pr_geom_mode.addItems(["smooth_noise", "spectral_band"])
        self._tool_pr_geom_mode.currentIndexChanged.connect(self._on_tool_pr_geom_mode_changed)
        self._tool_pr_geom_smooth_iters = QSpinBox(); self._tool_pr_geom_smooth_iters.setRange(0, 100); self._tool_pr_geom_smooth_iters.setValue(6)
        self._tool_pr_geom_freq_low = QDoubleSpinBox(); self._tool_pr_geom_freq_low.setRange(0.0, 0.75); self._tool_pr_geom_freq_low.setDecimals(4); self._tool_pr_geom_freq_low.setSingleStep(0.005); self._tool_pr_geom_freq_low.setValue(0.02)
        self._tool_pr_geom_freq_high = QDoubleSpinBox(); self._tool_pr_geom_freq_high.setRange(0.0, 0.75); self._tool_pr_geom_freq_high.setDecimals(4); self._tool_pr_geom_freq_high.setSingleStep(0.005); self._tool_pr_geom_freq_high.setValue(0.12)
        self._tool_pr_geom_freq_power = QDoubleSpinBox(); self._tool_pr_geom_freq_power.setRange(0.01, 12.0); self._tool_pr_geom_freq_power.setDecimals(3); self._tool_pr_geom_freq_power.setSingleStep(0.1); self._tool_pr_geom_freq_power.setValue(1.0)

        self._tool_pr_seed = QSpinBox(); self._tool_pr_seed.setRange(-1_000_000, 1_000_000); self._tool_pr_seed.setValue(0)
        self._tool_pr_scale_xy = QDoubleSpinBox(); self._tool_pr_scale_xy.setRange(0.001, 100.0); self._tool_pr_scale_xy.setDecimals(4); self._tool_pr_scale_xy.setValue(1.0)
        self._tool_pr_scale_z = QDoubleSpinBox(); self._tool_pr_scale_z.setRange(0.001, 100.0); self._tool_pr_scale_z.setDecimals(4); self._tool_pr_scale_z.setValue(1.0)

        self._tool_run_pr_btn = QPushButton("Run PR → AMA (Load)")
        self._tool_run_pr_btn.clicked.connect(self._on_tool_run_pr)
        self._tool_run_blackholes_btn = QPushButton("Generate Blackholes AMA (Load)")
        self._tool_run_blackholes_btn.clicked.connect(self._on_tool_run_blackholes)
        self._tool_status_lbl = QLabel("")

        ft.addRow(self._tool_use_api_chk)
        ft.addRow("API URL", self._tool_api_url)
        ft.addRow("PR Size", self._tool_pr_size)
        ft.addRow("PR Steps", self._tool_pr_steps)
        ft.addRow("PR dt", self._tool_pr_dt)
        ft.addRow("Diffusion", self._tool_pr_diff)
        ft.addRow("Coupling", self._tool_pr_coup)
        ft.addRow("Phase Dim", self._tool_pr_phase_dim)
        ft.addRow("Phase Space", self._tool_pr_phase_space)
        ft.addRow("Coupling Mode", self._tool_pr_coupling_mode)
        ft.addRow("Geom Mode", self._tool_pr_geom_mode)
        ft.addRow("Geom Smooth Iters", self._tool_pr_geom_smooth_iters)
        ft.addRow("Freq Low", self._tool_pr_geom_freq_low)
        ft.addRow("Freq High", self._tool_pr_geom_freq_high)
        ft.addRow("Freq Power", self._tool_pr_geom_freq_power)
        ft.addRow("Seed", self._tool_pr_seed)
        ft.addRow("Scale XY", self._tool_pr_scale_xy)
        ft.addRow("Scale Z", self._tool_pr_scale_z)
        ft.addRow(self._tool_run_pr_btn)
        ft.addRow(self._tool_run_blackholes_btn)
        ft.addRow("Status", self._tool_status_lbl)

        try:
            self._on_tool_pr_geom_mode_changed()
        except Exception:
            pass

        left.addWidget(gb_tools)
        self._register_section("compute_export", "Compute", gb_tools)

        # --- Feature Toggles ---
        gb_feat = QGroupBox("Features"); vf = QVBoxLayout(); gb_feat.setLayout(vf)
        self.cb_aa = QCheckBox("Analytic AA"); self.cb_aa.setChecked(True); self.cb_aa.stateChanged.connect(self._on_toggle)
        self.cb_fov = QCheckBox("Foveated Steps"); self.cb_fov.setChecked(True); self.cb_fov.stateChanged.connect(self._on_toggle)
        self.cb_toon = QCheckBox("Toon"); self.cb_toon.setChecked(False); self.cb_toon.stateChanged.connect(self._on_toggle)
        for w in (self.cb_aa, self.cb_fov, self.cb_toon): vf.addWidget(w)
        right.addWidget(gb_feat)
        self._register_section("features", "Features", gb_feat)

        # --- Parameters ---
        gb_sliders = QGroupBox("Parameters"); fs = QFormLayout(); gb_sliders.setLayout(fs)
        self.slider_toon = QSlider(Qt.Orientation.Horizontal); self.slider_toon.setRange(1,8); self.slider_toon.setValue(4); self.slider_toon.valueChanged.connect(self._on_toon_levels)
        self.slider_curv = QSlider(Qt.Orientation.Horizontal); self.slider_curv.setRange(0,100); self.slider_curv.setValue(100); self.slider_curv.valueChanged.connect(self._on_curv)
        self.cb_beta = QCheckBox("Î² Overlay"); self.cb_beta.setChecked(False); self.cb_beta.stateChanged.connect(self._on_toggle)
        self.slider_beta_int = QSlider(Qt.Orientation.Horizontal); self.slider_beta_int.setRange(0,100); self.slider_beta_int.setValue(int(self.view.beta_overlay_intensity*100)); self.slider_beta_int.valueChanged.connect(self._on_beta_int)
        self.slider_beta_scale = QSlider(Qt.Orientation.Horizontal); self.slider_beta_scale.setRange(1,800); self.slider_beta_scale.setValue(int(self.view.beta_scale*100)); self.slider_beta_scale.valueChanged.connect(self._on_beta_scale)
        self.cmap_box = QComboBox(); self.cmap_box.addItems(["Legacy","Viridis","Plasma","Diverge"]); self.cmap_box.currentIndexChanged.connect(self._on_cmap)
        fs.addRow("Toon Levels", self.slider_toon)
        fs.addRow("Curvature", self.slider_curv)
        fs.addRow(self.cb_beta)
        fs.addRow("Î² Intensity", self.slider_beta_int)
        fs.addRow("Î² Scale", self.slider_beta_scale)
        fs.addRow("Î² Colormap", self.cmap_box)
        right.addWidget(gb_sliders)
        self._register_section("parameters", "Parameters", gb_sliders)

        if _HAVE_WHEEL:
            def _make_slider(min_v: int, max_v: int, value: int, formatter):
                row = QWidget()
                hl = QHBoxLayout(row)
                hl.setContentsMargins(0, 0, 0, 0)
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(min_v, max_v)
                slider.setValue(value)
                slider.setSingleStep(1)
                slider.setTracking(True)
                label = QLabel()
                label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                label.setFixedWidth(64)
                def _update_label(val: int) -> None:
                    try:
                        label.setText(formatter(val))
                    except Exception:
                        label.setText(str(val))
                _update_label(value)
                slider.valueChanged.connect(_update_label)
                hl.addWidget(slider, 1)
                hl.addWidget(label)
                return slider, label, row

            gb_wheel = QGroupBox("HUD Wheel")
            fw = QFormLayout()
            gb_wheel.setLayout(fw)

            self._cb_wheel_enabled = QCheckBox("Enabled")
            self._cb_wheel_enabled.setChecked(self._wheel_enabled)
            self._cb_wheel_enabled.toggled.connect(self._on_wheel_enabled)
            fw.addRow(self._cb_wheel_enabled)

            self._cb_wheel_edge_fit = QCheckBox("Fit To Edge")
            self._cb_wheel_edge_fit.setChecked(self._wheel_edge_fit)
            self._cb_wheel_edge_fit.toggled.connect(self._on_wheel_edge_fit)
            fw.addRow(self._cb_wheel_edge_fit)

            self._spin_wheel_overshoot = QSpinBox()
            self._spin_wheel_overshoot.setRange(0, 64)
            self._spin_wheel_overshoot.setValue(int(self._wheel_edge_overshoot))
            self._spin_wheel_overshoot.valueChanged.connect(self._on_wheel_overshoot)
            fw.addRow("Overshoot (px)", self._spin_wheel_overshoot)

            thickness_val = max(6, min(40, int(round(self._wheel_thickness * 100))))
            self._slider_wheel_thickness, self._label_wheel_thickness, row_thickness = _make_slider(6, 40, thickness_val, lambda v: f"{v}%")
            self._slider_wheel_thickness.valueChanged.connect(self._on_wheel_thickness)
            fw.addRow("Thickness (%)", row_thickness)

            opacity_val = max(0, min(100, int(round(self._wheel_opacity * 100))))
            self._slider_wheel_opacity, self._label_wheel_opacity, row_opacity = _make_slider(0, 100, opacity_val, lambda v: f"{v}%")
            self._slider_wheel_opacity.valueChanged.connect(self._on_wheel_opacity)
            fw.addRow("Opacity", row_opacity)

            text_val = max(60, min(200, int(round(self._wheel_text_scale * 100))))
            self._slider_wheel_text, self._label_wheel_text, row_text = _make_slider(60, 200, text_val, lambda v: f"{v/100:.2f}x")
            self._slider_wheel_text.valueChanged.connect(self._on_wheel_text_scale)
            fw.addRow("Text Size", row_text)

            self._cb_wheel_autospin = QCheckBox("Auto Spin")
            self._cb_wheel_autospin.setChecked(self._wheel_auto_spin)
            self._cb_wheel_autospin.toggled.connect(self._on_wheel_autospin)
            fw.addRow(self._cb_wheel_autospin)

            spin_val = max(0, min(360, int(round(self._wheel_auto_spin_speed))))
            self._slider_wheel_spin, self._label_wheel_spin, row_spin = _make_slider(0, 360, spin_val, lambda v: f"{v} deg/s")
            self._slider_wheel_spin.valueChanged.connect(self._on_wheel_spin_speed)
            fw.addRow("Spin Speed", row_spin)

            right.addWidget(gb_wheel)
            self._register_section("hud_wheel", "HUD Wheel", gb_wheel)
            self._sync_wheel_controls()

        # Additional sections are treated as "navigator/tools" by default.
        self._populate_side_panel_controls(left)
        if getattr(self, '_section_toggles', None):
            self._section_toggle_container.setVisible(True)
        else:
            self._section_toggle_container.setVisible(False)
        def _make_scroll(w: QWidget) -> QScrollArea:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            scroll.setWidget(w)
            try:
                content_w = int(w.sizeHint().width()) + 28
            except Exception:
                content_w = 480
            content_w = max(320, min(content_w, 860))
            scroll.setMinimumWidth(content_w)
            scroll.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            return scroll

        if docked:
            self._dock_left_scroll = _make_scroll(left_widget)
            self._dock_right_scroll = _make_scroll(right_widget)
            self._dock_bottom_widget = self._build_dashboard_bottom_panel()
        else:
            scroll = _make_scroll(side_widget)
            root.addWidget(scroll)
        self._refresh_prim_label()

    def _build_dashboard_bottom_panel(self) -> QWidget:
        tabs = QTabWidget()

        console = QPlainTextEdit()
        console.setReadOnly(True)
        try:
            console.setMaximumBlockCount(4000)
        except Exception:
            pass
        try:
            from PySide6.QtGui import QFont

            f = QFont("Consolas")
            f.setStyleHint(QFont.Monospace)
            console.setFont(f)
        except Exception:
            pass

        metrics = QTableWidget(0, 2)
        metrics.setHorizontalHeaderLabels(["Metric", "Value"])
        try:
            metrics.horizontalHeader().setStretchLastSection(True)
            metrics.verticalHeader().setVisible(False)
            metrics.setEditTriggers(QAbstractItemView.NoEditTriggers)
            metrics.setSelectionBehavior(QAbstractItemView.SelectRows)
            metrics.setShowGrid(False)
        except Exception:
            pass

        self._dashboard_console = console
        self._dashboard_metrics = metrics

        tabs.addTab(console, "Console")
        tabs.addTab(metrics, "Run Metrics")
        return tabs

    def _dashboard_log(self, msg: str) -> None:
        try:
            if self._dashboard_console is not None:
                self._dashboard_console.appendPlainText(str(msg))
        except Exception:
            pass

    def _dashboard_set_metrics(self, obj: object) -> None:
        if self._dashboard_metrics is None:
            return
        if not isinstance(obj, dict):
            return
        metrics = self._dashboard_metrics
        try:
            pairs = []
            # Prefer a compact set if available.
            for k in (
                "geom_mode",
                "geom_spectral_centroid",
                "phase_energy",
                "coupling_energy",
                "total_energy",
                "coherence",
                "falsifier_mean",
                "falsifier_max",
            ):
                if k in obj:
                    pairs.append((k, obj.get(k)))
            # Add a few extras if not present.
            if not pairs:
                for k, v in obj.items():
                    if isinstance(k, str):
                        pairs.append((k, v))
            metrics.setRowCount(0)
            for k, v in pairs[:80]:
                r = metrics.rowCount()
                metrics.insertRow(r)
                metrics.setItem(r, 0, QTableWidgetItem(str(k)))
                metrics.setItem(r, 1, QTableWidgetItem(str(v)))
        except Exception:
            pass

    def _on_field_clip_changed(self, *args) -> None:
        try:
            enabled = bool(self._field_clip_chk is not None and self._field_clip_chk.isChecked())
        except Exception:
            enabled = False
        if self._field_clip_spin is not None:
            try:
                self._field_clip_spin.setEnabled(enabled)
            except Exception:
                pass
        self._apply_field_overlay_clip()

    # --- Compute / Export tooling (local or API server) ---
    def _tool_set_status(self, msg: str) -> None:
        try:
            if getattr(self, "_tool_status_lbl", None) is not None:
                self._tool_status_lbl.setText(str(msg))
        except Exception:
            pass
        self._dashboard_log(msg)

    def _tool_read_ama_scene_scales(self, ama_path: str) -> tuple[dict | None, float | None, float | None]:
        try:
            import zipfile
            import json
        except Exception:
            return None, None, None

        scene_obj = None
        sx = None
        sz = None
        try:
            with zipfile.ZipFile(str(ama_path), "r") as z:
                if "analytic/scene.json" in z.namelist():
                    obj = json.loads(z.read("analytic/scene.json").decode("utf-8"))
                    if isinstance(obj, dict):
                        scene_obj = obj
                        scales = obj.get("scales")
                        if isinstance(scales, dict):
                            sx = scales.get("xy")
                            sz = scales.get("z")
        except Exception:
            return None, None, None

        try:
            sx = float(sx) if sx is not None else None
        except Exception:
            sx = None
        try:
            sz = float(sz) if sz is not None else None
        except Exception:
            sz = None
        return scene_obj, sx, sz

    def _tool_load_ama_into_viewer(self, ama_path: str, *, selected: str | None = None) -> None:
        # Populate layers and load the chosen layer (or scene.render.source_layer).
        scene_obj, sx, sz = self._tool_read_ama_scene_scales(ama_path)
        mesh_loaded = False
        try:
            mesh_loaded = self.set_field_layers_from_ama(str(ama_path), scene_obj, sx, sz, selected=selected)
        except Exception:
            pass

        # If a pre-built mesh was loaded, we're done - skip heightmap conversion.
        if mesh_loaded:
            return

        # Decide which key to load.
        key = None
        if isinstance(selected, str) and selected:
            key = selected
        else:
            try:
                render = scene_obj.get("render") if isinstance(scene_obj, dict) else None
                if isinstance(render, dict) and isinstance(render.get("source_layer"), str):
                    key = str(render.get("source_layer"))
            except Exception:
                key = None
        if key is None:
            # Fall back to first dropdown entry.
            try:
                if self._field_layer_box is not None and self._field_layer_box.count() > 0:
                    key = self._field_layer_box.itemData(0)
            except Exception:
                key = None
        if not isinstance(key, str) or not key:
            return

        try:
            self._load_field_layer_from_ama(key)
        except Exception:
            pass

    def _tool_run_pr_payload(self) -> dict:
        # Mirror apps-sdk schemas (roughly) but keep viewer-side simple.
        return {
            "size": int(self._tool_pr_size.value()),
            "steps": int(self._tool_pr_steps.value()),
            "dt": float(self._tool_pr_dt.value()),
            "diffusion": float(self._tool_pr_diff.value()),
            "coupling": float(self._tool_pr_coup.value()),
            "phase_dim": int(self._tool_pr_phase_dim.value()),
            "phase_space": str(self._tool_pr_phase_space.currentText()).strip(),
            "coupling_mode": str(self._tool_pr_coupling_mode.currentText()).strip(),
            "geom_mode": str(self._tool_pr_geom_mode.currentText()).strip(),
            "geom_smooth_iters": int(self._tool_pr_geom_smooth_iters.value()),
            "geom_freq_low": float(self._tool_pr_geom_freq_low.value()),
            "geom_freq_high": float(self._tool_pr_geom_freq_high.value()),
            "geom_freq_power": float(self._tool_pr_geom_freq_power.value()),
            "scale_xy": float(self._tool_pr_scale_xy.value()),
            "scale_z": float(self._tool_pr_scale_z.value()),
            "units": "mm",
            "defl": 0.05,
            "seed": int(self._tool_pr_seed.value()),
        }

    def _on_tool_pr_geom_mode_changed(self) -> None:
        mode = ""
        try:
            mode = str(self._tool_pr_geom_mode.currentText()).strip()
        except Exception:
            mode = ""
        is_spectral = (mode == "spectral_band")
        try:
            self._tool_pr_geom_smooth_iters.setEnabled(not is_spectral)
        except Exception:
            pass
        for w in (self._tool_pr_geom_freq_low, self._tool_pr_geom_freq_high, self._tool_pr_geom_freq_power):
            try:
                w.setEnabled(is_spectral)
            except Exception:
                pass

    def _on_tool_run_pr(self) -> None:
        # Run in a background thread; then load AMA in the UI thread.
        try:
            import threading
            import tempfile
            import base64
        except Exception:
            return

        payload = self._tool_run_pr_payload()
        use_api = False
        api_url = ""
        try:
            use_api = bool(self._tool_use_api_chk is not None and self._tool_use_api_chk.isChecked())
        except Exception:
            use_api = False
        try:
            api_url = str(self._tool_api_url.text()).strip() if self._tool_api_url is not None else ""
        except Exception:
            api_url = ""

        self._tool_set_status("Running PR → AMA…")

        def _worker() -> None:
            ama_bytes = None
            out_path = None
            err = None
            metrics_obj = None
            try:
                if use_api and api_url:
                    import json
                    import urllib.request

                    # Backwards-compat: keep server payload stable if it does not
                    # yet accept the advanced geometry tuning keys.
                    payload_api = dict(payload)
                    for k in ("geom_mode", "geom_smooth_iters", "geom_freq_low", "geom_freq_high", "geom_freq_power"):
                        payload_api.pop(k, None)

                    req = urllib.request.Request(
                        api_url.rstrip("/") + "/api/pr/export_ama",
                        data=json.dumps(payload_api).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        raw = resp.read().decode("utf-8")
                    obj = json.loads(raw)
                    if isinstance(obj, dict):
                        metrics_obj = obj
                    if isinstance(obj, dict) and isinstance(obj.get("saved_path"), str) and obj.get("saved_path"):
                        out_path = str(obj.get("saved_path"))
                    elif isinstance(obj, dict) and isinstance(obj.get("ama_data"), str):
                        ama_bytes = base64.b64decode(obj.get("ama_data"))
                else:
                    from adaptivecad.pr import PRFieldConfig, relax_phase_field, export_phase_field_as_ama

                    cfg = PRFieldConfig(
                        size=int(payload["size"]),
                        steps=int(payload["steps"]),
                        dt=float(payload["dt"]),
                        diffusion=float(payload["diffusion"]),
                        coupling=float(payload["coupling"]),
                        coupling_mode=str(payload["coupling_mode"]),
                        geom_mode=str(payload.get("geom_mode", "smooth_noise")),
                        geom_smooth_iters=int(payload.get("geom_smooth_iters", 6)),
                        geom_freq_low=float(payload.get("geom_freq_low", 0.02)),
                        geom_freq_high=float(payload.get("geom_freq_high", 0.12)),
                        geom_freq_power=float(payload.get("geom_freq_power", 1.0)),
                        phase_dim=int(payload["phase_dim"]),
                        phase_space=str(payload["phase_space"]),
                        seed=int(payload["seed"]),
                    )
                    _metrics, state = relax_phase_field(cfg)
                    metrics_obj = _metrics
                    ama_bytes = export_phase_field_as_ama(
                        state.phi,
                        falsifier_residual=state.falsifier_residual,
                        scale_xy=float(payload["scale_xy"]),
                        scale_z=float(payload["scale_z"]),
                        filename="viewer_pr.ama",
                        params={
                            "dt": float(payload["dt"]),
                            "diffusion": float(payload["diffusion"]),
                            "coupling": float(payload["coupling"]),
                            "coupling_mode": str(payload["coupling_mode"]),
                            "geom_mode": str(payload.get("geom_mode", "smooth_noise")),
                            "geom_smooth_iters": int(payload.get("geom_smooth_iters", 6)),
                            "geom_freq_low": float(payload.get("geom_freq_low", 0.02)),
                            "geom_freq_high": float(payload.get("geom_freq_high", 0.12)),
                            "geom_freq_power": float(payload.get("geom_freq_power", 1.0)),
                            "phase_dim": int(payload["phase_dim"]),
                            "phase_space": str(payload["phase_space"]),
                            "seed": int(payload["seed"]),
                        },
                        units="mm",
                        defl=0.05,
                    )

                if ama_bytes is None and out_path is None:
                    raise RuntimeError("Failed to produce AMA bytes")
                if ama_bytes is not None:
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ama")
                    tmp.write(ama_bytes)
                    tmp.flush()
                    out_path = tmp.name
                    tmp.close()
            except Exception as e:
                err = str(e)

            def _finish() -> None:
                if err:
                    self._tool_set_status(f"PR failed: {err}")
                    return
                if out_path:
                    self._tool_set_status("Loaded PR AMA")
                    try:
                        if metrics_obj is not None:
                            self._dashboard_set_metrics(metrics_obj)
                    except Exception:
                        pass
                    try:
                        self._tool_load_ama_into_viewer(out_path, selected=None)
                    except Exception:
                        pass

            try:
                QTimer.singleShot(0, _finish)
            except Exception:
                _finish()

        threading.Thread(target=_worker, daemon=True).start()

    def _on_tool_run_blackholes(self) -> None:
        try:
            import threading
            import tempfile
            import base64
        except Exception:
            return

        use_api = False
        api_url = ""
        try:
            use_api = bool(self._tool_use_api_chk is not None and self._tool_use_api_chk.isChecked())
        except Exception:
            use_api = False
        try:
            api_url = str(self._tool_api_url.text()).strip() if self._tool_api_url is not None else ""
        except Exception:
            api_url = ""

        # Reuse PR size + scales for the demo field.
        size = int(self._tool_pr_size.value())
        scale_xy = float(self._tool_pr_scale_xy.value())
        scale_z = float(self._tool_pr_scale_z.value())

        self._tool_set_status("Generating blackholes AMA…")

        def _worker() -> None:
            ama_bytes = None
            out_path = None
            err = None
            if use_api and api_url:
                try:
                    import json
                    import urllib.request

                    req = urllib.request.Request(
                        api_url.rstrip("/") + "/api/demo/blackholes",
                        data=json.dumps({"size": size, "scale_xy": scale_xy, "scale_z": scale_z}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=120) as resp:
                        raw = resp.read().decode("utf-8")
                    obj = json.loads(raw)
                    if isinstance(obj, dict) and isinstance(obj.get("ama_data"), str):
                        ama_bytes = base64.b64decode(obj.get("ama_data"))
                except Exception:
                    ama_bytes = None

            if ama_bytes is None:
                try:
                    # Local generation without server: use the same logic as generate_binary_blackholes_ama.py
                    import zipfile
                    import json
                    import numpy as np
                    import hashlib
                    from datetime import datetime, timezone

                    # Build field
                    xs = np.linspace(-1.0, 1.0, size, dtype=np.float32)
                    ys = np.linspace(-1.0, 1.0, size, dtype=np.float32)
                    X, Y = np.meshgrid(xs, ys, indexing="xy")
                    eps = 0.06
                    c1 = (-0.45, 0.00)
                    c2 = (0.45, 0.00)
                    r1 = np.sqrt((X - c1[0]) ** 2 + (Y - c1[1]) ** 2 + eps**2)
                    r2 = np.sqrt((X - c2[0]) ** 2 + (Y - c2[1]) ** 2 + eps**2)
                    pot = -1.0 / r1 - 1.0 / r2
                    bridge = np.exp(-(Y * 5.0) ** 2) * np.exp(-(X * 1.2) ** 2)
                    pot = pot - 0.35 * bridge
                    pot = pot.astype(np.float32)
                    pot = (pot - float(np.min(pot))) / max(1e-9, float(np.max(pot) - np.min(pot)))
                    field = (1.0 - pot).astype(np.float32)

                    scene = {
                        "format": "AdaptiveCAD.AnalyticScene",
                        "version": "0.1.0",
                        "kind": "ndfield_heightmap",
                        "scales": {"xy": float(scale_xy), "z": float(scale_z)},
                        "layers": [
                            {"id": "field", "label": "Binary Blackholes", "field_ref": "fields/f000_field.npy", "colormap": "plasma"}
                        ],
                        "render": {"mode": "iso", "iso": 0.55, "source_layer": "field"},
                        "units": "mm",
                    }

                    manifest = {
                        "format": "AdaptiveCAD.AnalyticManifest",
                        "version": "0.1.0",
                        "kind": "ndfield",
                        "fields": [{"id": "field", "path": "fields/f000_field.npy", "dtype": str(field.dtype), "shape": list(field.shape)}],
                    }

                    cosmo_meta = {
                        "ama_version": "0.1",
                        "model": {"name": "BinaryBlackholesDemo", "pr_root": {"pi_a": "adaptive", "invariants": ["2pi_a", "w", "b", "C"]}},
                        "run": {
                            "solver": "viewer.blackholes",
                            "solver_version": "0.1.0",
                            "git_commit": "unknown",
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "seed": None,
                            "platform": {"python": __import__("sys").version.split()[0]},
                        },
                        "numerics": {"grid": [int(field.shape[0]), int(field.shape[1])], "integrator": "procedural", "step_size": None},
                        "observables": {},
                        "tests": [],
                    }
                    cosmo_bytes = json.dumps(cosmo_meta, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
                    cosmo_header = {
                        "meta_format": "json",
                        "meta_path": "meta/cosmo_meta.json",
                        "meta_len": int(len(cosmo_bytes)),
                        "meta_sha256": hashlib.sha256(cosmo_bytes).hexdigest(),
                        "schema": "AdaptiveCAD.CosmoMeta",
                        "schema_version": "0.1.0",
                    }

                    import io
                    buf_zip = io.BytesIO()
                    with zipfile.ZipFile(buf_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
                        z.writestr("manifest.json", json.dumps({"version": "0.1.0", "parts": []}, indent=2))
                        z.writestr("analytic/scene.json", json.dumps(scene, indent=2))
                        z.writestr("analytic/manifest.json", json.dumps(manifest, indent=2))
                        z.writestr("meta/cosmo_meta.json", cosmo_bytes)
                        z.writestr("meta/cosmo_header.json", json.dumps(cosmo_header, indent=2))
                        z.writestr("meta/info.json", json.dumps({"generator": "viewer", "size": int(field.shape[0]), "cosmo_header": "meta/cosmo_header.json"}, indent=2))
                        bio = io.BytesIO(); np.save(bio, field); z.writestr("fields/f000_field.npy", bio.getvalue())
                    ama_bytes = buf_zip.getvalue()
                except Exception as e:
                    err = str(e)

            try:
                if ama_bytes is None:
                    raise RuntimeError("Failed to produce AMA bytes")
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ama")
                tmp.write(ama_bytes)
                tmp.flush()
                out_path = tmp.name
                tmp.close()
            except Exception as e:
                err = err or str(e)

            def _finish() -> None:
                if err:
                    self._tool_set_status(f"Blackholes failed: {err}")
                    return
                if out_path:
                    self._tool_set_status("Loaded blackholes AMA")
                    try:
                        self._tool_load_ama_into_viewer(out_path, selected=None)
                    except Exception:
                        pass

            try:
                QTimer.singleShot(0, _finish)
            except Exception:
                _finish()

        threading.Thread(target=_worker, daemon=True).start()

    def _on_field_contour_changed(self, *args) -> None:
        self._recolor_field_overlay_source()

    def _recolor_field_overlay_source(self) -> None:
        mesh = getattr(self, "_field_overlay_source_mesh", None)
        if mesh is None:
            return
        try:
            self._apply_vertex_colormap_to_mesh(mesh, self._field_current_colormap)
        except Exception:
            pass
        self._apply_field_overlay_clip()

    def _apply_field_overlay_clip(self) -> None:
        """Rebuild the current field mesh overlay using a height/iso threshold.

        This is intended for the AMA->NDField visualization path where the launcher
        provides the source mesh as `self._field_overlay_source_mesh`.
        """

        mesh = getattr(self, "_field_overlay_source_mesh", None)
        if mesh is None:
            return

        try:
            import numpy as _np
        except Exception:
            return

        # Normalize to a Trimesh instance if a Scene was provided.
        try:
            import trimesh as _trimesh  # type: ignore
            if isinstance(mesh, _trimesh.Scene):
                mesh = _trimesh.util.concatenate(tuple(mesh.dump()))
        except Exception:
            pass

        # If clip is disabled, show the original mesh as-is.
        try:
            clip_on = bool(self._field_clip_chk is not None and self._field_clip_chk.isChecked())
        except Exception:
            clip_on = False
        if not clip_on:
            try:
                self.view.add_mesh_overlay(mesh, source_path=self._field_overlay_source_path, replace_existing=True)
            except Exception:
                pass
            return

        # Compute threshold in world Z based on a 0..1 fraction of current Z range.
        try:
            frac = float(self._field_clip_spin.value()) if self._field_clip_spin is not None else 0.5
        except Exception:
            frac = 0.5
        frac = max(0.0, min(1.0, frac))

        try:
            verts = _np.asarray(mesh.vertices, dtype=_np.float32)
            faces = _np.asarray(mesh.faces, dtype=_np.int64)
            if verts.size == 0 or faces.size == 0:
                return
            z = verts[:, 2]
            zmin = float(_np.nanmin(z))
            zmax = float(_np.nanmax(z))
            if not _np.isfinite(zmin) or not _np.isfinite(zmax) or abs(zmax - zmin) < 1e-9:
                return
            zcut = zmin + frac * (zmax - zmin)
            face_z_mean = z[faces].mean(axis=1)
            mask = _np.asarray(face_z_mean >= zcut, dtype=bool)
            if mask.size != faces.shape[0]:
                return
        except Exception:
            return

        try:
            m2 = mesh.copy()
            # keep faces above threshold
            m2.update_faces(mask)
            m2.remove_unreferenced_vertices()
            self.view.add_mesh_overlay(m2, source_path=self._field_overlay_source_path, replace_existing=True)
        except Exception:
            pass

    def _try_load_ama_mesh(self, ama_path: str, scene_obj: dict | None) -> bool:
        """Load a pre-built mesh from the AMA if specified in scene.json.
        
        Returns True if a mesh was loaded, False otherwise.
        """
        import zipfile
        import tempfile
        
        mesh_ref = None
        if isinstance(scene_obj, dict):
            mesh_ref = scene_obj.get("mesh")
        if not isinstance(mesh_ref, str) or not mesh_ref:
            # Try common fallback paths
            mesh_ref = None
            try:
                with zipfile.ZipFile(ama_path, "r") as z:
                    for candidate in ["mesh/ribbon.stl", "mesh/surface.stl", "mesh/model.stl"]:
                        if candidate in z.namelist():
                            mesh_ref = candidate
                            break
            except Exception:
                pass
        
        if not mesh_ref:
            return False
        
        try:
            import trimesh
            with zipfile.ZipFile(ama_path, "r") as z:
                stl_bytes = z.read(mesh_ref)
            
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".stl")
            tmp.write(stl_bytes)
            tmp.flush()
            tmp_path = tmp.name
            tmp.close()
            
            mesh = trimesh.load_mesh(tmp_path)
            if isinstance(mesh, trimesh.Scene):
                mesh = trimesh.util.concatenate(tuple(mesh.dump()))
            
            # Apply default colormap based on scene layers
            cmap = None
            if isinstance(scene_obj, dict):
                layers = scene_obj.get("layers")
                if isinstance(layers, list) and layers:
                    cmap = layers[0].get("colormap") if isinstance(layers[0], dict) else None
            
            if cmap:
                self._apply_vertex_colormap_to_mesh(mesh, cmap)
            
            self._field_overlay_source_mesh = mesh
            self._field_overlay_source_path = tmp_path
            self._apply_field_overlay_clip()
            return True
        except Exception as e:
            self._tool_set_status(f"Failed to load AMA mesh: {e}")
            return False

    def set_field_layers_from_ama(
        self,
        ama_path: str,
        scene_obj: dict | None,
        scale_xy: float | None,
        scale_z: float | None,
        *,
        selected: str | None = None,
    ) -> bool:
        """Populate the Field Layer dropdown from an AMA archive.

        Enables layer switching (e.g. `field` vs `gradmag`) without relaunch.
        Also loads a pre-built mesh (e.g. ribbon) if present in the archive.
        
        Returns True if a pre-built mesh was loaded (skip heightmap conversion).
        """

        self._field_ama_path = str(ama_path)
        self._field_ama_scene = scene_obj if isinstance(scene_obj, dict) else None
        self._field_current_colormap = None

        # --- Load pre-built mesh if specified in scene.json ---
        mesh_loaded = self._try_load_ama_mesh(ama_path, scene_obj)
        try:
            self._field_ama_scale_xy = float(scale_xy) if scale_xy is not None else None
        except Exception:
            self._field_ama_scale_xy = None
        try:
            self._field_ama_scale_z = float(scale_z) if scale_z is not None else None
        except Exception:
            self._field_ama_scale_z = None

        if self._field_layer_box is None:
            return

        import zipfile

        items: list[tuple[str, str]] = []
        layers: dict[str, dict[str, object]] = {}

        # Prefer analytic/scene.json layer definitions if present.
        if isinstance(self._field_ama_scene, dict):
            scene_layers = self._field_ama_scene.get("layers")
            if isinstance(scene_layers, list):
                for layer in scene_layers:
                    if not isinstance(layer, dict):
                        continue
                    lid = str(layer.get("id", "")).strip()
                    if not lid:
                        continue
                    field_ref = layer.get("field_ref")
                    if not isinstance(field_ref, str) or not field_ref.lower().endswith(".npy"):
                        continue
                    label = layer.get("label")
                    display = str(label).strip() if isinstance(label, str) and str(label).strip() else lid
                    layers[lid] = {
                        "kind": "layer_id",
                        "field_ref": field_ref,
                        "colormap": layer.get("colormap"),
                        "display": display,
                    }
                    items.append((display, lid))

        # Fallback: include raw fields/*.npy paths as selectable entries.
        try:
            with zipfile.ZipFile(self._field_ama_path, "r") as z:
                for name in sorted(z.namelist()):
                    n = str(name)
                    if not (n.lower().startswith("fields/") and n.lower().endswith(".npy")):
                        continue
                    key = n
                    if key in layers:
                        continue
                    display = n.replace("fields/", "")
                    layers[key] = {"kind": "field_path", "field_ref": n, "display": display}
                    items.append((display, key))
        except Exception:
            pass

        self._field_layer_populating = True
        try:
            self._field_layers = layers
            self._field_layer_box.blockSignals(True)
            self._field_layer_box.clear()
            for display, key in items:
                self._field_layer_box.addItem(display, key)
            self._field_layer_box.setEnabled(len(items) > 0)

            # Choose default selection.
            pick = None
            if isinstance(selected, str) and selected:
                pick = selected
            else:
                try:
                    render = self._field_ama_scene.get("render") if isinstance(self._field_ama_scene, dict) else None
                    if isinstance(render, dict) and isinstance(render.get("source_layer"), str):
                        pick = render.get("source_layer")
                except Exception:
                    pick = None

            if pick is not None:
                idx = self._field_layer_box.findData(pick)
                if idx >= 0:
                    self._field_layer_box.setCurrentIndex(idx)
        finally:
            try:
                self._field_layer_box.blockSignals(False)
            except Exception:
                pass
            self._field_layer_populating = False
        
        return mesh_loaded

    def _on_field_layer_changed(self, *args) -> None:
        if self._field_layer_populating:
            return
        if self._field_layer_box is None:
            return
        try:
            key = self._field_layer_box.currentData()
        except Exception:
            key = None
        if not isinstance(key, str) or not key:
            try:
                key = str(self._field_layer_box.currentText())
            except Exception:
                key = ""
        if not key:
            return
        self._load_field_layer_from_ama(key)

    def _apply_vertex_colormap_to_mesh(self, mesh, cmap: str | None) -> None:
        if mesh is None:
            return
        try:
            import numpy as _np
        except Exception:
            return

        cmap = (cmap or "plasma").strip().lower()
        try:
            z = _np.asarray(mesh.vertices, dtype=_np.float32)[:, 2]
            zmin = float(_np.nanmin(z))
            zmax = float(_np.nanmax(z))
            if not _np.isfinite(zmin) or not _np.isfinite(zmax) or abs(zmax - zmin) < 1e-9:
                return
            t = (z - zmin) / (zmax - zmin)
            t = _np.clip(t, 0.0, 1.0)
        except Exception:
            return

        # Contour settings (viewer-side)
        try:
            contour_on = bool(self._field_contour_chk is not None and self._field_contour_chk.isChecked())
        except Exception:
            contour_on = False
        try:
            bands = int(self._field_contour_bands.value()) if self._field_contour_bands is not None else 12
        except Exception:
            bands = 12
        bands = max(2, min(256, bands))
        try:
            width = float(self._field_contour_width.value()) if self._field_contour_width is not None else 0.12
        except Exception:
            width = 0.12
        width = max(0.01, min(0.5, width))

        def _lerp(a, b, tt):
            return a * (1.0 - tt) + b * tt

        def _colormap_rgb(tt: "_np.ndarray") -> "_np.ndarray":
            tt = _np.asarray(tt, dtype=_np.float32)
            tt = _np.clip(tt, 0.0, 1.0)
            if cmap == "viridis":
                c0 = _np.array([0.267, 0.005, 0.329], _np.float32)
                c1 = _np.array([0.283, 0.141, 0.458], _np.float32)
                c2 = _np.array([0.254, 0.265, 0.530], _np.float32)
                c3 = _np.array([0.207, 0.372, 0.553], _np.float32)
                c4 = _np.array([0.164, 0.471, 0.558], _np.float32)
                c5 = _np.array([0.128, 0.567, 0.551], _np.float32)
                c6 = _np.array([0.135, 0.659, 0.518], _np.float32)
                c7 = _np.array([0.267, 0.749, 0.441], _np.float32)
                c8 = _np.array([0.478, 0.821, 0.318], _np.float32)
                c9 = _np.array([0.741, 0.873, 0.150], _np.float32)
                c10 = _np.array([0.993, 0.906, 0.144], _np.float32)
                stops = _np.stack([c0,c1,c2,c3,c4,c5,c6,c7,c8,c9,c10], axis=0)
                nseg = stops.shape[0] - 1
                u = tt * nseg
                i = _np.clip(_np.floor(u).astype(_np.int32), 0, nseg - 1)
                f = (u - i).astype(_np.float32)
                return _lerp(stops[i], stops[i + 1], f[:, None])
            # plasma-ish (also used for diverge)
            c0 = _np.array([0.050, 0.030, 0.528], _np.float32)
            c1 = _np.array([0.465, 0.004, 0.659], _np.float32)
            c2 = _np.array([0.796, 0.277, 0.473], _np.float32)
            c3 = _np.array([0.940, 0.975, 0.131], _np.float32)
            rgb = _np.zeros((tt.shape[0], 3), _np.float32)
            m1 = tt < 0.33
            m2 = (tt >= 0.33) & (tt < 0.66)
            m3 = tt >= 0.66
            rgb[m1] = _lerp(c0, c1, (tt[m1] / 0.33)[:, None])
            rgb[m2] = _lerp(c1, c2, ((tt[m2] - 0.33) / 0.33)[:, None])
            rgb[m3] = _lerp(c2, c3, ((tt[m3] - 0.66) / 0.34)[:, None])
            return rgb

        if contour_on:
            # Filled bands + dark iso-lines at the band boundaries.
            u = t * float(bands)
            tq = _np.floor(u) / float(bands)
            tq = _np.clip(tq, 0.0, 1.0)
            rgb = _colormap_rgb(tq)

            # Distance to nearest band boundary in [0..0.5]
            frac = u - _np.floor(u)
            dist = _np.minimum(frac, 1.0 - frac)
            edge = 1.0 - _np.clip(dist / width, 0.0, 1.0)
            edge = edge * edge * (3.0 - 2.0 * edge)  # smoothstep
            rgb = rgb * (1.0 - 0.70 * edge[:, None])
        else:
            rgb = _colormap_rgb(t)

        rgba = (_np.clip(rgb, 0.0, 1.0) * 255.0).astype(_np.uint8)
        alpha = _np.full((rgba.shape[0], 1), 255, dtype=_np.uint8)
        try:
            mesh.visual.vertex_colors = _np.concatenate([rgba, alpha], axis=1)
        except Exception:
            pass

    def _load_field_layer_from_ama(self, key: str) -> None:
        if not isinstance(key, str) or not key:
            return
        if not isinstance(self._field_ama_path, str) or not self._field_ama_path:
            return

        layer = self._field_layers.get(key)
        field_ref = None
        cmap = None
        mesh_ref = None
        if isinstance(layer, dict):
            fr = layer.get("field_ref")
            if isinstance(fr, str) and fr:
                field_ref = fr
            if isinstance(layer.get("colormap"), str):
                cmap = layer.get("colormap")
            if isinstance(layer.get("mesh_ref"), str):
                mesh_ref = layer.get("mesh_ref")
        if field_ref is None:
            field_ref = key

        try:
            import numpy as np
            import trimesh  # type: ignore
            from io import BytesIO
            import tempfile
            import zipfile
        except Exception:
            return

        # --- Try to load a pre-rendered mesh first (e.g. from ribbon/sweep) ---
        mesh = None
        tmp_path = None
        try:
            with zipfile.ZipFile(self._field_ama_path, "r") as z:
                # Check for explicit mesh_ref, then scene.json mesh, then mesh/ribbon.stl fallback
                mesh_candidates = []
                if mesh_ref:
                    mesh_candidates.append(mesh_ref)
                try:
                    scene_raw = z.read("analytic/scene.json")
                    scene_obj = __import__("json").loads(scene_raw.decode("utf-8"))
                    if isinstance(scene_obj, dict) and isinstance(scene_obj.get("mesh"), str):
                        mesh_candidates.append(scene_obj["mesh"])
                except Exception:
                    pass
                mesh_candidates.extend(["mesh/ribbon.stl", "mesh/surface.stl", "mesh/model.stl"])
                
                for mc in mesh_candidates:
                    try:
                        stl_bytes = z.read(mc)
                        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".stl")
                        tmp.write(stl_bytes)
                        tmp.flush()
                        tmp_path = tmp.name
                        tmp.close()
                        mesh = trimesh.load_mesh(tmp_path)
                        break
                    except Exception:
                        continue
        except Exception:
            pass

        # --- Fallback: generate heightmap STL from field if mesh not found ---
        if mesh is None:
            try:
                with zipfile.ZipFile(self._field_ama_path, "r") as z:
                    raw = z.read(str(field_ref))
            except Exception as e:
                self._tool_set_status(f"Failed to read field: {e}")
                return

            try:
                phi = np.load(BytesIO(raw))
            except Exception as e:
                self._tool_set_status(f"Failed to load field: {e}")
                return

            # Only attempt heightmap conversion for square NxN fields
            if phi.ndim != 2 or phi.shape[0] != phi.shape[1]:
                self._tool_set_status(f"Field shape {phi.shape} is not square; skipping heightmap conversion")
                # Still try to display whatever mesh might be present
                return

            scale_xy = float(self._field_ama_scale_xy) if self._field_ama_scale_xy is not None else 1.0
            scale_z = float(self._field_ama_scale_z) if self._field_ama_scale_z is not None else 1.0

            try:
                from adaptivecad.pr.export import export_phase_field_as_heightmap_stl
            except Exception:
                return

            try:
                stl_bytes = export_phase_field_as_heightmap_stl(np.asarray(phi), scale_xy=float(scale_xy), scale_z=float(scale_z))
            except Exception as e:
                self._tool_set_status(f"Failed to convert field to STL: {e}")
                return

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".stl")
            tmp.write(stl_bytes)
            tmp.flush()
            tmp_path = tmp.name
            tmp.close()

            try:
                mesh = trimesh.load_mesh(tmp_path)
            except Exception:
                return

        if mesh is None:
            return

        try:
            if isinstance(mesh, trimesh.Scene):
                mesh = trimesh.util.concatenate(tuple(mesh.dump()))
        except Exception:
            pass

        try:
            self._apply_vertex_colormap_to_mesh(mesh, cmap)
        except Exception:
            pass

        try:
            self._field_current_colormap = str(cmap) if isinstance(cmap, str) and cmap else None
        except Exception:
            self._field_current_colormap = None

        try:
            self._field_overlay_source_mesh = mesh
            self._field_overlay_source_path = tmp_path
            self._apply_field_overlay_clip()
        except Exception:
            pass

    # --- Tesseract helpers ---
    def _add_tesseract(self):
        L = float(self._tess_edge.value())
        er = float(self._tess_edge_rad.value())
        nr = float(self._tess_node_rad.value())
        include_nodes = bool(self._tess_include_nodes.isChecked())
        proj = self._tess_proj.currentIndex()  # 0=ortho,1=persp
        fw = float(self._tess_fw.value())
        verts4 = self._tesseract_vertices4(L)
        edges = self._tesseract_edges()
        # Prim budget
        need = len(edges) + (len(verts4) if include_nodes else 0)
        if len(self.view.scene.prims) + need > MAX_PRIMS:
            log.info(f"[tesseract] Not enough prim budget: need {need}, have {MAX_PRIMS-len(self.view.scene.prims)}")
            return
        # Create prims
        color_edge = (0.9, 0.8, 0.35)
        color_node = (0.85, 0.55, 0.2)
        # Initial angles
        angs = { 'xy': float(self._tess_ang_xy.value()), 'xz': float(self._tess_ang_xz.value()), 'xw': float(self._tess_ang_xw.value()),
                 'yz': float(self._tess_ang_yz.value()), 'yw': float(self._tess_ang_yw.value()), 'zw': float(self._tess_ang_zw.value()) }
        pidx_edges = []
        for (i,j) in edges:
            pr = Prim(KIND_CAPSULE, [er, 1.0, 0.0, 0.0], beta=0.0, color=color_edge)
            self.view.scene.add(pr)
            pidx_edges.append(len(self.view.scene.prims)-1)
        pidx_nodes = []
        if include_nodes:
            for _ in verts4:
                pr = Prim(KIND_SPHERE, [nr, 0.0, 0.0, 0.0], beta=0.0, color=color_node)
                self.view.scene.add(pr)
                pidx_nodes.append(len(self.view.scene.prims)-1)
        rig = {
            'type':'tesseract', 'edges':edges, 'verts4':verts4,
            'pidx_edges':pidx_edges, 'pidx_nodes':pidx_nodes,
            'edge_r':er, 'node_r':nr, 'L':L,
            'proj':proj, 'fw':fw,
            'angs':angs,
            'autospin': bool(self._tess_autospin.isChecked()), 'speed': float(self._tess_speed.value())
        }
        self._rigs.append(rig)
        self._refresh_prim_label(); self.view.update()
        self._update_tesseract_rig(rig)

    def _update_rigs(self):
        if not self._rigs:
            return
        dt = 0.033
        for rig in self._rigs:
            try:
                if rig.get('type') == 'tesseract':
                    if rig.get('autospin', False):
                        sp = float(rig.get('speed', 0.0))
                        for k in ('xy','xz','xw','yz','yw','zw'):
                            rig['angs'][k] = float(rig['angs'][k]) + sp*dt
                    self._update_tesseract_rig(rig)
                elif rig.get('type') == 'molecule':
                    if rig.get('autospin', False):
                        rig['angle'] = float(rig.get('angle', 0.0)) + float(rig.get('speed', 0.0)) * dt
                    
                    # Handle molecule growth animation (for dramatic spawn)
                    if 'growth' in rig:
                        growth = rig['growth']
                        growth['start_time'] += dt
                        t = growth['start_time']
                        dur = growth['duration']
                        
                        if t < dur:
                            # Smooth growth curve
                            k = t / dur
                            kk = k * k * (3.0 - 2.0 * k)  # smoothstep
                            
                            # Scale atoms and bonds from tiny to full size
                            target_atom = growth['target_atom_scale']
                            target_bond = growth['target_bond_r']
                            target_speed = growth['target_speed']
                            
                            current_atom_scale = 0.1 * target_atom * (1.0 - kk) + target_atom * kk
                            current_bond_r = 0.1 * target_bond * (1.0 - kk) + target_bond * kk
                            current_speed = 60.0 * (1.0 - kk) + target_speed * kk
                            
                            # Update molecule size in real-time
                            for pidx in rig.get('pidx_atoms', []):
                                if pidx < len(self.view.scene.prims):
                                    pr = self.view.scene.prims[pidx]
                                    # Scale radius based on original atom properties
                                    base_r = pr.params[0] / (current_atom_scale / target_atom) if target_atom > 0 else 0.5
                                    pr.params[0] = float(base_r * current_atom_scale / target_atom)
                            
                            for pidx in rig.get('pidx_bonds', []):
                                if pidx < len(self.view.scene.prims):
                                    pr = self.view.scene.prims[pidx]
                                    pr.params[0] = float(current_bond_r)
                            
                            rig['speed'] = current_speed
                        else:
                            # Growth complete
                            del rig['growth']
                    
                    self._update_molecule_rig(rig)
                elif rig.get('type') == 'scale_sphere':
                    self._update_scale_sphere_rig(rig, dt)

            except Exception as e:
                log.debug(f"rig update failed: {e}")
        # remove finished rigs
        self._rigs = [r for r in self._rigs if not r.get('done')]

    def _update_tesseract_rig(self, rig):
        import math
        verts4 = rig['verts4']
        angs = rig['angs']
        proj = rig['proj']; fw = rig['fw']
        # Build 4D rotation matrix
        def R4_plane(i,j,deg):
            a = math.radians(float(deg)); c = math.cos(a); s = math.sin(a)
            R = np.eye(4, dtype=np.float32)
            R[i,i]=c; R[i,j]=-s; R[j,i]=s; R[j,j]=c
            return R
        R = np.eye(4, dtype=np.float32)
        R = R4_plane(0,1,angs['xy']) @ R
        R = R4_plane(0,2,angs['xz']) @ R
        R = R4_plane(0,3,angs['xw']) @ R
        R = R4_plane(1,2,angs['yz']) @ R
        R = R4_plane(1,3,angs['yw']) @ R
        R = R4_plane(2,3,angs['zw']) @ R
        # Transform and project
        v3 = []
        for v in verts4:
            vv = (R @ v.reshape(4,1)).reshape(4)
            x,y,z,w = float(vv[0]), float(vv[1]), float(vv[2]), float(vv[3])
            if proj == 0:
                p = np.array([x,y,z], np.float32)
            else:
                factor = fw / max(1e-3, (fw - w))
                p = np.array([x*factor, y*factor, z*factor], np.float32)
            v3.append(p)
        # Center offset
        center = np.array([0.0, 0.0, 0.0], np.float32)
        v3 = [p + center for p in v3]
        # Update edges
        for eidx, (i,j) in enumerate(rig['edges']):
            a = v3[i]; b = v3[j]
            mid = (a+b)*0.5
            dirv = b - a
            h = float(max(1e-6, np.linalg.norm(dirv)))
            y = dirv / max(1e-6, np.linalg.norm(dirv))
            # Build orthonormal basis (x,y,z) with y along dir
            tmp = np.array([1.0, 0.0, 0.0], np.float32) if abs(float(y[0])) < 0.9 else np.array([0.0, 0.0, 1.0], np.float32)
            x = np.cross(tmp, y); x /= max(1e-6, np.linalg.norm(x))
            z = np.cross(y, x)
            M = np.eye(4, dtype=np.float32)
            M[:3,0] = x; M[:3,1] = y; M[:3,2] = z; M[:3,3] = mid
            pr = self.view.scene.prims[rig['pidx_edges'][eidx]]
            pr.params[0] = float(rig['edge_r']); pr.params[1] = float(h)
            pr.xform.M = M
            try: pr.xform.M_inv = np.linalg.inv(M)
            except Exception: pr.xform.M_inv = None
        # Update nodes
        if rig['pidx_nodes']:
            for vidx, pidx in enumerate(rig['pidx_nodes']):
                pr = self.view.scene.prims[pidx]
                M = np.eye(4, dtype=np.float32); M[:3,3] = v3[vidx]
                pr.xform.M = M
                try: pr.xform.M_inv = np.linalg.inv(M)
                except Exception: pr.xform.M_inv = None
        try: self.view.scene._notify()
        except Exception: pass
        self.view.update()

    def _tesseract_vertices4(self, L):
        # 16 vertices with coords at +/- L/2 in 4D
        s = float(L) * 0.5
        verts = []
        for sx in (-s, s):
            for sy in (-s, s):
                for sz in (-s, s):
                    for sw in (-s, s):
                        verts.append(np.array([sx, sy, sz, sw], np.float32))
        return verts

    def _tesseract_edges(self):
        # Edges connect vertices differing in exactly one coordinate
        edges = []
        def idx_of(bits):
            # bits is tuple (bx,by,bz,bw) with 0 or 1
            return (bits[0]<<3) | (bits[1]<<2) | (bits[2]<<1) | bits[3]
        for bx in (0,1):
            for by in (0,1):
                for bz in (0,1):
                    for bw in (0,1):
                        b = (bx,by,bz,bw)
                        i = idx_of(b)
                        for dim in range(4):
                            bb = list(b); bb[dim] = 1 - bb[dim]
                            j = idx_of(tuple(bb))
                            if i < j:
                                edges.append((i,j))
        return edges

    # --- Pixel-to-Quantum scale helpers -----------------------------------
    def _ensure_scale_sphere_rig(self):
        try:
            rig = getattr(self, '_scale_rig_ref', None)
            if rig is not None:
                rig['disabled'] = False
                if rig not in self._rigs:
                    self._rigs.append(rig)
                return rig
            rig = self._build_scale_sphere_rig()
            if rig is None:
                return None
            self._scale_rig_ref = rig
            if rig not in self._rigs:
                self._rigs.append(rig)
            self._update_scale_sphere_rig(rig, 0.0)
            return rig
        except Exception as exc:
            log.debug(f"ensure scale sphere failed: {exc}")
            return None

    def _build_scale_sphere_rig(self):
        try:
            view = self.view
            center = np.array(getattr(view, 'cam_target', [0.0, 0.0, 0.0]), dtype=np.float32)
            pixels_widget = getattr(self, '_scale_pixels', None)
            duration_widget = getattr(self, '_scale_duration', None)
            fov_widget = getattr(self, '_scale_fov', None)
            pixels = float(pixels_widget.value()) if pixels_widget is not None else 2.5
            fov_deg = float(fov_widget.value()) if fov_widget is not None else 60.0
            eps_now, depth_now, width_px = _compute_world_tolerance(view, center, pixels, fov_deg)
            base_radius = max(1e-5, 0.5 * (2.0 * depth_now * math.tan(math.radians(fov_deg) * 0.5) / max(1.0, width_px)))
            base_color = (0.72, 0.78, 0.92)
            scene = view.scene

            def _unit(vec):
                v = np.array(vec, dtype=np.float32)
                n = float(np.linalg.norm(v))
                return v if n < 1e-6 else v / n

            axes = [_unit(v) for v in ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))]
            diag = [_unit(v) for v in ((1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0), (1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1))]
            corners = [_unit(v) for v in ((1, 1, 1), (-1, 1, 1), (1, -1, 1), (-1, -1, 1), (1, 1, -1), (-1, 1, -1), (1, -1, -1), (-1, -1, -1))]

            def scaled(k: float) -> float:
                return max(base_radius * k, 1e-6)

            micro_r = scaled(0.35)
            meso_r = scaled(0.22)
            molecular_r = scaled(0.12)
            atomic_outer_r = scaled(0.07)
            atomic_bohr_r = scaled(0.045)
            nuclear_r = scaled(0.02)
            subnuclear_r = scaled(0.012)
            halo_r = scaled(1.4)

            feature_specs = []
            for direction in axes:
                offset = direction * (base_radius + micro_r * 0.6)
                feature_specs.append({
                    'level': 'micro',
                    'offset': offset,
                    'max_radius': micro_r,
                    'min_radius': max(1e-6, micro_r * 0.04),
                    'color': (0.63, 0.66, 0.70),
                })
            for direction in diag:
                offset = direction * (base_radius + meso_r * 0.3)
                feature_specs.append({
                    'level': 'meso',
                    'offset': offset,
                    'max_radius': meso_r,
                    'min_radius': max(1e-6, meso_r * 0.04),
                    'color': (0.78, 0.68, 0.52),
                })
            for direction in corners[::2]:
                offset = direction * (base_radius * 0.55)
                feature_specs.append({
                    'level': 'molecular',
                    'offset': offset,
                    'max_radius': molecular_r,
                    'min_radius': max(1e-6, molecular_r * 0.05),
                    'color': (0.28, 0.82, 0.72),
                })
            for direction in axes:
                offset = direction * (base_radius * 0.32)
                feature_specs.append({
                    'level': 'atomic_outer',
                    'offset': offset,
                    'max_radius': atomic_outer_r,
                    'min_radius': max(1e-6, atomic_outer_r * 0.05),
                    'color': (0.48, 0.42, 0.88),
                })
            for direction in axes:
                offset = direction * (base_radius * 0.18)
                feature_specs.append({
                    'level': 'atomic_bohr',
                    'offset': offset,
                    'max_radius': atomic_bohr_r,
                    'min_radius': max(1e-6, atomic_bohr_r * 0.05),
                    'color': (0.66, 0.48, 0.92),
                })
            feature_specs.append({
                'level': 'nuclear',
                'offset': np.zeros(3, dtype=np.float32),
                'max_radius': nuclear_r,
                'min_radius': max(1e-6, nuclear_r * 0.1),
                'color': (0.92, 0.32, 0.30),
            })
            for direction in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
                offset = _unit(direction) * (base_radius * 0.08)
                feature_specs.append({
                    'level': 'subnuclear',
                    'offset': offset,
                    'max_radius': subnuclear_r,
                    'min_radius': max(1e-6, subnuclear_r * 0.1),
                    'color': (0.95, 0.55, 0.88),
                })
            feature_specs.append({
                'level': 'deep_quantum',
                'offset': np.zeros(3, dtype=np.float32),
                'max_radius': halo_r,
                'min_radius': max(1e-5, halo_r * 0.1),
                'color': (0.20, 0.36, 0.82),
                'color_a': (0.20, 0.36, 0.82),
                'color_b': (0.55, 0.72, 0.96),
            })

            total_needed = 1 + len(feature_specs)
            if len(scene.prims) + total_needed > MAX_PRIMS:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(
                    self,
                    "Scale Journey",
                    f"Not enough primitive budget for scale sphere (need {total_needed}, have {MAX_PRIMS - len(scene.prims)})",
                )
                return None

            base = Prim(KIND_SPHERE, [base_radius, 0.0, 0.0, 0.0], color=base_color)
            base.set_transform(pos=center, euler=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0))
            scene.add(base)
            base_idx = len(scene.prims) - 1
            features = []
            for spec in feature_specs:
                pr = Prim(KIND_SPHERE, [spec['min_radius'], 0.0, 0.0, 0.0], color=spec['color'])
                pr.set_transform(pos=center + spec['offset'], euler=(0.0, 0.0, 0.0), scale=(1.0, 1.0, 1.0))
                scene.add(pr)
                feat = {
                    'level': spec['level'],
                    'pidx': len(scene.prims) - 1,
                    'mode': 'radius',
                    'min': spec['min_radius'],
                    'max': spec['max_radius'],
                }
                if 'color_a' in spec and 'color_b' in spec:
                    feat['color_a'] = spec['color_a']
                    feat['color_b'] = spec['color_b']
                features.append(feat)

            rig = {
                'type': 'scale_sphere',
                'center': center,
                'base_idx': base_idx,
                'base_radius': base_radius,
                'base_min': max(base_radius * 0.1, 1e-5),
                'features': features,
                'pixels_widget': pixels_widget,
                'duration_widget': duration_widget,
                'fov_widget': fov_widget,
                'status_widget': getattr(self, '_scale_status', None),
                'pixels': pixels,
                'fov_deg': fov_deg,
                'duration': float(duration_widget.value()) if duration_widget is not None else 12.0,
                't': 0.0,
                'd0': depth_now,
                'd1': max(0.02, depth_now * 0.1),
                'running': False,
                'disabled': False,
            }
            try:
                scene._notify()
            except Exception:
                pass
            status = rig.get('status_widget')
            if status is not None:
                status.setText(f"Ready - eps~{_format_length(eps_now)}")
            return rig
        except Exception as exc:
            log.debug(f"scale sphere rig build failed: {exc}")
            return None

    def _start_scale_sphere_journey(self):
        try:
            rig = self._ensure_scale_sphere_rig()
            if rig is None:
                return
            rig['disabled'] = False
            if rig.get('pixels_widget') is not None:
                rig['pixels'] = float(rig['pixels_widget'].value())
            if rig.get('fov_widget') is not None:
                rig['fov_deg'] = float(rig['fov_widget'].value())
            if rig.get('duration_widget') is not None:
                rig['duration'] = float(rig['duration_widget'].value())
            rig['t'] = 0.0
            rig['running'] = True
            pixels = rig.get('pixels', 2.5)
            fov_deg = rig.get('fov_deg', 60.0)
            _, _, width_px = _compute_world_tolerance(self.view, rig['center'], pixels, fov_deg)
            start_eps = _SCALE_LEVELS[0][1] * 15.0
            end_eps = _SCALE_LEVELS[-1][1] * 0.5
            rig['d0'] = max(_distance_for_epsilon(start_eps, width_px, pixels, fov_deg), rig['base_radius'] * 40.0)
            rig['d1'] = max(0.02, min(_distance_for_epsilon(end_eps, width_px, pixels, fov_deg), rig['base_radius'] * 0.2))
            if rig['d0'] <= rig['d1']:
                rig['d0'] = max(rig['d1'] * 3.0, rig['base_radius'] * 10.0)
            self.view.distance = float(rig['d0'])
            self.view._update_camera()
            status = rig.get('status_widget')
            if status is not None:
                status.setText("Journey in progress...")
            self._update_scale_sphere_rig(rig, 0.0)
        except Exception as exc:
            log.debug(f"start scale sphere journey failed: {exc}")

    def _stop_scale_sphere(self):
        try:
            rig = getattr(self, '_scale_rig_ref', None)
            if not rig:
                if getattr(self, '_scale_status', None) is not None:
                    self._scale_status.setText("Scale sphere idle.")
                return
            rig['running'] = False
            rig['disabled'] = True
            rig['t'] = 0.0
            for feat in rig.get('features', []):
                pidx = feat.get('pidx', -1)
                if 0 <= pidx < len(self.view.scene.prims) and feat.get('mode') == 'radius':
                    self.view.scene.prims[pidx].params[0] = float(feat['min'])
            base_idx = rig.get('base_idx', -1)
            if 0 <= base_idx < len(self.view.scene.prims):
                self.view.scene.prims[base_idx].params[0] = float(rig.get('base_radius', self.view.scene.prims[base_idx].params[0]))
            try:
                self.view.scene._notify()
            except Exception:
                pass
            status = rig.get('status_widget')
            if status is not None:
                status.setText("Scale sphere paused.")
            self.view.update()
        except Exception as exc:
            log.debug(f"stop scale sphere failed: {exc}")

    def _update_scale_sphere_rig(self, rig, dt):
        try:
            if rig.get('disabled'):
                return
            if rig.get('pixels_widget') is not None:
                rig['pixels'] = float(rig['pixels_widget'].value())
            if rig.get('fov_widget') is not None:
                rig['fov_deg'] = float(rig['fov_widget'].value())
            if not rig.get('running') and rig.get('duration_widget') is not None:
                rig['duration'] = float(rig['duration_widget'].value())
            if rig.get('running'):
                rig['t'] += dt
                dur = max(1e-3, float(rig.get('duration', 12.0)))
                if rig['t'] > dur:
                    rig['t'] = dur
                eased = _smoothstep(0.0, 1.0, rig['t'] / dur)
                d = rig.get('d0', self.view.distance) * (1.0 - eased) + rig.get('d1', rig.get('d0', self.view.distance) * 0.5) * eased
                self.view.distance = float(max(0.02, d))
                self.view._update_camera()
                if rig['t'] >= dur:
                    rig['running'] = False
            pixels = rig.get('pixels', 2.5)
            fov_deg = rig.get('fov_deg', 60.0)
            eps, _, _ = _compute_world_tolerance(self.view, rig['center'], pixels, fov_deg)
            rig['last_eps'] = eps
            weights = {name: _level_activation(name, eps) for name, _ in _SCALE_LEVELS}
            refreshed = False
            for feat in rig.get('features', []):
                pidx = feat.get('pidx', -1)
                if not (0 <= pidx < len(self.view.scene.prims)):
                    continue
                pr = self.view.scene.prims[pidx]
                w = weights.get(feat['level'], 0.0)
                w = max(0.0, min(1.0, w))
                if feat.get('mode') == 'radius':
                    target = feat['min'] + (feat['max'] - feat['min']) * w
                    target = max(feat['min'], target)
                    if abs(float(pr.params[0]) - float(target)) > 1e-7:
                        pr.params[0] = float(target)
                        refreshed = True
                if 'color_a' in feat and 'color_b' in feat:
                    col = tuple(feat['color_a'][i] * (1.0 - w) + feat['color_b'][i] * w for i in range(3))
                    pr.color[:] = col
                    refreshed = True
            if refreshed:
                try:
                    self.view.scene._notify()
                except Exception:
                    pass
            status = rig.get('status_widget')
            if status is not None:
                level, nxt, blend = _lod_state(eps)
                eps_text = _format_length(eps)
                if nxt:
                    status.setText(f"{level.replace('_', ' ').title()} -> {nxt.replace('_', ' ').title()} ({blend * 100.0:.0f}%) | eps~{eps_text}")
                else:
                    status.setText(f"{level.replace('_', ' ').title()} | eps~{eps_text}")
            self.view.update()
        except Exception as exc:
            log.debug(f"scale sphere update failed: {exc}")

    # --- Molecule import ---
    def _import_xyz_molecule(self):
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            path, _ = QFileDialog.getOpenFileName(self, "Import Molecule (XYZ)", filter="XYZ (*.xyz)")
            if not path:
                return
            atoms = self._parse_xyz(path)
            if not atoms:
                QMessageBox.information(self, "Import XYZ", "No atoms parsed.")
                return
            # Build rig with bonds and add to scene
            rig = self._build_molecule_rig(atoms,
                                           atom_scale=float(self._mol_atom_scale.value()),
                                           bond_r=float(self._mol_bond_r.value()),
                                           bond_thresh=float(self._mol_bond_thresh.value()),
                                           autospin=bool(self._mol_autospin.isChecked()),
                                           speed=float(self._mol_speed.value()))
            if rig is None:
                return
            self._rigs.append(rig)
            self._refresh_prim_label(); self.view.update()
        except Exception as e:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Import XYZ", f"Failed: {e}")
            except Exception:
                pass

    def _parse_xyz(self, path: str):
        atoms = []
        try:
            with open(path, 'r', encoding='utf-8') as f:
                lines = [ln.strip() for ln in f if ln.strip()]
            if not lines:
                return []
            try:
                n = int(lines[0].split()[0])
                start = 2 if len(lines) > 1 else 1
            except Exception:
                n = len(lines)
                start = 0
            for ln in lines[start:start+n]:
                parts = ln.split()
                if len(parts) < 4:
                    continue
                sym = parts[0]
                try:
                    x, y, z = float(parts[1]), float(parts[2]), float(parts[3])
                except Exception:
                    continue
                color, rcov = self._element_color_radius(sym)
                atoms.append({'sym': sym, 'pos': np.array([x, y, z], np.float32), 'color': color, 'rcov': rcov})
        except Exception:
            return []
        return atoms

    def _element_color_radius(self, sym: str):
        s = sym.capitalize()
        # Simple JMol-like colors and covalent radii (Ãƒâ€¦) for common elements; defaults otherwise
        colors = {
            'H': (1.0, 1.0, 1.0), 'C': (0.3, 0.3, 0.3), 'N': (0.1, 0.1, 0.9), 'O': (0.9, 0.1, 0.1),
            'S': (0.9, 0.9, 0.2), 'P': (1.0, 0.5, 0.0), 'F': (0.1, 0.9, 0.1), 'Cl': (0.1, 0.8, 0.1)
        }
        rcov = {
            'H': 0.31, 'C': 0.76, 'N': 0.71, 'O': 0.66, 'S': 1.05, 'P': 1.07, 'F': 0.57, 'Cl': 1.02
        }.get(s, 0.8)
        return colors.get(s, (0.7, 0.7, 0.7)), rcov

    def _build_molecule_rig(self, atoms, atom_scale=0.6, bond_r=0.035, bond_thresh=0.2, autospin=True, speed=25.0):
        try:
            pts = np.array([a['pos'] for a in atoms], dtype=np.float32)
            ctr = pts.mean(axis=0)
            pts -= ctr
            # Bond detection by covalent radii sum + threshold (Ãƒâ€¦)
            bonds = []
            N = len(atoms)
            for i in range(N):
                for j in range(i+1, N):
                    rij = np.linalg.norm(pts[i] - pts[j])
                    if rij <= (atoms[i]['rcov'] + atoms[j]['rcov'] + bond_thresh):
                        bonds.append((i, j))
            need = N + len(bonds)
            if len(self.view.scene.prims) + need > MAX_PRIMS:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Import XYZ", f"Not enough primitive budget for molecule: need {need}, have {MAX_PRIMS-len(self.view.scene.prims)}")
                return None
            pidx_atoms = []
            for i, a in enumerate(atoms):
                r = float(atom_scale * max(0.2, a.get('rcov', 0.8)) * 0.5)
                pr = Prim(KIND_SPHERE, [r, 0, 0, 0], beta=0.0, color=tuple(a.get('color', (0.7, 0.7, 0.7))))
                M = np.eye(4, dtype=np.float32); M[:3,3] = pts[i]
                pr.xform.M = M
                try: pr.xform.M_inv = np.linalg.inv(M)
                except Exception: pr.xform.M_inv = None
                self.view.scene.add(pr)
                pidx_atoms.append(len(self.view.scene.prims)-1)
            pidx_bonds = []
            for (i, j) in bonds:
                pr = Prim(KIND_CAPSULE, [float(bond_r), 1.0, 0.0, 0.0], beta=0.0, color=(0.85, 0.85, 0.85))
                self.view.scene.add(pr)
                pidx_bonds.append(len(self.view.scene.prims)-1)
            rig = {
                'type': 'molecule',
                'pts': pts,  # Nx3 np.array
                'bonds': bonds,
                'pidx_atoms': pidx_atoms,
                'pidx_bonds': pidx_bonds,
                'bond_r': float(bond_r),
                'autospin': bool(autospin),
                'speed': float(speed),
                'angle': 0.0
            }
            # Apply initial placement
            self._update_molecule_rig(rig)
            return rig
        except Exception as e:
            log.debug(f"molecule build failed: {e}")
            return None

    def _update_molecule_rig(self, rig):
        try:
            # Simple rotation about Y axis by angle (degrees)
            ang = float(rig.get('angle', 0.0))
            ca = np.cos(np.deg2rad(ang)); sa = np.sin(np.deg2rad(ang))
            R = np.array([[ ca, 0.0,  sa],
                          [0.0, 1.0, 0.0],
                          [-sa, 0.0,  ca]], dtype=np.float32)
            pts_rot = (R @ rig['pts'].T).T
            # Update atoms
            for idx, pidx in enumerate(rig['pidx_atoms']):
                pr = self.view.scene.prims[pidx]
                M = np.eye(4, dtype=np.float32); M[:3,3] = pts_rot[idx]
                pr.xform.M = M
                try: pr.xform.M_inv = np.linalg.inv(M)
                except Exception: pr.xform.M_inv = None
            # Update bonds
            for bidx, (i, j) in enumerate(rig['bonds']):
                a = pts_rot[i]; b = pts_rot[j]
                mid = (a + b) * 0.5
                dirv = b - a
                h = float(max(1e-6, np.linalg.norm(dirv)))
                y = dirv / max(1e-6, np.linalg.norm(dirv))
                tmp = np.array([1.0, 0.0, 0.0], np.float32) if abs(float(y[0])) < 0.9 else np.array([0.0, 0.0, 1.0], np.float32)
                x = np.cross(tmp, y); x /= max(1e-6, np.linalg.norm(x))
                z = np.cross(y, x)
                M = np.eye(4, dtype=np.float32)
                M[:3,0] = x; M[:3,1] = y; M[:3,2] = z; M[:3,3] = mid
                pr = self.view.scene.prims[rig['pidx_bonds'][bidx]]
                pr.params[0] = float(rig['bond_r']); pr.params[1] = float(h)
                pr.xform.M = M
                try: pr.xform.M_inv = np.linalg.inv(M)
                except Exception: pr.xform.M_inv = None
            try: self.view.scene._notify()
            except Exception: pass
            self.view.update()
        except Exception as e:
            log.debug(f"molecule update failed: {e}")

    def _update_sketch_info(self, sel_key):
        try:
            if sel_key is None:
                self._sketch_info_label.setText("No selection"); return
            if isinstance(sel_key, tuple) and len(sel_key)==2 and isinstance(sel_key[0], Polyline2D):
                ent, idx = sel_key
                self._sketch_info_label.setText(f"Polyline: {len(getattr(ent,'pts',[]))} pts, vertex #{idx}")
                return
            if isinstance(sel_key, tuple) and sel_key[0]=='circle' and isinstance(sel_key[1], Circle2D):
                ent = sel_key[1]
                self._sketch_info_label.setText(f"Circle: r={getattr(ent,'radius',0.0):.3f}")
                return
            self._sketch_info_label.setText("Selection: unknown")
        except Exception:
            try:
                self._sketch_info_label.setText("Selection: error")
            except Exception:
                pass

    # --- UI callbacks ---

    def _sync_wheel_controls(self) -> None:
        if not _HAVE_WHEEL:
            return
        if self._cb_wheel_enabled is not None:
            self._cb_wheel_enabled.blockSignals(True)
            self._cb_wheel_enabled.setChecked(bool(self._wheel_enabled))
            self._cb_wheel_enabled.blockSignals(False)
        if self._cb_wheel_edge_fit is not None:
            self._cb_wheel_edge_fit.blockSignals(True)
            self._cb_wheel_edge_fit.setChecked(bool(self._wheel_edge_fit))
            self._cb_wheel_edge_fit.blockSignals(False)
        if self._spin_wheel_overshoot is not None:
            self._spin_wheel_overshoot.blockSignals(True)
            self._spin_wheel_overshoot.setValue(int(self._wheel_edge_overshoot))
            self._spin_wheel_overshoot.setEnabled(bool(self._wheel_edge_fit))
            self._spin_wheel_overshoot.blockSignals(False)
        if self._slider_wheel_thickness is not None:
            val = int(round(self._wheel_thickness * 100))
            self._slider_wheel_thickness.blockSignals(True)
            self._slider_wheel_thickness.setValue(val)
            self._slider_wheel_thickness.blockSignals(False)
            if self._label_wheel_thickness is not None:
                self._label_wheel_thickness.setText(f"{val}%")
        if self._slider_wheel_opacity is not None:
            val = int(round(self._wheel_opacity * 100))
            self._slider_wheel_opacity.blockSignals(True)
            self._slider_wheel_opacity.setValue(val)
            self._slider_wheel_opacity.blockSignals(False)
            if self._label_wheel_opacity is not None:
                self._label_wheel_opacity.setText(f"{val}%")
        if self._slider_wheel_text is not None:
            val = int(round(self._wheel_text_scale * 100))
            self._slider_wheel_text.blockSignals(True)
            self._slider_wheel_text.setValue(val)
            self._slider_wheel_text.blockSignals(False)
            if self._label_wheel_text is not None:
                self._label_wheel_text.setText(f"{val/100:.2f}x")
        if self._cb_wheel_autospin is not None:
            self._cb_wheel_autospin.blockSignals(True)
            self._cb_wheel_autospin.setChecked(bool(self._wheel_auto_spin))
            self._cb_wheel_autospin.blockSignals(False)
        if self._slider_wheel_spin is not None:
            val = int(round(self._wheel_auto_spin_speed))
            self._slider_wheel_spin.blockSignals(True)
            self._slider_wheel_spin.setValue(val)
            self._slider_wheel_spin.blockSignals(False)
            self._slider_wheel_spin.setEnabled(bool(self._wheel_auto_spin))
            if self._label_wheel_spin is not None:
                self._label_wheel_spin.setText(f"{val} deg/s")

    def _apply_wheel_settings(self, persist: bool = False) -> None:
        if not _HAVE_WHEEL:
            return
        wheel = getattr(self, '_radial_wheel', None)
        if wheel is None:
            return
        wheel.setVisible(bool(self._wheel_enabled))
        if self._wheel_enabled:
            wheel.show()
            wheel.raise_()
        wheel.set_fit_to_viewport_edge(bool(self._wheel_edge_fit))
        wheel.set_edge_overshoot(int(self._wheel_edge_overshoot))
        wheel.set_thickness_ratio(float(self._wheel_thickness))
        wheel.set_opacity(float(self._wheel_opacity))
        wheel.set_text_scale(float(self._wheel_text_scale))
        wheel.set_min_alpha(0.20 if self._wheel_enabled else 0.0)
        spin_speed = float(self._wheel_auto_spin_speed) if self._wheel_auto_spin else 0.0
        wheel.set_idle_rotation(spin_speed)
        if persist:
            self._persist_wheel_settings()

    def _persist_wheel_settings(self) -> None:
        try:
            self.view._save_settings()
        except Exception:
            pass

    def _on_wheel_enabled(self, checked: bool) -> None:
        self._wheel_enabled = bool(checked)
        self._apply_wheel_settings()
        self._persist_wheel_settings()

    def _on_wheel_edge_fit(self, checked: bool) -> None:
        self._wheel_edge_fit = bool(checked)
        if self._spin_wheel_overshoot is not None:
            self._spin_wheel_overshoot.setEnabled(self._wheel_edge_fit)
        self._apply_wheel_settings()
        self._persist_wheel_settings()

    def _on_wheel_overshoot(self, value: int) -> None:
        self._wheel_edge_overshoot = int(value)
        self._apply_wheel_settings()
        self._persist_wheel_settings()

    def _on_wheel_thickness(self, value: int) -> None:
        self._wheel_thickness = max(0.02, min(0.40, value / 100.0))
        self._apply_wheel_settings()
        self._persist_wheel_settings()

    def _on_wheel_opacity(self, value: int) -> None:
        self._wheel_opacity = max(0.0, min(1.0, value / 100.0))
        self._apply_wheel_settings()
        self._persist_wheel_settings()

    def _on_wheel_text_scale(self, value: int) -> None:
        self._wheel_text_scale = max(0.5, min(2.5, value / 100.0))
        self._apply_wheel_settings()
        self._persist_wheel_settings()

    def _on_wheel_autospin(self, checked: bool) -> None:
        self._wheel_auto_spin = bool(checked)
        if self._slider_wheel_spin is not None:
            self._slider_wheel_spin.setEnabled(self._wheel_auto_spin)
        self._apply_wheel_settings()
        self._persist_wheel_settings()

    def _on_wheel_spin_speed(self, value: int) -> None:
        self._wheel_auto_spin_speed = float(max(0, value))
        self._apply_wheel_settings()
        self._persist_wheel_settings()

    def _on_mode(self, idx:int):
        self.view.debug_mode = idx
        self.view._update_title(); self.view.update()

    def _on_toggle(self):
        self.view.use_analytic_aa = 1 if self.cb_aa.isChecked() else 0
        self.view.use_foveated = 1 if self.cb_fov.isChecked() else 0
        self.view.use_toon = 1 if self.cb_toon.isChecked() else 0
        self.view.show_beta_overlay = 1 if self.cb_beta.isChecked() else 0
        self.view._update_title(); self.view.update(); self.view._save_settings()

    def _on_toon_levels(self, v:int):
        self.view.toon_levels = float(v)
        if self.view.use_toon:
            self.view.update(); self.view._save_settings()

    def _on_curv(self, v:int):
        self.view.curv_strength = v/100.0
        self.view.update(); self.view._save_settings()

    def _on_beta_int(self, v:int):
        self.view.beta_overlay_intensity = v/100.0
        if self.view.show_beta_overlay:
            self.view.update(); self.view._save_settings()

    def _on_beta_scale(self, v:int):
        self.view.beta_scale = v/100.0
        if self.view.show_beta_overlay:
            self.view.update(); self.view._save_settings()

    def _on_cmap(self, idx:int):
        self.view.beta_cmap = idx
        if self.view.show_beta_overlay:
            self.view.update()
        self.view._save_settings(); self.view._update_title()

    # --- Environment callbacks ---
    def _on_bg_changed(self, _v):
        for i,s in enumerate(self._bg_sliders):
            self.view.scene.bg_color[i] = s.value()/255.0
        self.view.update()

    def _on_env_changed(self, _v):
        for i,s in enumerate(self._env_sliders):
            self.view.scene.env_light[i] = s.value()/100.0
        self.view.update()

    # --- Radial wheel handler ---
    def _delete_last_sketch_item(self) -> None:
        layer = getattr(self, '_sketch', None)
        if layer is None:
            return
        removed = False
        active_poly = getattr(layer, 'active_poly', None)
        if active_poly is not None and getattr(active_poly, 'pts', None):
            if active_poly.pts:
                active_poly.pts.pop()
                if not active_poly.pts:
                    layer.active_poly = None
                removed = True
        elif getattr(layer, 'dimensions', None):
            if layer.dimensions:
                layer.dimensions.pop()
                removed = True
        if not removed and getattr(layer, 'entities', None):
            if layer.entities:
                layer.entities.pop()
                removed = True
        if removed:
            try:
                self.view.update()
            except Exception:
                pass

    def _register_section(self, key: str, label: str, widget: QWidget, default_visible: bool = True) -> None:
        if not hasattr(self, '_section_vis') or not isinstance(self._section_vis, dict):
            self._section_vis = {}
        state = bool(self._section_vis.get(key, default_visible))
        self._section_vis[key] = state
        if not hasattr(self, '_section_groups') or not isinstance(self._section_groups, dict):
            self._section_groups = {}
        self._section_groups[key] = widget
        widget.setVisible(state)
        layout = getattr(self, '_section_toggle_layout', None)
        if layout is None:
            return
        toggles = getattr(self, '_section_toggles', {})
        if key in toggles:
            btn = toggles[key]
            btn.blockSignals(True)
            btn.setChecked(state)
            btn.blockSignals(False)
            return
        btn = QToolButton()
        btn.setText(label)
        btn.setCheckable(True)
        btn.setAutoRaise(True)
        btn.setToolButtonStyle(Qt.ToolButtonTextOnly)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        btn.setChecked(state)
        btn.toggled.connect(partial(self._on_section_toggle, key))
        idx = getattr(self, '_section_toggle_count', 0)
        cols = getattr(self, '_section_toggle_columns', 3) or 1
        row = idx // cols
        col = idx % cols
        layout.addWidget(btn, row, col)
        self._section_toggle_count = idx + 1
        toggles[key] = btn
        self._section_toggles = toggles

    def _sync_fractal_controls(self) -> None:
        try:
            if self._fractal_mode_box is not None:
                self._fractal_mode_box.blockSignals(True)
                self._fractal_mode_box.setCurrentIndex(int(self.view.fractal_color_mode))
                self._fractal_mode_box.blockSignals(False)
            if self._fractal_shell_spin is not None:
                self._fractal_shell_spin.blockSignals(True)
                self._fractal_shell_spin.setValue(float(self.view.fractal_orbit_shell))
                self._fractal_shell_spin.blockSignals(False)
            if self._fractal_ni_spin is not None:
                self._fractal_ni_spin.blockSignals(True)
                self._fractal_ni_spin.setValue(float(self.view.fractal_ni_scale))
                self._fractal_ni_spin.blockSignals(False)
            if self._mb_color_box is not None:
                self._mb_color_box.blockSignals(True)
                self._mb_color_box.setCurrentIndex(int(self.view.fractal_color_mode))
                self._mb_color_box.blockSignals(False)
        except Exception:
            pass

    def _on_fractal_mode_changed(self, idx: int) -> None:
        try:
            self.view.fractal_color_mode = int(idx)
            if self._mb_color_box is not None and self._mb_color_box.currentIndex() != int(idx):
                self._mb_color_box.blockSignals(True)
                self._mb_color_box.setCurrentIndex(int(idx))
                self._mb_color_box.blockSignals(False)
            self.view.update()
            self.view._save_settings()
        except Exception:
            pass

    def _on_fractal_shell_changed(self, value: float) -> None:
        try:
            self.view.fractal_orbit_shell = float(value)
            self.view.update()
            self.view._save_settings()
        except Exception:
            pass

    def _on_fractal_ni_changed(self, value: float) -> None:
        try:
            self.view.fractal_ni_scale = float(value)
            self.view.update()
            self.view._save_settings()
        except Exception:
            pass

    def _on_mandelbulb_export_color_mode_changed(self, idx: int) -> None:
        try:
            idx = int(idx)
            if self._fractal_mode_box is not None:
                self._fractal_mode_box.blockSignals(True)
                self._fractal_mode_box.setCurrentIndex(idx)
                self._fractal_mode_box.blockSignals(False)
            self._on_fractal_mode_changed(idx)
        except Exception:
            pass
            
    def _on_norm_mode_changed(self, idx: int) -> None:
        """Auto-adjust step scale when switching norm modes."""
        try:
            if idx == 1:  # Adaptive norm
                self._mb_step_scale_spin.setValue(0.8)
                self._mb_step_scale_spin.setToolTip("Recommended: 0.8 for adaptive norm stability.")
            else:  # Euclidean
                self._mb_step_scale_spin.setValue(1.0)
                self._mb_step_scale_spin.setToolTip("Safety factor for ray marching. Use 0.8 with adaptive norm.")
        except Exception:
            pass

    def _selected_mandelbulb_prim(self):
        if not hasattr(self.view, 'scene'):
            return None
        if not (0 <= getattr(self, '_current_sel', -1) < len(self.view.scene.prims)):
            return None
        pr = self.view.scene.prims[self._current_sel]
        if pr.kind == KIND_MANDELBULB:
            return pr
        return None

    def _apply_mandelbulb_params_to_controls(self, pr) -> None:
        if pr is None:
            return
        try:
            if self._mb_power_spin is not None:
                self._mb_power_spin.blockSignals(True)
                self._mb_power_spin.setValue(float(pr.params[0]))
                self._mb_power_spin.blockSignals(False)
            if self._mb_bailout_spin is not None and len(pr.params) > 1:
                self._mb_bailout_spin.blockSignals(True)
                self._mb_bailout_spin.setValue(float(pr.params[1]))
                self._mb_bailout_spin.blockSignals(False)
            if self._mb_iter_spin is not None and len(pr.params) > 2:
                self._mb_iter_spin.blockSignals(True)
                self._mb_iter_spin.setValue(int(max(4, pr.params[2])))
                self._mb_iter_spin.blockSignals(False)
            if self._mb_scale_spin is not None and len(pr.params) > 3:
                self._mb_scale_spin.blockSignals(True)
                self._mb_scale_spin.setValue(float(pr.params[3]))
                self._mb_scale_spin.blockSignals(False)
        except Exception:
            pass

    def _pull_mandelbulb_params_from_selection(self) -> None:
        pr = self._selected_mandelbulb_prim()
        if pr is None:
            self._set_mb_status("Select a Mandelbulb primitive first.")
            return
        self._apply_mandelbulb_params_to_controls(pr)
        self._set_mb_status(f"Loaded parameters from Mandelbulb #{self._current_sel}.")

    def _set_mb_status(self, text: str) -> None:
        if self._mb_status_label is not None:
            self._mb_status_label.setText(text)

    def _update_mandelbulb_export_ui(self, pr) -> None:
        has_mb = pr is not None and getattr(pr, 'kind', None) == KIND_MANDELBULB
        if self._mb_export_btn is not None:
            self._mb_export_btn.setEnabled(has_mb and self._mandelbulb_worker is None)
        if self._mb_pull_btn is not None:
            self._mb_pull_btn.setEnabled(has_mb)
        if self._mb_reload_btn is not None:
            enable_reload = self._mb_last_export is not None and self._mandelbulb_worker is None
            self._mb_reload_btn.setEnabled(enable_reload)
        if self._mb_clear_overlay_btn is not None:
            self._mb_clear_overlay_btn.setEnabled(self._mb_overlay_loaded)
        if has_mb:
            self._apply_mandelbulb_params_to_controls(pr)
            self._set_mb_status(f"Ready to export Mandelbulb #{self._current_sel}.")
        else:
            self._set_mb_status("Select a Mandelbulb primitive to export.")

    def _export_mandelbulb_mesh(self) -> None:
        if self._mandelbulb_worker is not None:
            self._set_mb_status("Export already in progress.")
            return
        pr = self._selected_mandelbulb_prim()
        if pr is None:
            self._set_mb_status("Select a Mandelbulb primitive first.")
            return

        resolution = self._mb_res_spin.value() if self._mb_res_spin is not None else 160
        extent = self._mb_extent_spin.value() if self._mb_extent_spin is not None else 1.6
        power = self._mb_power_spin.value() if self._mb_power_spin is not None else float(pr.params[0])
        bailout = self._mb_bailout_spin.value() if self._mb_bailout_spin is not None else float(pr.params[1])
        max_iter = self._mb_iter_spin.value() if self._mb_iter_spin is not None else int(max(4, pr.params[2]))
        scale = self._mb_scale_spin.value() if self._mb_scale_spin is not None else (pr.params[3] if len(pr.params) > 3 else 1.0)
        color_mode = self._mb_color_box.currentIndex() if self._mb_color_box is not None else int(self.view.fractal_color_mode)
        pi_mode = "adaptive" if (self._mb_pi_mode_box is not None and self._mb_pi_mode_box.currentIndex() == 1) else "fixed"
        pi_base = self._mb_pi_base_spin.value() if self._mb_pi_base_spin is not None else float(np.pi)
        pi_alpha = self._mb_pi_alpha_spin.value() if self._mb_pi_alpha_spin is not None else 0.0
        pi_mu = self._mb_pi_mu_spin.value() if self._mb_pi_mu_spin is not None else 0.05
        orbit_shell = float(getattr(self.view, 'fractal_orbit_shell', 1.0))
        ni_scale = float(getattr(self.view, 'fractal_ni_scale', 0.08))
        use_gpu = bool(self._mb_use_gpu_chk.isChecked()) if self._mb_use_gpu_chk is not None else False
        bake_colors = bool(self._mb_colors_chk.isChecked()) if self._mb_colors_chk is not None else True

        export_root_env = (os.getenv("ADCAD_MANDELBULB_EXPORT_DIR", "") or "").strip()
        if export_root_env:
            export_root = Path(export_root_env)
        else:
            export_root = Path(__file__).resolve().parent.parent / "exports" / "mandelbulbs"
        try:
            export_root.mkdir(parents=True, exist_ok=True)
        except Exception:
            fallback_root = Path.cwd() / "mandelbulb_exports"
            fallback_root.mkdir(parents=True, exist_ok=True)
            export_root = fallback_root

        def _tag_float(val: float) -> str:
            txt = f"{val:.2f}".rstrip("0").rstrip(".")
            return txt.replace(".", "p") if txt else "0"

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        default_name = f"mandelbulb_p{_tag_float(power)}_res{int(resolution)}_{timestamp}.stl"
        default_path = str(export_root / default_name)

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Mandelbulb Mesh",
            default_path,
            "STL (*.stl);;All Files (*)",
        )
        if not path:
            return

        path_obj = Path(path)
        outfile_path = path_obj.with_suffix("") if path_obj.suffix.lower() == ".stl" else path_obj
        out_dir = outfile_path.parent
        if out_dir and out_dir != Path('.'):
            out_dir.mkdir(parents=True, exist_ok=True)

        outfile = str(outfile_path)

        transform = pr.xform.M.astype(np.float64)

        self._mandelbulb_worker = self._MandelbulbExportWorker(
            resolution=resolution,
            extent=extent,
            power=power,
            bailout=bailout,
            max_iter=max_iter,
            color_mode_index=color_mode,
            pi_mode=pi_mode,
            pi_base=pi_base,
            pi_alpha=pi_alpha,
            pi_mu=pi_mu,
            norm_mode=["euclid", "adaptive"][self._mb_norm_mode_box.currentIndex()],
            norm_k=self._mb_norm_k_spin.value(),
            norm_r0=self._mb_norm_r0_spin.value(),
            norm_sigma=self._mb_norm_sigma_spin.value(),
            step_scale=self._mb_step_scale_spin.value(),
            use_gpu_colors=self._mb_gpu_colors_chk.isChecked(),
            outfile=outfile,
            transform=transform,
            scale=scale,
            orbit_shell=orbit_shell,
            ni_scale=ni_scale,
            use_gpu=use_gpu,
            compute_colors=bake_colors,
            parent=self,
        )
        self._mandelbulb_worker.progress.connect(self._handle_mandelbulb_export_progress)
        self._mandelbulb_worker.finished.connect(self._handle_mandelbulb_export_finished)

        dlg = QProgressDialog("Starting Mandelbulb export…", None, 0, 0, self)
        dlg.setWindowTitle("Exporting Mandelbulb")
        dlg.setCancelButton(None)
        dlg.setModal(True)
        dlg.show()
        self._mb_progress_dialog = dlg
        self._set_mb_status("Exporting Mandelbulb…")

        self._mandelbulb_worker.start()
        self._update_mandelbulb_export_ui(pr)

    def _handle_mandelbulb_export_progress(self, message: str) -> None:
        self._set_mb_status(message)
        if self._mb_progress_dialog is not None:
            self._mb_progress_dialog.setLabelText(message)

    def _handle_mandelbulb_export_finished(self, ok: bool, stl_path: str, ply_path: str, err: str) -> None:
        if self._mb_progress_dialog is not None:
            self._mb_progress_dialog.hide()
            self._mb_progress_dialog.deleteLater()
            self._mb_progress_dialog = None
        self._mandelbulb_worker = None
        self._update_mandelbulb_export_ui(self._selected_mandelbulb_prim())
        if ok:
            self._mb_last_export = (stl_path, ply_path)
            if self._mb_reload_btn is not None:
                self._mb_reload_btn.setEnabled(True)
            self._set_mb_status("Export complete.")
            QMessageBox.information(self, "Mandelbulb Export", f"Saved:\n{stl_path}\n{ply_path}")
        else:
            self._set_mb_status("Export failed.")
            QMessageBox.warning(self, "Mandelbulb Export", err or "Unknown error")

    def _add_last_mandelbulb_export(self) -> None:
        if self._mb_last_export is None:
            self._set_mb_status("No Mandelbulb export available to reload.")
            return
        if not hasattr(self, 'view') or self.view is None:
            QMessageBox.warning(self, "Reload Mandelbulb", "Viewport unavailable for mesh overlay.")
            return

        stl_path, ply_path = self._mb_last_export
        candidates = [p for p in (ply_path, stl_path) if p]
        existing = None
        for candidate in candidates:
            p = Path(candidate)
            if p.exists():
                existing = p
                break
        if existing is None:
            QMessageBox.warning(
                self,
                "Reload Mandelbulb",
                "Last export files could not be found. Please export again.",
            )
            return

        try:
            import trimesh  # type: ignore

            mesh = trimesh.load(str(existing), process=False)
            if isinstance(mesh, trimesh.Scene):
                geoms = list(mesh.geometry.values())
                if not geoms:
                    raise ValueError("Mesh scene is empty")
                mesh = trimesh.util.concatenate(geoms)
            if not isinstance(mesh, trimesh.Trimesh):
                raise ValueError("Unsupported mesh type")
            if len(mesh.vertices) == 0:
                raise ValueError("Mesh has no vertices")
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Reload Mandelbulb",
                f"Failed to load exported mesh:\n{exc}",
            )
            return

        success, error_msg = self.view.add_mesh_overlay(mesh, source_path=str(existing))
        if success:
            self._set_mb_status(f"Loaded Mandelbulb overlay from {existing.name}.")
            self._mb_overlay_loaded = True
            if self._mb_clear_overlay_btn is not None:
                self._mb_clear_overlay_btn.setEnabled(True)
            self.view.update()
        else:
            QMessageBox.warning(
                self,
                "Reload Mandelbulb",
                error_msg or "Could not create mesh overlay.",
            )

    def _clear_mandelbulb_overlay(self) -> None:
        if not hasattr(self, 'view') or self.view is None:
            return
        try:
            self.view.clear_mesh_overlays()
            self._mb_overlay_loaded = False
            if self._mb_clear_overlay_btn is not None:
                self._mb_clear_overlay_btn.setEnabled(False)
            self._set_mb_status("Cleared Mandelbulb mesh overlay.")
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Clear Mandelbulb Mesh",
                f"Could not clear overlay:\n{exc}",
            )

    def _on_section_toggle(self, key: str, checked: bool) -> None:
        if not hasattr(self, '_section_vis') or not isinstance(self._section_vis, dict):
            self._section_vis = {}
        self._section_vis[key] = bool(checked)
        widget = None
        if hasattr(self, '_section_groups') and isinstance(self._section_groups, dict):
            widget = self._section_groups.get(key)
        if widget is not None:
            widget.setVisible(bool(checked))
        try:
            if hasattr(self, 'view') and hasattr(self.view, '_save_settings'):
                self.view._save_settings()
        except Exception:
            pass

    def _populate_side_panel_controls(self, side):
        # --- AI Copilot ---
        self._ai_group = QGroupBox("AI Copilot")
        ai_layout = QVBoxLayout()
        self._ai_group.setLayout(ai_layout)
        self._ai_transcript = QTextEdit()
        self._ai_transcript.setReadOnly(True)
        self._ai_transcript.setPlaceholderText("AI copilot responses will appear here.")
        self._ai_transcript.setMinimumHeight(140)
        ai_layout.addWidget(self._ai_transcript)
        ai_row = QHBoxLayout()
        self._ai_model_label = QLabel(self._ai_model)
        self._ai_model_label.setToolTip("Model used for AI requests")
        ai_row.addWidget(self._ai_model_label)
        ai_row.addStretch(1)
        self._ai_send_btn = QPushButton("Send")
        self._ai_send_btn.setEnabled(False)
        ai_row.addWidget(self._ai_send_btn)
        ai_layout.addLayout(ai_row)
        self._ai_input = QLineEdit()
        self._ai_input.setPlaceholderText("Describe what you want (e.g., 'create a 100 mm circle')")
        self._ai_input.setEnabled(False)
        ai_layout.addWidget(self._ai_input)
        side.addWidget(self._ai_group)
        self._register_section("ai_copilot", "AI Copilot", self._ai_group, default_visible=True)

        # --- AI Custom Tools ---
        self._ai_tools_group = QGroupBox("AI Custom Tools")
        ai_tools_layout = QVBoxLayout()
        self._ai_tools_group.setLayout(ai_tools_layout)
        self._ai_tools_list = QListWidget()
        self._ai_tools_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        ai_tools_layout.addWidget(self._ai_tools_list)
        tools_btn_row = QHBoxLayout()
        self._ai_tools_pin_chk = QCheckBox("Pin to Wheel")
        self._ai_tools_pin_chk.setEnabled(False)
        tools_btn_row.addWidget(self._ai_tools_pin_chk)
        tools_btn_row.addStretch(1)
        self._ai_tools_run_btn = QPushButton("Run")
        self._ai_tools_run_btn.setEnabled(False)
        self._ai_tools_delete_btn = QPushButton("Delete")
        self._ai_tools_delete_btn.setEnabled(False)
        tools_btn_row.addWidget(self._ai_tools_run_btn)
        tools_btn_row.addWidget(self._ai_tools_delete_btn)
        ai_tools_layout.addLayout(tools_btn_row)
        self._ai_tools_group.setEnabled(False)
        side.addWidget(self._ai_tools_group)
        self._register_section("ai_tools", "AI Tools", self._ai_tools_group, default_visible=False)

        # --- Gizmo / Transform Controls ---
        gb_gizmo = QGroupBox("Gizmo / Transform"); fg = QFormLayout(); gb_gizmo.setLayout(fg)
        # Mode buttons
        row_modes = QWidget(); hm = QHBoxLayout(row_modes); hm.setContentsMargins(0,0,0,0)
        btn_move = QPushButton("Move"); btn_rot = QPushButton("Rotate [R]"); btn_scl = QPushButton("Scale [S]")
        for b in (btn_move, btn_rot, btn_scl): b.setCheckable(True)
        btn_move.setChecked(True)
        def _set_mode(m):
            def f():
                btn_move.setChecked(m=='move'); btn_rot.setChecked(m=='rotate'); btn_scl.setChecked(m=='scale')
                self._gizmo_mode = m
                self._move_drag_free = (m == 'move')
            return f
        btn_move.clicked.connect(_set_mode('move'))
        btn_rot.clicked.connect(_set_mode('rotate'))
        btn_scl.clicked.connect(_set_mode('scale'))
        hm.addWidget(btn_move); hm.addWidget(btn_rot); hm.addWidget(btn_scl)
        fg.addRow("Mode", row_modes)
        # Axis lock buttons
        row_axes = QWidget(); ha = QHBoxLayout(row_axes); ha.setContentsMargins(0,0,0,0)
        ax_x = QPushButton("X"); ax_y = QPushButton("Y"); ax_z = QPushButton("Z"); ax_clr = QPushButton("Free")
        for b in (ax_x, ax_y, ax_z, ax_clr): b.setCheckable(True)
        ax_clr.setChecked(True)
        def _lock_axis(a):
            def f():
                for b,a2 in ((ax_x,'x'),(ax_y,'y'),(ax_z,'z')):
                    b.setChecked(a==a2)
                ax_clr.setChecked(a is None)
                self._axis_lock = a
            return f
        ax_x.clicked.connect(_lock_axis('x'))
        ax_y.clicked.connect(_lock_axis('y'))
        ax_z.clicked.connect(_lock_axis('z'))
        ax_clr.clicked.connect(_lock_axis(None))
        for b in (ax_x, ax_y, ax_z, ax_clr): ha.addWidget(b)
        fg.addRow("Axis", row_axes)
        # Space toggle
        cb_space = QCheckBox("Local Space"); cb_space.setChecked(True)
        def _space_toggle(_v): self._space_local = cb_space.isChecked()
        cb_space.stateChanged.connect(_space_toggle)
        fg.addRow("Space", cb_space)
        # Snap controls
        spin_ang = QDoubleSpinBox(); spin_ang.setRange(0.5,45.0); spin_ang.setSingleStep(0.5); spin_ang.setValue(self._snap_angle_deg); spin_ang.setSuffix(" Ã‚Â°")
        spin_scl = QDoubleSpinBox(); spin_scl.setRange(0.01,10.0); spin_scl.setDecimals(3); spin_scl.setSingleStep(0.05); spin_scl.setValue(self._snap_scale_step)
        def _upd_ang(_v): self._snap_angle_deg = float(spin_ang.value())
        def _upd_scl(_v): self._snap_scale_step = float(spin_scl.value())
        spin_ang.valueChanged.connect(_upd_ang)
        spin_scl.valueChanged.connect(_upd_scl)
        fg.addRow("Angle Snap", spin_ang)
        fg.addRow("Scale Snap", spin_scl)
        side.addWidget(gb_gizmo)
        self._register_section("gizmo", "Gizmo", gb_gizmo)
        
        # --- Sketch (2D) overlay ---
        gb_sk = QGroupBox("Sketch (2D)"); fs = QFormLayout(); gb_sk.setLayout(fs)
        cb_sketch = QCheckBox("Enable Sketch Overlay"); cb_sketch.setChecked(False)
        def _toggle_sk(_):
            self._sketch_on = cb_sketch.isChecked()
            if not self._sketch_on:  # disable & clean up
                self._sketch_mode = None
                self._sketch.active_poly = None
            else:
                if getattr(self, '_sketch_lock_top', False):
                    try:
                        self.view.yaw = 0.0; self.view.pitch = 0.0
                        self.view._update_camera()
                    except Exception:
                        self.view.update()
                else:
                    self.view.update()
        cb_sketch.stateChanged.connect(_toggle_sk)
        # store for programmatic toggling
        self._cb_sketch = cb_sketch
        fs.addRow(cb_sketch)
        # Lock top view while sketching
        row_lock = QWidget(); hlk = QHBoxLayout(row_lock); hlk.setContentsMargins(0,0,0,0)
        cb_lock_top = QCheckBox("Lock Top View (XY)"); cb_lock_top.setChecked(True)
        def _apply_lock_top(_):
            self._sketch_lock_top = cb_lock_top.isChecked()
            if self._sketch_on and self._sketch_lock_top:
                # force yaw/pitch to top view and refresh
                try:
                    self.view.yaw = 0.0; self.view.pitch = 0.0
                    self.view._update_camera()
                except Exception:
                    pass
            else:
                self.view.update()
        cb_lock_top.stateChanged.connect(_apply_lock_top)
        hlk.addWidget(cb_lock_top)
        fs.addRow("View Lock", row_lock)
        # Grid & Snap
        self._sketch_grid_on = False
        self._sketch_snap_grid = False
        self._sketch_grid_step = 10.0
        # If True: interpret grid_step as pixel spacing (screen-locked); if False: world units
        self._sketch_grid_screen_lock = True
        row_grid = QWidget(); hg = QHBoxLayout(row_grid); hg.setContentsMargins(0,0,0,0)
        cb_grid = QCheckBox("Show Grid"); cb_grid.stateChanged.connect(lambda _v: setattr(self, '_sketch_grid_on', cb_grid.isChecked()) or self.view.update())
        cb_snapg= QCheckBox("Snap Grid"); cb_snapg.stateChanged.connect(lambda _v: setattr(self, '_sketch_snap_grid', cb_snapg.isChecked()))
        # Toggle: screen-lock (pixels) vs world units
        cb_lock = QCheckBox("Screen-locked spacing"); cb_lock.setChecked(self._sketch_grid_screen_lock)
        cb_lock.stateChanged.connect(lambda _v: setattr(self, '_sketch_grid_screen_lock', cb_lock.isChecked()) or self.view.update())
        sp_grid = QDoubleSpinBox(); sp_grid.setRange(0.1, 1000.0); sp_grid.setDecimals(2); sp_grid.setSingleStep(0.5); sp_grid.setValue(self._sketch_grid_step)
        sp_grid.valueChanged.connect(lambda v: setattr(self, '_sketch_grid_step', float(v)))
        hg.addWidget(cb_grid); hg.addWidget(cb_snapg); hg.addWidget(cb_lock); hg.addWidget(QLabel("Step")); hg.addWidget(sp_grid)
        fs.addRow("Grid/Snap", row_grid)
        # Kernel Sync (optional)
        row_sync = QWidget(); hsync = QHBoxLayout(row_sync); hsync.setContentsMargins(0,0,0,0)
        self._sketch_circle_to_ring = False
        cb_circle_sync = QCheckBox("Circle â†’ Ring (kernel)")
        cb_circle_sync.setToolTip("When enabled, finalizing a sketch circle adds a thin torus at the same center/radius in the AACore scene.")
        cb_circle_sync.stateChanged.connect(lambda _v: setattr(self, '_sketch_circle_to_ring', cb_circle_sync.isChecked()))
        hsync.addWidget(cb_circle_sync)
        fs.addRow("Sync", row_sync)
        row_tools = QWidget(); ht = QHBoxLayout(row_tools); ht.setContentsMargins(0,0,0,0)
        btn_poly = QPushButton("Polyline"); btn_poly.setCheckable(True)
        btn_line = QPushButton("Line"); btn_line.setCheckable(True)
        btn_arc3 = QPushButton("Arc (3-pt)"); btn_arc3.setCheckable(True)
        btn_circle = QPushButton("Circle"); btn_circle.setCheckable(True)
        btn_rect = QPushButton("Rectangle"); btn_rect.setCheckable(True)
        btn_insv = QPushButton("Insert Vertex"); btn_insv.setCheckable(True)
        self._btn_sketch_poly = btn_poly
        self._btn_sketch_line = btn_line
        self._btn_sketch_arc3 = btn_arc3
        self._btn_sketch_circle = btn_circle
        self._btn_sketch_rect = btn_rect
        self._btn_sketch_insert = btn_insv
        def _choose_poly():
            on = btn_poly.isChecked()
            if on:
                for b2 in (btn_line, btn_arc3, btn_circle, btn_rect): b2.setChecked(False)
                self._sketch_mode = 'polyline'
                self._sketch.active_shape = None
                if getattr(self, '_sketch_lock_top', False):
                    try: self.view.yaw=0.0; self.view.pitch=0.0; self.view._update_camera()
                    except Exception: pass
            else:
                if self._sketch_mode=='polyline':
                    self._sketch_mode = None
            self.view.update()
        btn_poly.clicked.connect(_choose_poly)
        def _choose_line():
            on = btn_line.isChecked()
            if on:
                for b2 in (btn_poly, btn_arc3, btn_circle, btn_rect): b2.setChecked(False)
                self._sketch_mode = 'line'
                self._sketch.active_poly = None
                self._sketch.active_shape = None
                if getattr(self, '_sketch_lock_top', False):
                    try: self.view.yaw=0.0; self.view.pitch=0.0; self.view._update_camera()
                    except Exception: pass
            else:
                if self._sketch_mode=='line': self._sketch_mode = None
            self.view.update()
        btn_line.clicked.connect(_choose_line)
        def _choose_arc3():
            on = btn_arc3.isChecked()
            if on:
                for b2 in (btn_poly, btn_line, btn_circle, btn_rect): b2.setChecked(False)
                self._sketch_mode = 'arc3'
                self._sketch.active_poly = None
                self._sketch.active_shape = None
                if getattr(self, '_sketch_lock_top', False):
                    try: self.view.yaw=0.0; self.view.pitch=0.0; self.view._update_camera()
                    except Exception: pass
            else:
                if self._sketch_mode=='arc3': self._sketch_mode = None
            self.view.update()
        btn_arc3.clicked.connect(_choose_arc3)
        def _choose_circle():
            on = btn_circle.isChecked()
            if on:
                for b2 in (btn_poly, btn_line, btn_arc3, btn_rect): b2.setChecked(False)
                self._sketch_mode = 'circle'
                self._sketch.active_poly = None
                self._sketch.active_shape = None
                if getattr(self, '_sketch_lock_top', False):
                    try: self.view.yaw=0.0; self.view.pitch=0.0; self.view._update_camera()
                    except Exception: pass
            else:
                if self._sketch_mode=='circle': self._sketch_mode = None
            self.view.update()
        btn_circle.clicked.connect(_choose_circle)
        def _choose_rect():
            on = btn_rect.isChecked()
            if on:
                for b2 in (btn_poly, btn_line, btn_arc3, btn_circle): b2.setChecked(False)
                self._sketch_mode = 'rect'
                self._sketch.active_poly = None
                self._sketch.active_shape = None
                if getattr(self, '_sketch_lock_top', False):
                    try: self.view.yaw=0.0; self.view.pitch=0.0; self.view._update_camera()
                    except Exception: pass
            else:
                if self._sketch_mode=='rect': self._sketch_mode = None
            self.view.update()
        btn_rect.clicked.connect(_choose_rect)
        # Insert Vertex / Midpoint option
        self._insert_midpoint = False
        cb_ins_mid = QCheckBox("Midpoint")
        cb_ins_mid.stateChanged.connect(lambda _v: setattr(self, '_insert_midpoint', cb_ins_mid.isChecked()))
        self._chk_sketch_midpoint = cb_ins_mid
        def _choose_insv():
            on = btn_insv.isChecked()
            if on:
                for b2 in (btn_poly, btn_line, btn_arc3, btn_circle, btn_rect): b2.setChecked(False)
                self._sketch_mode = 'insert_vertex'
                self._sketch._dim_pick = None
            else:
                if self._sketch_mode=='insert_vertex': self._sketch_mode = None
            self.view.update()
        btn_insv.clicked.connect(_choose_insv)
        # Dimension tool
        btn_dim = QPushButton("Dimension"); btn_dim.setCheckable(True)
        self._btn_sketch_dim = btn_dim
        def _choose_dim():
            on = btn_dim.isChecked()
            if on:
                for b2 in (btn_poly, btn_line, btn_arc3, btn_circle, btn_rect): b2.setChecked(False)
                self._sketch_mode = 'dimension'
                self._sketch._dim_pick = None
            else:
                if self._sketch_mode=='dimension':
                    self._sketch_mode = None
                    # reset any in-progress placing state
                    try:
                        self._sketch._dim_placing = False; self._sketch._dim_place_data = None; self._sketch._dim_preview = None
                    except Exception:
                        pass
            self.view.update()
        btn_dim.clicked.connect(_choose_dim)
        for b in (btn_poly, btn_line, btn_arc3, btn_circle, btn_rect, btn_insv, btn_dim, cb_ins_mid):
            ht.addWidget(b)
        fs.addRow("Tool", row_tools)
        # Dimension settings (type + precision)
        row_dim = QWidget(); hdim = QHBoxLayout(row_dim); hdim.setContentsMargins(0,0,0,0)
        from PySide6.QtWidgets import QComboBox as _QCB
        self._dim_type = 'linear'
        cb_dim_type = _QCB(); cb_dim_type.addItems(["Linear","Horizontal","Vertical","Radius","Diameter"])
        def _set_dim_type(idx):
            self._dim_type = [ 'linear','horizontal','vertical','radius','diameter' ][max(0,min(4,idx))]
        cb_dim_type.currentIndexChanged.connect(_set_dim_type)
        self._dim_precision = 2
        sp_dim_prec = QSpinBox(); sp_dim_prec.setRange(0,6); sp_dim_prec.setValue(self._dim_precision)
        sp_dim_prec.valueChanged.connect(lambda v: setattr(self, '_dim_precision', int(v)))
        hdim.addWidget(QLabel("Type")); hdim.addWidget(cb_dim_type)
        hdim.addWidget(QLabel("Precision")); hdim.addWidget(sp_dim_prec)
        fs.addRow("Dimensions", row_dim)
        # Selection info label
        self._sketch_info_label = QLabel("No selection")
        fs.addRow("Selection", self._sketch_info_label)
        # Save/Load Sketch JSON
        row_io = QWidget(); hio = QHBoxLayout(row_io); hio.setContentsMargins(0,0,0,0)
        btn_save_sk = QPushButton("Save Sketch JSON")
        btn_load_sk = QPushButton("Load Sketch JSON")
        btn_save_sk.clicked.connect(self._save_sketch_json)
        btn_load_sk.clicked.connect(self._load_sketch_json)
        # Clear button
        btn_clear_sk = QPushButton("Clear Sketch")
        def _clear_sk():
            self._sketch.entities.clear(); self._sketch.active_poly=None; self._sketch.active_shape=None
            self.view._sk_point_sel=None; self.view._sk_dragging=False
            self._update_sketch_info(None)
            self.view.update()
        btn_clear_sk.clicked.connect(_clear_sk)
        hio.addWidget(btn_save_sk); hio.addWidget(btn_load_sk)
        hio.addWidget(btn_clear_sk)
        fs.addRow("IO", row_io)
        side.addWidget(gb_sk)
        self._register_section("sketch", "Sketch", gb_sk)
        # Backing model
        self._sketch_doc = SketchDocument(units=Units.MM)
        
        # --- Actions ---
        gb_act = QGroupBox("Actions"); va = QVBoxLayout(); gb_act.setLayout(va)
        btn_save = QPushButton("Save G-Buffers [G]"); btn_save.setEnabled(False)
        btn_help = QPushButton("Print Shortcuts [H]"); btn_help.clicked.connect(lambda: log.info(self.view._shortcuts_help()))
        btn_showcase = QPushButton("Showcase Primitives")
        btn_clear_scene = QPushButton("Clear Scene")
        def _do_showcase():
            try:
                # Add a small curated set if budget allows
                if len(self.view.scene.prims) < MAX_PRIMS - 6:
                    self.view.scene.add(Prim(KIND_SPHERE, [0.7,0,0,0], beta=0.08, color=(0.95,0.45,0.35)))
                    self.view.scene.add(Prim(KIND_TORUS, [1.0,0.22,0,0], beta=0.03, color=(0.6,0.85,0.5)))
                    self.view.scene.add(Prim(KIND_MOBIUS, [1.4,0.25,0,0], beta=0.02, color=(0.7,0.55,0.95)))
                    self.view.scene.add(Prim(KIND_SUPERELLIPSOID, [1.1,3.5,0,0], beta=0.0, color=(0.95,0.9,0.85)))
                    self.view.scene.add(Prim(KIND_GYROID, [2.2,0.0,0.035,0], beta=0.0, color=(0.65,0.9,0.3)))
                    self.view.scene.add(Prim(KIND_TREFOIL, [0.8,0.08,96,0], beta=0.0, color=(0.95,0.6,0.25)))
                    # Offset for variety
                    try:
                        for i, pr in enumerate(self.view.scene.prims[-6:]):
                            pr.xform.M[:3,3] += np.array([ (i%3-1)*1.6, (i//3-0.5)*1.4, 0.0 ], np.float32)
                    except Exception:
                        pass
                    try: self.view.scene._notify()
                    except Exception: pass
                    self.view.update()
            except Exception as e:
                log.debug(f"showcase failed: {e}")
        def _do_clear_scene():
            try:
                self.view.scene.prims.clear()
                try: self.view.scene._notify()
                except Exception: pass
                try: self.view.clear_polyline_overlays()
                except Exception: pass
                self._refresh_prim_label(); self.view.update()
            except Exception:
                pass
        btn_showcase.clicked.connect(_do_showcase)
        btn_clear_scene.clicked.connect(_do_clear_scene)
        # keep references so the wheel can trigger them
        self._btn_showcase = btn_showcase
        self._btn_clear_scene = btn_clear_scene
        va.addWidget(btn_save); va.addWidget(btn_help); va.addWidget(btn_showcase); va.addWidget(btn_clear_scene); side.addWidget(gb_act)
        self._register_section("actions", "Actions", gb_act)
        
        # --- Environment ---
        gb_env = QGroupBox("Environment"); fe = QFormLayout(); gb_env.setLayout(fe)
        self._bg_sliders = []
        for i, ch in enumerate(['R','G','B']):
            s = QSlider(Qt.Orientation.Horizontal); s.setRange(0,255); s.setValue(int(self.view.scene.bg_color[i]*255)); s.valueChanged.connect(self._on_bg_changed)
            fe.addRow(f"BG {ch}", s); self._bg_sliders.append(s)
        self._env_sliders = []
        for i, ch in enumerate(['X','Y','Z']):
            s = QSlider(Qt.Orientation.Horizontal); s.setRange(-150,150); s.setValue(int(self.view.scene.env_light[i]*100)); s.valueChanged.connect(self._on_env_changed)
            fe.addRow(f"Light {ch}", s); self._env_sliders.append(s)
        side.addWidget(gb_env)
        self._register_section("environment", "Environment", gb_env)
        
        # --- Primitives + Editing ---
        gb_prims = QGroupBox("Primitives"); vp = QVBoxLayout(); gb_prims.setLayout(vp)
        self._prim_list_label = QLabel("(0)")
        self._prim_buttons_box = QVBoxLayout()
        btn_add_sphere = QPushButton("Add Sphere"); btn_add_sphere.clicked.connect(lambda: self._add_prim('sphere'))
        btn_add_box = QPushButton("Add Box"); btn_add_box.clicked.connect(lambda: self._add_prim('box'))
        btn_add_capsule = QPushButton("Add Capsule"); btn_add_capsule.clicked.connect(lambda: self._add_prim('capsule'))
        btn_add_torus = QPushButton("Add Torus"); btn_add_torus.clicked.connect(lambda: self._add_prim('torus'))
        btn_add_mobius = QPushButton("Add Mobius"); btn_add_mobius.clicked.connect(lambda: self._add_prim('mobius'))
        btn_add_superell = QPushButton("Add Superellipsoid"); btn_add_superell.clicked.connect(lambda: self._add_prim('superellipsoid'))
        btn_add_qc = QPushButton("Add QuasiCrystal"); btn_add_qc.clicked.connect(lambda: self._add_prim('quasicrystal'))
        btn_add_torus4d = QPushButton("Add 4D Torus"); btn_add_torus4d.clicked.connect(lambda: self._add_prim('torus4d'))
        btn_add_mandelbulb = QPushButton("Add Mandelbulb"); btn_add_mandelbulb.clicked.connect(lambda: self._add_prim('mandelbulb'))
        btn_add_klein = QPushButton("Add Klein Bottle"); btn_add_klein.clicked.connect(lambda: self._add_prim('klein'))
        btn_add_menger = QPushButton("Add Menger Sponge"); btn_add_menger.clicked.connect(lambda: self._add_prim('menger'))
        btn_add_hyperbolic = QPushButton("Add Hyperbolic Tiling"); btn_add_hyperbolic.clicked.connect(lambda: self._add_prim('hyperbolic'))
        btn_add_gyroid = QPushButton("Add Gyroid"); btn_add_gyroid.clicked.connect(lambda: self._add_prim('gyroid'))
        btn_add_trefoil = QPushButton("Add Trefoil Knot"); btn_add_trefoil.clicked.connect(lambda: self._add_prim('trefoil'))
        btn_del_last = QPushButton("Delete Last"); btn_del_last.clicked.connect(self._del_last)
        btn_dup_sel = QPushButton("Duplicate Selected"); btn_dup_sel.clicked.connect(self._duplicate_selected)
        btn_center_sel = QPushButton("Center On Selected"); btn_center_sel.clicked.connect(self._center_on_selected)
        btn_reset_cam = QPushButton("Reset Camera"); btn_reset_cam.clicked.connect(self._reset_camera)
        btn_export = QPushButton("Export Scene JSON"); btn_export.clicked.connect(self._export_scene_json)
        for b in (self._prim_list_label, btn_add_sphere, btn_add_box, btn_add_capsule, btn_add_torus, btn_add_mobius, btn_add_superell, btn_add_qc, btn_add_torus4d, btn_add_mandelbulb, btn_add_klein, btn_add_menger, btn_add_hyperbolic, btn_add_gyroid, btn_add_trefoil, btn_del_last):
            vp.addWidget(b)
        for b in (btn_dup_sel, btn_center_sel, btn_reset_cam, btn_export):
            vp.addWidget(b)
        vb_holder = QWidget(); vb_holder.setLayout(self._prim_buttons_box); vp.addWidget(vb_holder)
        # Edit group
        self._edit_group = QGroupBox("Edit Selected"); fe2 = QFormLayout(); self._edit_group.setLayout(fe2)
        from PySide6.QtWidgets import QComboBox as _QCB2, QColorDialog
        def dspin(r=(-10,10), step=0.01, val=0.0):
            sp = QDoubleSpinBox(); sp.setRange(r[0], r[1]); sp.setSingleStep(step); sp.setDecimals(4); sp.setValue(val); return sp
        self._sp_pos = [dspin() for _ in range(3)]
        self._sp_param = [dspin((0,10),0.01,0.5) for _ in range(2)]
        self._sp_beta = dspin((-1,1),0.01,0.0)
        self._btn_color = QPushButton("Color...")
        self._op_box = _QCB2(); self._op_box.addItems(["solid","subtract"])
        fe2.addRow("Pos X/Y/Z", self._make_row(self._sp_pos))
        fe2.addRow("Param A/B", self._make_row(self._sp_param))
        fe2.addRow("Beta", self._sp_beta)
        fe2.addRow("Color", self._btn_color)
        fe2.addRow("Op", self._op_box)
        # Rotation & Scale controls
        def rspin():
            s = QDoubleSpinBox(); s.setRange(-180.0,180.0); s.setSingleStep(1.0); s.setDecimals(2); s.setValue(0.0); return s
        def sspin():
            s = QDoubleSpinBox(); s.setRange(0.01,100.0); s.setSingleStep(0.05); s.setDecimals(3); s.setValue(1.0); return s
        self._sp_rot = [rspin() for _ in range(3)]
        self._sp_scl = [sspin() for _ in range(3)]
        # Uniform scale control: sets X/Y/Z together
        self._sp_scl_u = sspin()
        # Move (translate) controls
        def mspin():
            s = QDoubleSpinBox(); s.setRange(-1000.0,1000.0); s.setSingleStep(0.01); s.setDecimals(4); s.setValue(0.0); return s
        self._sp_move = [mspin() for _ in range(3)]
        fe2.addRow("Rot deg X/Y/Z", self._make_row(self._sp_rot))
        fe2.addRow("Scale X/Y/Z", self._make_row(self._sp_scl))
        def _set_uniform_scale(v: float):
            try:
                for sp in self._sp_scl:
                    sp.blockSignals(True)
                    sp.setValue(float(v))
                    sp.blockSignals(False)
                # Apply after setting all axes
                self._apply_edit()
            except Exception:
                pass
        self._sp_scl_u.valueChanged.connect(_set_uniform_scale)
        fe2.addRow("Scale (Uniform)", self._sp_scl_u)
        fe2.addRow("Move X/Y/Z", self._make_row(self._sp_move))
        self._nudge_step = QDoubleSpinBox(); self._nudge_step.setRange(0.001,100.0); self._nudge_step.setDecimals(3); self._nudge_step.setSingleStep(0.1); self._nudge_step.setValue(1.0)
        fe2.addRow("Nudge Step", self._nudge_step)
        # Preview button for selected primitive (CPU low-res raymarch)
        btn_preview = QPushButton("Preview Primitive")
        btn_preview.setToolTip("Generate a quick low-resolution CPU preview of the selected primitive (useful when shaders unavailable)")
        btn_preview.clicked.connect(lambda checked=False, p=self: preview_primitive(p))
        fe2.addRow(btn_preview)
        self._edit_group.setEnabled(False); vp.addWidget(self._edit_group)
        for sp in self._sp_pos: sp.valueChanged.connect(self._apply_edit)
        for sp in self._sp_param: sp.valueChanged.connect(self._apply_edit)
        self._sp_beta.valueChanged.connect(self._apply_edit); self._op_box.currentIndexChanged.connect(self._apply_edit)
        for s in self._sp_rot + self._sp_scl + self._sp_move:
            s.valueChanged.connect(self._apply_edit)
        def pick_color():
            from PySide6.QtGui import QColor
            c = QColorDialog.getColor(QColor(200,180,160), self, "Primitive Color")
            if c.isValid():
                self._current_color = (c.red()/255.0, c.green()/255.0, c.blue()/255.0)
                self._apply_edit()
        self._btn_color.clicked.connect(pick_color)
        self._current_sel = -1; self._current_color = (0.8,0.7,0.6)
        side.addWidget(gb_prims)
        self._register_section("primitives", "Primitives", gb_prims)

        # --- Fractal Color Fields ---
        gb_fractal = QGroupBox("Fractal Color Fields"); ff = QFormLayout(); gb_fractal.setLayout(ff)
        self._fractal_mode_box = QComboBox(); self._fractal_mode_box.addItems(["Smooth Escape", "Orbit Trap", "Angular/Phase"])
        self._fractal_mode_box.setCurrentIndex(int(self.view.fractal_color_mode))
        self._fractal_mode_box.currentIndexChanged.connect(self._on_fractal_mode_changed)

        self._fractal_shell_spin = QDoubleSpinBox(); self._fractal_shell_spin.setRange(0.0, 4.0); self._fractal_shell_spin.setDecimals(3); self._fractal_shell_spin.setSingleStep(0.05); self._fractal_shell_spin.setValue(float(self.view.fractal_orbit_shell))
        self._fractal_shell_spin.valueChanged.connect(self._on_fractal_shell_changed)

        self._fractal_ni_spin = QDoubleSpinBox(); self._fractal_ni_spin.setRange(0.01, 0.5); self._fractal_ni_spin.setDecimals(3); self._fractal_ni_spin.setSingleStep(0.01); self._fractal_ni_spin.setValue(float(self.view.fractal_ni_scale))
        self._fractal_ni_spin.valueChanged.connect(self._on_fractal_ni_changed)

        ff.addRow("Color Mode", self._fractal_mode_box)
        ff.addRow("Orbit Shell R", self._fractal_shell_spin)
        ff.addRow("NI Palette Scale", self._fractal_ni_spin)
        side.addWidget(gb_fractal)
        self._register_section("fractal_color", "Fractal Color", gb_fractal)
        self._sync_fractal_controls()

        # --- Mandelbulb Mesh Export ---
        gb_mb = QGroupBox("Mandelbulb Mesh Export"); fb_mb = QFormLayout(); gb_mb.setLayout(fb_mb)
        self._mb_res_spin = QSpinBox(); self._mb_res_spin.setRange(32, 512); self._mb_res_spin.setSingleStep(16); self._mb_res_spin.setValue(256)
        self._mb_extent_spin = QDoubleSpinBox(); self._mb_extent_spin.setRange(0.2, 4.0); self._mb_extent_spin.setDecimals(3); self._mb_extent_spin.setSingleStep(0.1); self._mb_extent_spin.setValue(1.6)
        self._mb_power_spin = QDoubleSpinBox(); self._mb_power_spin.setRange(2.0, 16.0); self._mb_power_spin.setDecimals(2); self._mb_power_spin.setSingleStep(0.1); self._mb_power_spin.setValue(8.0)
        self._mb_bailout_spin = QDoubleSpinBox(); self._mb_bailout_spin.setRange(2.0, 32.0); self._mb_bailout_spin.setDecimals(2); self._mb_bailout_spin.setSingleStep(0.1); self._mb_bailout_spin.setValue(8.0)
        self._mb_iter_spin = QSpinBox(); self._mb_iter_spin.setRange(4, 96); self._mb_iter_spin.setSingleStep(2); self._mb_iter_spin.setValue(14)
        self._mb_scale_spin = QDoubleSpinBox(); self._mb_scale_spin.setRange(0.1, 4.0); self._mb_scale_spin.setDecimals(3); self._mb_scale_spin.setSingleStep(0.05); self._mb_scale_spin.setValue(1.0)
        self._mb_color_box = QComboBox(); self._mb_color_box.addItems(["Smooth Escape", "Orbit Trap", "Angular/Phase"]); self._mb_color_box.setCurrentIndex(int(self.view.fractal_color_mode))
        self._mb_color_box.currentIndexChanged.connect(self._on_mandelbulb_export_color_mode_changed)
        self._mb_pi_mode_box = QComboBox(); self._mb_pi_mode_box.addItems(["Fixed π", "Adaptive πₐ"])
        self._mb_pi_base_spin = QDoubleSpinBox(); self._mb_pi_base_spin.setRange(2.5, 3.5); self._mb_pi_base_spin.setDecimals(8); self._mb_pi_base_spin.setSingleStep(0.0001); self._mb_pi_base_spin.setValue(float(np.pi))
        self._mb_pi_alpha_spin = QDoubleSpinBox(); self._mb_pi_alpha_spin.setRange(0.0, 1.0); self._mb_pi_alpha_spin.setDecimals(3); self._mb_pi_alpha_spin.setSingleStep(0.01); self._mb_pi_alpha_spin.setValue(0.0)
        self._mb_pi_mu_spin = QDoubleSpinBox(); self._mb_pi_mu_spin.setRange(0.0, 1.0); self._mb_pi_mu_spin.setDecimals(3); self._mb_pi_mu_spin.setSingleStep(0.01); self._mb_pi_mu_spin.setValue(0.05)

        # Adaptive norm controls
        self._mb_norm_mode_box = QComboBox(); self._mb_norm_mode_box.addItems(["Euclidean", "Adaptive Norm"])
        self._mb_norm_k_spin = QDoubleSpinBox(); self._mb_norm_k_spin.setRange(0.0, 1.0); self._mb_norm_k_spin.setDecimals(3); self._mb_norm_k_spin.setSingleStep(0.01); self._mb_norm_k_spin.setValue(0.12)
        self._mb_norm_r0_spin = QDoubleSpinBox(); self._mb_norm_r0_spin.setRange(0.1, 2.0); self._mb_norm_r0_spin.setDecimals(3); self._mb_norm_r0_spin.setSingleStep(0.05); self._mb_norm_r0_spin.setValue(0.9)
        self._mb_norm_sigma_spin = QDoubleSpinBox(); self._mb_norm_sigma_spin.setRange(0.01, 1.0); self._mb_norm_sigma_spin.setDecimals(3); self._mb_norm_sigma_spin.setSingleStep(0.01); self._mb_norm_sigma_spin.setValue(0.35)
        self._mb_step_scale_spin = QDoubleSpinBox(); self._mb_step_scale_spin.setRange(0.1, 2.0); self._mb_step_scale_spin.setDecimals(2); self._mb_step_scale_spin.setSingleStep(0.05); self._mb_step_scale_spin.setValue(1.0)
        self._mb_step_scale_spin.setToolTip("Safety factor for ray marching. Use 0.8 with adaptive norm.")
        
        # Connect adaptive norm mode to auto-adjust step scale
        self._mb_norm_mode_box.currentIndexChanged.connect(self._on_norm_mode_changed)

        fb_mb.addRow("Resolution", self._mb_res_spin)
        fb_mb.addRow("Bounds ±", self._mb_extent_spin)
        fb_mb.addRow("Power", self._mb_power_spin)
        fb_mb.addRow("Bailout", self._mb_bailout_spin)
        fb_mb.addRow("Max Iter", self._mb_iter_spin)
        fb_mb.addRow("Internal Scale", self._mb_scale_spin)
        fb_mb.addRow("Color Mode", self._mb_color_box)
        fb_mb.addRow("π Mode", self._mb_pi_mode_box)
        fb_mb.addRow("π Base", self._mb_pi_base_spin)
        fb_mb.addRow("π α", self._mb_pi_alpha_spin)
        fb_mb.addRow("π μ", self._mb_pi_mu_spin)
        
        # Adaptive norm controls
        fb_mb.addRow("Norm Mode", self._mb_norm_mode_box)
        fb_mb.addRow("Norm k", self._mb_norm_k_spin)
        fb_mb.addRow("Norm r₀", self._mb_norm_r0_spin)
        fb_mb.addRow("Norm σ", self._mb_norm_sigma_spin)
        fb_mb.addRow("Step Scale", self._mb_step_scale_spin)

        self._mb_use_gpu_chk = QCheckBox("Use GPU (CuPy)")
        have_cupy = _cupy_available()
        self._mb_use_gpu_chk.setChecked(have_cupy)
        self._mb_use_gpu_chk.setEnabled(True)
        if not have_cupy:
            reason = _CUPY_INIT_ERROR or "Install CuPy (or ensure CUDA is available) to enable GPU sampling."
            self._mb_use_gpu_chk.setToolTip(str(reason))
        else:
            self._mb_use_gpu_chk.setToolTip("Run field sampling on the GPU via CuPy when exporting.")
        fb_mb.addRow("Acceleration", self._mb_use_gpu_chk)

        self._mb_colors_chk = QCheckBox("Bake Vertex Colors")
        self._mb_colors_chk.setChecked(True)
        self._mb_colors_chk.setToolTip("When disabled, skip per-vertex fractal colors to speed up exports.")
        fb_mb.addRow("Vertex Colors", self._mb_colors_chk)
        
        self._mb_gpu_colors_chk = QCheckBox("GPU Vertex Colors")
        self._mb_gpu_colors_chk.setChecked(have_cupy)
        self._mb_gpu_colors_chk.setEnabled(True)
        if not have_cupy:
            self._mb_gpu_colors_chk.setToolTip("Requires GPU acceleration. Install CuPy to enable.")
        else:
            self._mb_gpu_colors_chk.setToolTip("Use GPU RawKernel for fast vertex coloring with adaptive parameters.")
        fb_mb.addRow("GPU Colors", self._mb_gpu_colors_chk)

        self._mb_pull_btn = QPushButton("Use Selected Mandelbulb")
        self._mb_pull_btn.setEnabled(False)
        self._mb_pull_btn.clicked.connect(self._pull_mandelbulb_params_from_selection)
        self._mb_export_btn = QPushButton("Export STL & PLY…")
        self._mb_export_btn.setEnabled(False)
        self._mb_export_btn.clicked.connect(self._export_mandelbulb_mesh)
        fb_mb.addRow(self._make_row([self._mb_pull_btn, self._mb_export_btn]))

        self._mb_status_label = QLabel("Select a Mandelbulb primitive to export.")
        self._mb_status_label.setWordWrap(True)
        fb_mb.addRow(self._mb_status_label)

        self._mb_reload_btn = QPushButton("Add Last Export to Scene")
        self._mb_reload_btn.setEnabled(False)
        self._mb_reload_btn.clicked.connect(self._add_last_mandelbulb_export)
        self._mb_clear_overlay_btn = QPushButton("Clear Loaded Mesh")
        self._mb_clear_overlay_btn.setEnabled(False)
        self._mb_clear_overlay_btn.clicked.connect(self._clear_mandelbulb_overlay)
        fb_mb.addRow(self._make_row([self._mb_reload_btn, self._mb_clear_overlay_btn]))

        side.addWidget(gb_mb)
        self._register_section("mandelbulb_export", "Mandelbulb Export", gb_mb, default_visible=True)
        
        # --- Tesseract (4D hypercube) ---
        gb_tess = QGroupBox("Tesseract (4D Hypercube)"); ft = QFormLayout(); gb_tess.setLayout(ft)
        self._tess_edge = QDoubleSpinBox(); self._tess_edge.setRange(0.1, 10.0); self._tess_edge.setDecimals(3); self._tess_edge.setSingleStep(0.1); self._tess_edge.setValue(2.0)
        self._tess_edge_rad = QDoubleSpinBox(); self._tess_edge_rad.setRange(0.001, 1.0); self._tess_edge_rad.setDecimals(3); self._tess_edge_rad.setSingleStep(0.01); self._tess_edge_rad.setValue(0.03)
        self._tess_node_rad = QDoubleSpinBox(); self._tess_node_rad.setRange(0.001, 1.0); self._tess_node_rad.setDecimals(3); self._tess_node_rad.setSingleStep(0.01); self._tess_node_rad.setValue(0.04)
        self._tess_include_nodes = QCheckBox("Include Nodes (spheres)"); self._tess_include_nodes.setChecked(False)
        # Projection
        self._tess_proj = QComboBox(); self._tess_proj.addItems(["Orthographic","Perspective"])
        self._tess_fw = QDoubleSpinBox(); self._tess_fw.setRange(0.5, 10.0); self._tess_fw.setDecimals(2); self._tess_fw.setSingleStep(0.1); self._tess_fw.setValue(3.0)
        # 4D rotation angles
        def r4spin():
            s = QDoubleSpinBox(); s.setRange(-360.0, 360.0); s.setDecimals(2); s.setSingleStep(1.0); s.setValue(0.0); return s
        self._tess_ang_xy = r4spin(); self._tess_ang_xz = r4spin(); self._tess_ang_xw = r4spin();
        self._tess_ang_yz = r4spin(); self._tess_ang_yw = r4spin(); self._tess_ang_zw = r4spin();
        self._tess_autospin = QCheckBox("Auto-Spin"); self._tess_autospin.setChecked(True)
        self._tess_speed = QDoubleSpinBox(); self._tess_speed.setRange(0.0, 360.0); self._tess_speed.setDecimals(2); self._tess_speed.setSingleStep(5.0); self._tess_speed.setValue(30.0)
        btn_tess = QPushButton("Add Tesseract")
        btn_tess.clicked.connect(self._add_tesseract)
        # Layout
        ft.addRow("Edge Length", self._tess_edge)
        ft.addRow("Edge Radius", self._tess_edge_rad)
        ft.addRow("Node Radius", self._tess_node_rad)
        ft.addRow(self._tess_include_nodes)
        ft.addRow("Projection", self._tess_proj)
        ft.addRow("Focal (persp fw)", self._tess_fw)
        row_ang1 = self._make_row([QLabel("XY"), self._tess_ang_xy, QLabel("XZ"), self._tess_ang_xz, QLabel("XW"), self._tess_ang_xw])
        row_ang2 = self._make_row([QLabel("YZ"), self._tess_ang_yz, QLabel("YW"), self._tess_ang_yw, QLabel("ZW"), self._tess_ang_zw])
        ft.addRow("Angles 1", row_ang1)
        ft.addRow("Angles 2", row_ang2)
        row_spin = self._make_row([self._tess_autospin, QLabel("Speed (deg/s)"), self._tess_speed])
        ft.addRow("Spin", row_spin)
        ft.addRow(btn_tess)
        side.addWidget(gb_tess)
        self._register_section("tesseract", "Tesseract", gb_tess)
        
        # rigs & timer
        self._rigs = []
        self._rig_timer = QTimer(self); self._rig_timer.timeout.connect(self._update_rigs)
        self._rig_timer.start(33)
        
        # --- Pixel-to-Quantum Sphere ---
        gb_scale = QGroupBox("Pixel-to-Quantum Sphere"); fs = QFormLayout(); gb_scale.setLayout(fs)
        self._scale_pixels = QDoubleSpinBox(); self._scale_pixels.setRange(0.5, 10.0); self._scale_pixels.setDecimals(2); self._scale_pixels.setSingleStep(0.25); self._scale_pixels.setValue(2.5); self._scale_pixels.setSuffix(" px")
        self._scale_duration = QDoubleSpinBox(); self._scale_duration.setRange(2.0, 120.0); self._scale_duration.setDecimals(1); self._scale_duration.setSingleStep(0.5); self._scale_duration.setValue(12.0); self._scale_duration.setSuffix(" s")
        self._scale_fov = QDoubleSpinBox(); self._scale_fov.setRange(20.0, 120.0); self._scale_fov.setDecimals(1); self._scale_fov.setSingleStep(1.0); self._scale_fov.setValue(60.0); self._scale_fov.setSuffix(" deg")
        self._scale_status = QLabel("Press start to generate the scale-aware sphere."); self._scale_status.setWordWrap(True)
        btn_start_scale = QPushButton("Start Scale Journey"); btn_start_scale.clicked.connect(self._start_scale_sphere_journey)
        btn_clear_scale = QToolButton(); btn_clear_scale.setText("Reset"); btn_clear_scale.setToolTip("Pause the journey and tuck the sphere detail away."); btn_clear_scale.clicked.connect(self._stop_scale_sphere)
        row_scale_btns = self._make_row([btn_start_scale, btn_clear_scale])
        fs.addRow("Visibility (px)", self._scale_pixels)
        fs.addRow("Duration", self._scale_duration)
        fs.addRow("FOV", self._scale_fov)
        fs.addRow(row_scale_btns)
        fs.addRow(self._scale_status)
        side.addWidget(gb_scale)
        self._register_section("scale", "Scale Journey", gb_scale)

        
        # --- Molecules ---
        gb_mol = QGroupBox("Molecules"); fmol = QFormLayout(); gb_mol.setLayout(fmol)
        self._mol_atom_scale = QDoubleSpinBox(); self._mol_atom_scale.setRange(0.1, 5.0); self._mol_atom_scale.setSingleStep(0.1); self._mol_atom_scale.setValue(0.6)
        self._mol_bond_r = QDoubleSpinBox(); self._mol_bond_r.setRange(0.005, 1.0); self._mol_bond_r.setDecimals(3); self._mol_bond_r.setSingleStep(0.005); self._mol_bond_r.setValue(0.035)
        self._mol_bond_thresh = QDoubleSpinBox(); self._mol_bond_thresh.setRange(0.0, 1.0); self._mol_bond_thresh.setDecimals(3); self._mol_bond_thresh.setSingleStep(0.02); self._mol_bond_thresh.setValue(0.2)
        self._mol_autospin = QCheckBox("Auto-Spin"); self._mol_autospin.setChecked(True)
        self._mol_speed = QDoubleSpinBox(); self._mol_speed.setRange(0.0, 360.0); self._mol_speed.setDecimals(1); self._mol_speed.setSingleStep(5.0); self._mol_speed.setValue(25.0)
        btn_imp_xyz = QPushButton("Import XYZ...")
        btn_imp_xyz.clicked.connect(self._import_xyz_molecule)
        fmol.addRow("Atom Scale", self._mol_atom_scale)
        fmol.addRow("Bond Radius", self._mol_bond_r)
        fmol.addRow("Bond Thresh", self._mol_bond_thresh)
        row_spinmol = self._make_row([self._mol_autospin, QLabel("Speed"), self._mol_speed])
        fmol.addRow("Spin", row_spinmol)
        fmol.addRow(btn_imp_xyz)
        side.addWidget(gb_mol)
        self._register_section("molecules", "Molecules", gb_mol)
        
        # finalize
        side.addStretch(1)
        # Wrap the side widget in a scroll area so overflowing controls
        # become scrollable instead of going off-screen.



    def _setup_ai(self) -> None:
        import warnings

        def _quiet_disconnect(signal, slot) -> None:
            """Disconnect a Qt signal from a slot without noisy PySide6 RuntimeWarnings.

            PySide6 can emit RuntimeWarning (not an Exception) when disconnecting a
            not-currently-connected slot; this keeps logs clean.
            """
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore",
                        message=r".*Failed to disconnect.*",
                        category=RuntimeWarning,
                    )
                    signal.disconnect(slot)
            except Exception:
                pass

        if self._ai_model_label is not None:
            try:
                self._ai_model_label.setText(self._ai_model)
            except Exception:
                pass
        have_ai = bool(_HAVE_AI and CADActionBus is not None and chat_with_tools is not None)
        if not have_ai:
            if self._ai_transcript is not None:
                try:
                    self._ai_transcript.append("AI copilot unavailable. Install 'openai' and set OPENAI_API_KEY.")
                except Exception:
                    pass
            if self._ai_send_btn is not None:
                self._ai_send_btn.setEnabled(False)
            if self._ai_input is not None:
                self._ai_input.setEnabled(False)
                self._ai_input.setPlaceholderText("AI copilot unavailable (missing dependencies or API key).")
            if self._ai_tools_group is not None:
                self._ai_tools_group.setEnabled(False)
            return

        self._ai_bus = CADActionBus()
        self._ai_history = []
        if self._ai_transcript is not None:
            try:
                self._ai_transcript.clear()
                self._ai_transcript.append("<i>AI copilot ready.</i>")
            except Exception:
                pass
        if self._ai_send_btn is not None:
            _quiet_disconnect(self._ai_send_btn.clicked, self._ai_on_send)
            self._ai_send_btn.clicked.connect(self._ai_on_send)
            self._ai_send_btn.setEnabled(True)
        if self._ai_input is not None:
            _quiet_disconnect(self._ai_input.returnPressed, self._ai_on_send)
            self._ai_input.returnPressed.connect(self._ai_on_send)
            self._ai_input.setEnabled(True)

        self._ai_bus.on("select_tool", self._ai_select_tool)
        self._ai_bus.on("create_circle", self._ai_create_circle)
        self._ai_bus.on("create_pi_circle", self._ai_create_pi_circle)
        self._ai_bus.on("upgrade_profile_to_pi_a", self._ai_upgrade_profile_to_pi_a)
        self._ai_bus.on("create_line", self._ai_create_line)
        self._ai_bus.on("extrude", self._ai_extrude)

        self._tool_registry = None
        if ToolRegistry is not None:
            try:
                self._tool_registry = ToolRegistry(self._ai_bus)
            except Exception as exc:
                try:
                    log.debug(f"ToolRegistry init failed: {exc}")
                except Exception:
                    pass
                self._tool_registry = None

        if self._tool_registry is not None:
            if self._ai_tools_group is not None:
                self._ai_tools_group.setEnabled(True)
            if self._ai_tools_run_btn is not None:
                _quiet_disconnect(self._ai_tools_run_btn.clicked, self._ai_tools_run)
                self._ai_tools_run_btn.clicked.connect(self._ai_tools_run)
                self._ai_tools_run_btn.setEnabled(True)
            if self._ai_tools_delete_btn is not None:
                _quiet_disconnect(self._ai_tools_delete_btn.clicked, self._ai_tools_delete)
                self._ai_tools_delete_btn.clicked.connect(self._ai_tools_delete)
                self._ai_tools_delete_btn.setEnabled(True)
            if self._ai_tools_pin_chk is not None:
                _quiet_disconnect(self._ai_tools_pin_chk.toggled, self._ai_tools_pin)
                self._ai_tools_pin_chk.toggled.connect(self._ai_tools_pin)
                self._ai_tools_pin_chk.setEnabled(True)
            if self._ai_tools_list is not None:
                _quiet_disconnect(self._ai_tools_list.itemSelectionChanged, self._ai_tools_sync_pin)
                self._ai_tools_list.itemSelectionChanged.connect(self._ai_tools_sync_pin)
            try:
                self._tool_registry.changed.connect(self._on_tool_registry_changed)
            except Exception:
                pass
            self._on_tool_registry_changed()
        else:
            if self._ai_tools_group is not None:
                self._ai_tools_group.setEnabled(False)

        self._rebuild_wheel_tools()

    def _ai_append(self, who: str, text: str) -> None:
        if self._ai_transcript is None:
            return
        try:
            self._ai_transcript.append(f"<b>{who}:</b> {text}")
        except Exception:
            try:
                self._ai_transcript.append(f"{who}: {text}")
            except Exception:
                pass

    def _ai_on_send(self) -> None:
        if self._ai_input is None:
            return
        text = self._ai_input.text().strip()
        if not text:
            return
        self._ai_append("You", text)
        self._ai_history.append({"role": "user", "content": text})
        self._ai_input.clear()
        if self._ai_send_btn is not None:
            self._ai_send_btn.setEnabled(False)
        self._ai_input.setEnabled(False)
        worker = self._AIPromptWorker(
            text,
            tools=self._ai_available_tools,
            bus=self._ai_bus,
            model=self._ai_model,
            prior=self._ai_history,
            registry=self._tool_registry,
            parent=self,
        )
        worker.finished_text.connect(self._ai_on_response)
        self._ai_worker = worker
        worker.start()

    def _ai_on_response(self, text: str) -> None:
        self._ai_append("Copilot", text)
        self._ai_history.append({"role": "assistant", "content": text})
        if self._ai_worker is not None:
            try:
                self._ai_worker.deleteLater()
            except Exception:
                pass
            self._ai_worker = None
        if self._ai_send_btn is not None:
            self._ai_send_btn.setEnabled(True)
        if self._ai_input is not None:
            self._ai_input.setEnabled(True)
            self._ai_input.setFocus()

    def _ai_select_tool(self, tool_id: str) -> dict:
        button_map = {
            "polyline": self._btn_sketch_poly,
            "line": self._btn_sketch_line,
            "arc3": self._btn_sketch_arc3,
            "circle": self._btn_sketch_circle,
            "rect": self._btn_sketch_rect,
            "insert_vertex": self._btn_sketch_insert,
            "dimension": self._btn_sketch_dim,
        }
        for key, btn in button_map.items():
            if btn is None:
                continue
            try:
                btn.blockSignals(True)
                btn.setChecked(key == tool_id)
                btn.blockSignals(False)
            except Exception:
                pass
        try:
            self._on_wheel_tool(tool_id, tool_id)
        except Exception:
            pass
        return {"selected": tool_id}

    def _record_ai_profile(self, meta: dict | None) -> dict:
        if meta is None:
            self._ai_last_profile_meta = None
            return {}
        self._ai_last_profile_meta = meta
        pts = meta.get("points") if isinstance(meta, dict) else None
        count = len(pts) if isinstance(pts, list) else 0
        return {
            "metric": meta.get("metric") if isinstance(meta, dict) else None,
            "family": meta.get("family", "") if isinstance(meta, dict) else "",
            "points": count,
        }

    def _ai_create_circle(self, radius: float, cx: float | None = None, cy: float | None = None, segments: int = 256) -> dict:
        try:
            r = max(0.01, float(radius))
            cxv = float(cx) if cx is not None else 0.0
            cyv = float(cy) if cy is not None else 0.0
            segs = int(segments) if segments is not None else 256
            if segs < 16:
                segs = 16
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

        try:
            if pi_circle_points is not None:
                pts = pi_circle_points(r, cxv, cyv, segs)
            else:
                import math
                pts = [
                    (cxv + r * math.cos(2.0 * math.pi * i / segs),
                     cyv + r * math.sin(2.0 * math.pi * i / segs))
                    for i in range(segs)
                ]
        except Exception:
            pts = []
        overlay_pts = pts + [pts[0]] if pts else []
        if hasattr(self.view, "add_polyline_overlay") and overlay_pts:
            try:
                self.view.add_polyline_overlay(overlay_pts, color=(200, 220, 255), width=2)
            except Exception:
                pass
        meta = None
        if make_pi_circle_profile is not None:
            try:
                meta = make_pi_circle_profile(r, cxv, cyv, segs)
            except Exception:
                meta = None
        stats = self._record_ai_profile(meta)
        return {
            "ok": True,
            "profile": {
                "type": "circle_overlay",
                "radius": r,
                "center": [cxv, cyv],
                "metric": stats.get("metric"),
                "family": stats.get("family", ""),
                "points": stats.get("points", 0),
            },
        }

    def _ai_create_pi_circle(self, radius: float, cx: float | None = None, cy: float | None = None, segments: int = 256) -> dict:
        return self._ai_create_circle(radius=radius, cx=cx, cy=cy, segments=segments)

    def _ai_upgrade_profile_to_pi_a(self, profile_id: str | None = None) -> dict:
        if self._ai_last_profile_meta is None:
            return {"ok": False, "error": "no active profile"}
        meta = self._ai_last_profile_meta
        if upgrade_profile_meta_to_pia is not None:
            try:
                meta = upgrade_profile_meta_to_pia(meta)
            except Exception:
                pass
        stats = self._record_ai_profile(meta)
        return {"ok": True, "profile": stats}

    def _ai_create_line(self, x1: float, y1: float, x2: float, y2: float) -> dict:
        try:
            pts = [(float(x1), float(y1)), (float(x2), float(y2))]
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        if hasattr(self.view, "add_polyline_overlay"):
            try:
                self.view.add_polyline_overlay(pts, color=(255, 180, 90), width=3)
            except Exception:
                pass
        return {"ok": True, "line": {"start": [pts[0][0], pts[0][1]], "end": [pts[1][0], pts[1][1]]}}

    def _ai_extrude(self, distance: float, metric: str | None = None) -> dict:
        return {"ok": False, "error": "Extrude not supported in analytic panel"}

    def _ai_tools_selected_id(self) -> str | None:
        if self._ai_tools_list is None:
            return None
        item = self._ai_tools_list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _ai_tools_refresh(self) -> None:
        if self._ai_tools_list is None or self._tool_registry is None:
            return
        try:
            self._ai_tools_list.blockSignals(True)
        except Exception:
            pass
        self._ai_tools_list.clear()
        try:
            macros = sorted(self._tool_registry.list(), key=lambda m: m.name.lower())
        except Exception:
            macros = []
        for m in macros:
            item = QListWidgetItem(f"{m.name}  ({m.id})")
            item.setData(Qt.ItemDataRole.UserRole, m.id)
            self._ai_tools_list.addItem(item)
        try:
            self._ai_tools_list.blockSignals(False)
        except Exception:
            pass
        self._ai_tools_sync_pin()

    def _ai_tools_sync_pin(self) -> None:
        if self._ai_tools_pin_chk is None:
            return
        tid = self._ai_tools_selected_id()
        if tid is None or self._tool_registry is None:
            try:
                self._ai_tools_pin_chk.blockSignals(True)
            except Exception:
                pass
            self._ai_tools_pin_chk.setChecked(False)
            self._ai_tools_pin_chk.setEnabled(False)
            try:
                self._ai_tools_pin_chk.blockSignals(False)
            except Exception:
                pass
            return
        macro = self._tool_registry.get(tid)
        try:
            self._ai_tools_pin_chk.blockSignals(True)
        except Exception:
            pass
        self._ai_tools_pin_chk.setEnabled(True)
        self._ai_tools_pin_chk.setChecked(bool(macro and macro.ui.get("pinned")))
        try:
            self._ai_tools_pin_chk.blockSignals(False)
        except Exception:
            pass

    def _ai_tools_run(self) -> None:
        if self._tool_registry is None:
            return
        tid = self._ai_tools_selected_id()
        if not tid:
            return
        try:
            self._tool_registry.run(tid, parent_widget=self)
        except Exception as exc:
            try:
                log.debug(f"custom tool run failed: {exc}")
            except Exception:
                pass

    def _ai_tools_delete(self) -> None:
        if self._tool_registry is None:
            return
        tid = self._ai_tools_selected_id()
        if not tid:
            return
        try:
            from PySide6.QtWidgets import QMessageBox
        except Exception:
            QMessageBox = None  # type: ignore
        if QMessageBox is not None:
            res = QMessageBox.question(self, "Delete Tool", f"Delete custom tool '{tid}'?")
            if res != QMessageBox.Yes:
                return
        try:
            self._tool_registry.remove(tid)
        except Exception as exc:
            try:
                log.debug(f"custom tool delete failed: {exc}")
            except Exception:
                pass
        self._ai_tools_refresh()

    def _ai_tools_pin(self, checked: bool) -> None:
        if self._tool_registry is None:
            return
        tid = self._ai_tools_selected_id()
        if not tid:
            return
        try:
            self._tool_registry.set_pinned(tid, bool(checked))
        except Exception as exc:
            try:
                log.debug(f"custom tool pin failed: {exc}")
            except Exception:
                pass
        self._rebuild_wheel_tools()

    def _on_tool_registry_changed(self) -> None:
        self._ai_tools_refresh()
        self._rebuild_wheel_tools()

    def _rebuild_wheel_tools(self) -> None:
        if not _HAVE_WHEEL:
            return
        wheel = getattr(self, "_radial_wheel", None)
        if wheel is None:
            return

        base_specs = getattr(self, "_radial_wheel_base_tools", []) or []
        base = [spec.clone() if hasattr(spec, "clone") else ToolSpec(spec.label, spec.tool_id, list(getattr(spec, 'children', []))) for spec in base_specs]

        custom_group = next((spec for spec in base if spec.label == "Custom"), None)
        if custom_group is not None:
            custom_group.children.clear()

        if self._tool_registry is not None and ToolSpec is not None:
            try:
                pinned = self._tool_registry.pinned()
            except Exception:
                pinned = []
            if custom_group is None and pinned:
                custom_group = ToolSpec("Custom", children=[])
                base.append(custom_group)
            if custom_group is not None:
                for macro in pinned:
                    label = (macro.ui.get("icon_text") or macro.name)[:10]
                    custom_group.children.append(ToolSpec(label, f"custom:{macro.id}"))

        if custom_group is not None and not custom_group.children:
            base = [spec for spec in base if spec is not custom_group]

        try:
            wheel.set_tools(base)
        except Exception:
            pass

    def _run_custom_tool(self, tool_id: str) -> None:
        if self._tool_registry is None:
            return
        try:
            self._tool_registry.run(tool_id, parent_widget=self)
        except Exception as exc:
            try:
                log.debug(f"custom tool run failed: {exc}")
            except Exception:
                pass


    def _on_wheel_tool(self, tool_id: str, _label: str):
        try:
            if tool_id.startswith("custom:"):
                if self._tool_registry is not None:
                    self._run_custom_tool(tool_id.split(":", 1)[1])
                return
            if tool_id == 'file_new':
                if self._btn_clear_scene is not None:
                    self._btn_clear_scene.click()
                else:
                    try:
                        self._clear_scene()  # type: ignore[attr-defined]
                    except Exception:
                        pass
                return
            if tool_id == 'file_open':
                self._load_sketch_json()
                return
            if tool_id == 'file_save':
                self._save_sketch_json()
                return
            if tool_id.startswith('prim:'):
                self._add_prim(tool_id.split(':', 1)[1])
                return
            # Ensure sketch overlay is enabled for sketch tools
            def enable_sketch():
                if self._cb_sketch is not None and not self._cb_sketch.isChecked():
                    self._cb_sketch.setChecked(True)
                    # stateChanged handler will update view
            if tool_id in ("polyline","line","arc3","circle","rect","insert_vertex","dimension"):
                enable_sketch()
                self._sketch_mode = tool_id
                # reset active shape/poly for a clean start
                if tool_id == 'polyline':
                    self._sketch.active_shape = None
                    self._sketch.active_poly = None
                else:
                    self._sketch.active_poly = None
                    self._sketch.active_shape = None
                # lock to top if desired
                if getattr(self, '_sketch_lock_top', False):
                    try:
                        self.view.yaw = 0.0; self.view.pitch = 0.0
                        self.view._update_camera()
                    except Exception:
                        pass
                self.view.update()
                return
            # Gizmo modes
            if tool_id in ("move","rotate","scale"):
                self._gizmo_mode = tool_id
                self._move_drag_free = (tool_id == 'move')
                self.view.update(); return
            # Actions
            if tool_id == 'showcase' and self._btn_showcase is not None:
                self._btn_showcase.click(); return
            if tool_id == 'clear' and self._btn_clear_scene is not None:
                self._btn_clear_scene.click(); return
            if tool_id == 'center_selected':
                self._center_on_selected(); return
            if tool_id == 'reset_camera':
                self._reset_camera(); return
            if tool_id == 'delete_last':
                self._delete_last_sketch_item(); return
        except Exception as e:
            try:
                log.debug(f"wheel action failed: {e}")
            except Exception:
                pass

    # --- Primitive management ---
    def _add_prim(self, kind:str):
        if len(self.view.scene.prims) >= MAX_PRIMS:
            print(f"[prims] Max {MAX_PRIMS} reached")
            return
        if kind=='sphere':
            self.view.scene.add(Prim(KIND_SPHERE, [0.6,0,0,0], beta=0.05, color=(0.9,0.5,0.4)))
        elif kind=='box':
            self.view.scene.add(Prim(KIND_BOX, [0.5,0.5,0.5,0], beta=0.0, color=(0.4,0.7,0.9)))
        elif kind=='capsule':
            self.view.scene.add(Prim(KIND_CAPSULE, [0.3,1.5,0,0], beta=0.02, color=(0.6,0.9,0.5)))
        elif kind=='torus':
            self.view.scene.add(Prim(KIND_TORUS, [0.9,0.25,0,0], beta=0.03, color=(0.8,0.6,0.4)))
        elif kind=='mobius':
            # params: [R, width]
            self.view.scene.add(Prim(KIND_MOBIUS, [1.2, 0.25, 0, 0], beta=0.02, color=(0.7,0.5,0.9)))
        elif kind=='superellipsoid':
            # params: [radius, power]
            self.view.scene.add(Prim(KIND_SUPERELLIPSOID, [1.2, 4.0, 0, 0], beta=0.0, color=(0.95,0.9,0.85)))
        elif kind=='quasicrystal':
            # params: [scale, iso, thickness]
            self.view.scene.add(Prim(KIND_QUASICRYSTAL, [3.0, 1.0, 0.02, 0], beta=0.0, color=(0.2,0.9,0.9)))
        elif kind=='torus4d':
            # params: [R1, R2, r, w_slice] - two major radii, minor radius, 4D slice position
            self.view.scene.add(Prim(KIND_TORUS4D, [1.0, 0.8, 0.3, 0.0], beta=0.0, color=(0.9,0.3,0.9)))
        elif kind=='mandelbulb':
            # params: [power, bailout, max_iter, scale] - fractal parameters (better visibility)
            self.view.scene.add(Prim(KIND_MANDELBULB, [8.0, 2.0, 24, 0.8], beta=0.0, color=(0.9,0.2,0.1)))
        elif kind=='klein':
            # params: [scale, n, t_offset, thickness] - Klein bottle parameters (75% smaller)
            self.view.scene.add(Prim(KIND_KLEIN, [0.25, 2.0, 0.0, 0.025], beta=0.0, color=(0.1,0.7,0.9)))
        elif kind=='menger':
            # params: [iterations, size, 0, 0] - Menger sponge fractal
            self.view.scene.add(Prim(KIND_MENGER, [3, 1.0, 0, 0], beta=0.0, color=(0.8,0.6,0.2)))
        elif kind=='hyperbolic':
            # params: [scale, order, symmetry, 0] - Hyperbolic {order,symmetry} tiling
            self.view.scene.add(Prim(KIND_HYPERBOLIC, [2.0, 7, 3, 0], beta=0.0, color=(0.9,0.3,0.7)))
        elif kind=='gyroid':
            # params: [scale, tau, thickness, 0]
            self.view.scene.add(Prim(KIND_GYROID, [2.5, 0.0, 0.04, 0], beta=0.0, color=(0.7,0.9,0.3)))
        elif kind=='trefoil':
            # params: [scale, tube, samples, 0]
            self.view.scene.add(Prim(KIND_TREFOIL, [0.8, 0.08, 96, 0], beta=0.0, color=(0.9,0.5,0.2)))
        self._refresh_prim_label(); self.view.update()

    def _del_last(self):
        if self.view.scene.prims:
            self.view.scene.remove_index(len(self.view.scene.prims)-1)
            self._refresh_prim_label(); self.view.update()

    def _duplicate_selected(self):
        if not (0 <= self._current_sel < len(self.view.scene.prims)):
            return
        try:
            src = self.view.scene.prims[self._current_sel]
            # Shallow copy primitive fields
            from adaptivecad.aacore.sdf import Prim as _Prim
            new_pr = _Prim(src.kind, list(src.params), beta=float(src.beta), color=tuple(src.color[:3]), op=src.op)
            # Offset position slightly so it's visible; rely on set_transform if available
            M = src.xform.M.copy()
            M[:3,3] += np.array([0.25,0.25,0.0], np.float32)
            if hasattr(new_pr, 'xform'):
                new_pr.xform.M = M
            self.view.scene.add(new_pr)
            self._refresh_prim_label(); self.view.update()
        except Exception as e:
            log.debug(f"duplicate failed: {e}")

    def _center_on_selected(self):
        if not (0 <= self._current_sel < len(self.view.scene.prims)):
            return
        pr = self.view.scene.prims[self._current_sel]
        try:
            pos = pr.xform.M[:3,3]
            self.view.cam_target = pos.astype(np.float32)
            self.view._update_camera()
        except Exception:
            pass

    def _reset_camera(self):
        self.view.yaw = 0.0; self.view.pitch = 0.0
        self.view.distance = 6.0
        self.view.cam_target = np.array([0.0,0.0,0.0], np.float32)
        self.view._update_camera()

    def _export_scene_json(self):
        try:
            data = []
            for pr in self.view.scene.prims:
                entry = {
                    'kind': self._kind_name(pr.kind),
                    'params': [float(x) for x in pr.params],
                    'beta': float(pr.beta),
                    'color': [float(c) for c in pr.color[:3]],
                    'op': pr.op,
                    'pos': [float(v) for v in pr.xform.M[:3,3]]
                }
                data.append(entry)
            ts = time.strftime('%Y%m%d_%H%M%S')
            out_path = os.path.join(os.getcwd(), f'analytic_scene_{ts}.json')
            with open(out_path,'w',encoding='utf-8') as f:
                json.dump(data,f,indent=2)
            log.info(f"Exported analytic scene -> {out_path}")
        except Exception as e:
            log.debug(f"export scene failed: {e}")

    def _refresh_prim_label(self):
        self._prim_list_label.setText(f"({len(self.view.scene.prims)})")
        # rebuild primitive buttons
        while self._prim_buttons_box.count():
            it = self._prim_buttons_box.takeAt(0)
            w = it.widget()
            if w: w.deleteLater()
        for idx, pr in enumerate(self.view.scene.prims):
            b = QPushButton(f"#{idx} {self._kind_name(pr.kind)}")
            b.setCheckable(True)
            if idx == self._current_sel: b.setChecked(True)
            def make_cb(i):
                return lambda _=False: self._select_prim(i)
            b.clicked.connect(make_cb(idx))
            self._prim_buttons_box.addWidget(b)
        self._prim_buttons_box.addStretch(1)

    def _kind_name(self, k):
        return {KIND_SPHERE:"Sphere",KIND_BOX:"Box",KIND_CAPSULE:"Capsule",KIND_TORUS:"Torus", KIND_MOBIUS: "Mobius", KIND_SUPERELLIPSOID:"Superellipsoid", KIND_QUASICRYSTAL:"QuasiCrystal", KIND_TORUS4D:"4D Torus", KIND_MANDELBULB:"Mandelbulb", KIND_KLEIN:"Klein Bottle", KIND_MENGER:"Menger Sponge", KIND_HYPERBOLIC:"Hyperbolic Tiling", KIND_GYROID:"Gyroid", KIND_TREFOIL:"Trefoil Knot"}.get(k,str(k))

    def _make_row(self, widgets):
        box = QWidget(); hl = QHBoxLayout(box); hl.setContentsMargins(0,0,0,0)
        for w in widgets: hl.addWidget(w)
        return box

    def _ensure_on_screen(self):
        try:
            top = self.window()
            if top is None:
                return
            # get window frame geometry and check against available screens
            fg = top.frameGeometry()
            screens = QGuiApplication.screens()
            intersects = False
            for s in screens:
                ag = s.availableGeometry()
                if fg.intersected(ag).isValid():
                    intersects = True
                    break
            if not intersects and screens:
                # move to center of primary screen
                primary = QGuiApplication.primaryScreen() or screens[0]
                ag = primary.availableGeometry()
                new_x = ag.x() + max(0, (ag.width() - fg.width()) // 2)
                new_y = ag.y() + max(0, (ag.height() - fg.height()) // 2)
                try:
                    top.move(new_x, new_y)
                except Exception:
                    try:
                        top.setGeometry(new_x, new_y, fg.width(), fg.height())
                    except Exception:
                        pass
        except Exception:
            pass

    def _select_prim(self, idx:int):
        if not (0 <= idx < len(self.view.scene.prims)):
            self._current_sel = -1; self._edit_group.setEnabled(False);
            self._update_mandelbulb_export_ui(None)
            return
        self._current_sel = idx
        pr = self.view.scene.prims[idx]
        # position from transform matrix (assume affine last column xyz)
        pos = pr.xform.M[:3,3]
        for i in range(3): self._sp_pos[i].blockSignals(True); self._sp_pos[i].setValue(float(pos[i])); self._sp_pos[i].blockSignals(False)
        # populate move spinners (authoritative for translation edits)
        if hasattr(self, '_sp_move'):
            for i in range(3):
                self._sp_move[i].blockSignals(True)
                self._sp_move[i].setValue(float(pos[i]))
                self._sp_move[i].blockSignals(False)
        # params
        self._sp_param[0].blockSignals(True); self._sp_param[0].setValue(float(pr.params[0])); self._sp_param[0].blockSignals(False)
        self._sp_param[1].blockSignals(True); self._sp_param[1].setValue(float(pr.params[1] if pr.kind!=KIND_SPHERE else 0.0)); self._sp_param[1].blockSignals(False)
        self._sp_beta.blockSignals(True); self._sp_beta.setValue(pr.beta); self._sp_beta.blockSignals(False)
        self._op_box.blockSignals(True); self._op_box.setCurrentIndex(0 if pr.op=='solid' else 1); self._op_box.blockSignals(False)
        self._current_color = tuple(pr.color[:3])
        # rotation / scale sync
        if hasattr(pr, 'euler'):
            for i in range(3):
                self._sp_rot[i].blockSignals(True); self._sp_rot[i].setValue(float(pr.euler[i])); self._sp_rot[i].blockSignals(False)
        if hasattr(pr, 'scale'):
            for i in range(3):
                self._sp_scl[i].blockSignals(True); self._sp_scl[i].setValue(float(pr.scale[i])); self._sp_scl[i].blockSignals(False)
            try:
                # Reflect current uniform value as X scale (assumes uniform when set via this control)
                self._sp_scl_u.blockSignals(True)
                self._sp_scl_u.setValue(float(pr.scale[0]))
                self._sp_scl_u.blockSignals(False)
            except Exception:
                pass
        self._edit_group.setEnabled(True)
        # Update parameter tooltips / semantic hints
        try:
            kind_name = self._kind_name(pr.kind)
            if kind_name == 'Sphere':
                a_tt = 'Radius'; b_tt = 'Unused'
            elif kind_name == 'Capsule':
                a_tt = 'Radius'; b_tt = 'Half-Length'
            elif kind_name == 'Torus':
                a_tt = 'Major Radius'; b_tt = 'Minor Radius'
            elif kind_name == 'Mobius':
                a_tt = 'Ring Radius R'; b_tt = 'Strip Half-Width'
            elif kind_name == 'Box':
                a_tt = 'Half-Extent X'; b_tt = 'Half-Extent Y (Z via scale)'
            elif kind_name == 'Superellipsoid':
                a_tt = 'Radius (overall)'; b_tt = 'Power p (boxier > 2)'
            elif kind_name == 'QuasiCrystal':
                a_tt = 'Scale (frequency)'; b_tt = 'Iso (level)'
            elif kind_name == '4D Torus':
                a_tt = 'Major Radius 1 (XY plane)'; b_tt = 'Major Radius 2 (ZW plane)'
            elif kind_name == 'Mandelbulb':
                a_tt = 'Power (8.0 = classic)'; b_tt = 'Bailout Radius (escape)'
            elif kind_name == 'Klein Bottle':
                a_tt = 'Scale (overall size)'; b_tt = 'Shape Parameter'
            elif kind_name == 'Menger Sponge':
                a_tt = 'Iterations (detail level)'; b_tt = 'Size (overall scale)'
            elif kind_name == 'Hyperbolic Tiling':
                a_tt = 'Scale (overall size)'; b_tt = 'Order (polygon sides)'
            elif kind_name == 'Gyroid':
                a_tt = 'Scale (frequency)'; b_tt = 'Tau (iso-level)'
            elif kind_name == 'Trefoil Knot':
                a_tt = 'Scale (curve size)'; b_tt = 'Tube Radius'
            else:
                a_tt = 'Param A'; b_tt = 'Param B'
            self._sp_param[0].setToolTip(a_tt)
            self._sp_param[1].setToolTip(b_tt)
        except Exception:
            pass

        self._update_mandelbulb_export_ui(pr)

    def _apply_edit(self):
        if self._current_sel < 0 or self._current_sel >= len(self.view.scene.prims):
            return
        pr = self.view.scene.prims[self._current_sel]
        # existing matrix before rebuilding
        M = pr.xform.M.copy()
        # apply params
        pr.params[0] = self._sp_param[0].value()
        if pr.kind != KIND_SPHERE:
            pr.params[1] = self._sp_param[1].value()
        pr.beta = self._sp_beta.value()
        pr.op = 'solid' if self._op_box.currentIndex()==0 else 'subtract'
        pr.color[:3] = np.array(self._current_color[:3])
        # translation driven by move spinners
        if hasattr(self, '_sp_move'):
            pos = [self._sp_move[i].value() for i in range(3)]
        else:
            pos = [self._sp_pos[i].value() for i in range(3)]
        rx, ry, rz = [self._sp_rot[i].value() for i in range(3)]
        sx, sy, sz = [self._sp_scl[i].value() for i in range(3)]
        if hasattr(pr, 'set_transform'):
            pr.set_transform(pos=pos, euler=[rx,ry,rz], scale=[sx,sy,sz])
        else:
            # fallback: just translate
            for i in range(3): M[i,3] = pos[i]
            pr.xform.M = M
        # notify & refresh
        try:
            self.view.scene._notify()
        except Exception:
            pass
        self.view.update()

    # --- Sketch save/load ---
    def _save_sketch_json(self):
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            path, _ = QFileDialog.getSaveFileName(self, "Save Sketch JSON", "sketch.json", "JSON (*.json)")
            if not path:
                return
            # Build doc from overlay entities (minimal polyline/circle export)
            doc = SketchDocument(units=Units.MM)
            pid = 0
            def new_pid():
                nonlocal pid; pid += 1; return f"p{pid}"
            extra = { 'lines': [], 'rects': [], 'arcs3': [], 'dimensions': [], 'dim_precision': int(getattr(self,'_dim_precision',2)) }
            for ent in self._sketch.entities:
                if isinstance(ent, Polyline2D):
                    ids = []
                    for pt in ent.pts:
                        idp = new_pid(); ids.append(idp)
                        doc.points.append(type('P',(),{})())  # placeholder; will patch below
                        doc.points[-1].__dict__.update({"id": idp, "x": float(pt[0]), "y": float(pt[1]), "construction": False})
                    doc.polylines.append(type('PL',(),{})())
                    doc.polylines[-1].__dict__.update({"id": f"pl{pid}", "verts": ids, "closed": False, "construction": False})
                elif isinstance(ent, Circle2D):
                    idc = new_pid()
                    c = ent.center
                    doc.points.append(type('P',(),{})())
                    doc.points[-1].__dict__.update({"id": idc, "x": float(c[0]), "y": float(c[1]), "construction": False})
                    doc.circles.append(type('C',(),{})())
                    doc.circles[-1].__dict__.update({"id": f"c{pid}", "center": idc, "radius": float(ent.radius), "construction": False})
                elif isinstance(ent, Line2D):
                    if getattr(ent, 'p1', None) is not None:
                        extra['lines'].append({'p0':[float(ent.p0[0]), float(ent.p0[1])], 'p1':[float(ent.p1[0]), float(ent.p1[1])]})
                elif isinstance(ent, Rect2D):
                    p0 = [float(ent.p0[0]), float(ent.p0[1])]
                    p1 = [float(ent.p1[0]), float(ent.p1[1])] if getattr(ent,'p1', None) is not None else p0
                    extra['rects'].append({'p0': p0, 'p1': p1})
                elif isinstance(ent, Arc2D):
                    if getattr(ent,'p0',None) is not None and getattr(ent,'p1',None) is not None and getattr(ent,'p2',None) is not None:
                        extra['arcs3'].append({'p0':[float(ent.p0[0]), float(ent.p0[1])], 'p1':[float(ent.p1[0]), float(ent.p1[1])], 'p2':[float(ent.p2[0]), float(ent.p2[1])]} )
            # dimensions
            for d in getattr(self._sketch, 'dimensions', []) or []:
                try:
                    if isinstance(d, DimDiameter2D) and isinstance(d.circle_ref, tuple) and d.circle_ref[0]=='circle' and isinstance(d.circle_ref[1], Circle2D):
                        c = d.circle_ref[1]
                        extra['dimensions'].append({'type':'diameter', 'center':[float(c.center[0]), float(c.center[1])]})
                    elif isinstance(d, DimLinear2D):
                        a = d._xy(d.ref_a); b = d._xy(d.ref_b)
                        if a is not None and b is not None:
                            # type discrimination for H/V vs general
                            t = 'linear'
                            if isinstance(d, DimHorizontal2D): t='horizontal'
                            elif isinstance(d, DimVertical2D): t='vertical'
                            extra['dimensions'].append({'type': t, 'a':[float(a[0]), float(a[1])], 'b':[float(b[0]), float(b[1])], 'offset': float(getattr(d,'offset',0.0))})
                except Exception:
                    pass
            # Merge extra into doc JSON
            try:
                base = json.loads(doc.to_json())
            except Exception:
                base = {}
            base.update(extra)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(base, f, indent=2)
            QMessageBox.information(self, "Sketch", f"Saved sketch to {path}")
        except Exception as e:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Sketch Save", f"Failed: {e}")
            except Exception:
                pass

    def _load_sketch_json(self):
        try:
            from PySide6.QtWidgets import QFileDialog, QMessageBox
            path, _ = QFileDialog.getOpenFileName(self, "Load Sketch JSON", filter="JSON (*.json)")
            if not path:
                return
            with open(path, 'r', encoding='utf-8') as f:
                s = f.read()
            # Parse raw JSON alongside SketchDocument for compatibility
            try:
                raw = json.loads(s)
            except Exception:
                raw = {}
            doc = SketchDocument.from_json(s)
            # Replace overlay entities and include extended shapes
            self._sketch.entities.clear()
            # Build point map
            pm = {p.id: np.array([p.x, p.y], np.float32) for p in getattr(doc, 'points', [])}
            for pl in getattr(doc, 'polylines', []):
                pts = [ pm[v] for v in getattr(pl, 'verts', []) if v in pm ]
                self._sketch.entities.append(Polyline2D(pts))
            for c in getattr(doc, 'circles', []):
                ctr = pm.get(getattr(c, 'center', ''), np.array([0,0], np.float32))
                self._sketch.entities.append(Circle2D(ctr, float(getattr(c, 'radius', 0.0))))
            # Extended entities (raw JSON)
            for li in raw.get('lines', []) or []:
                p0 = np.array([float(li.get('p0',[0,0])[0]), float(li.get('p0',[0,0])[1])], np.float32)
                p1 = np.array([float(li.get('p1',[0,0])[0]), float(li.get('p1',[0,0])[1])], np.float32)
                self._sketch.entities.append(Line2D(p0, p1))
            for r in raw.get('rects', []) or []:
                p0 = np.array([float(r.get('p0',[0,0])[0]), float(r.get('p0',[0,0])[1])], np.float32)
                p1 = np.array([float(r.get('p1',[0,0])[0]), float(r.get('p1',[0,0])[1])], np.float32)
                self._sketch.entities.append(Rect2D(p0, p1))
            for a in raw.get('arcs3', []) or []:
                p0 = np.array([float(a.get('p0',[0,0])[0]), float(a.get('p0',[0,0])[1])], np.float32)
                p1 = np.array([float(a.get('p1',[0,0])[0]), float(a.get('p1',[0,0])[1])], np.float32)
                p2 = np.array([float(a.get('p2',[0,0])[0]), float(a.get('p2',[0,0])[1])], np.float32)
                self._sketch.entities.append(Arc2D(p0, p1, p2))
            # Dimensions
            self._sketch.dimensions = []
            for d in raw.get('dimensions', []) or []:
                t = d.get('type','linear')
                if t == 'diameter':
                    cx,cy = d.get('center',[0,0])
                    circ = None
                    for ent in self._sketch.entities:
                        if isinstance(ent, Circle2D) and abs(ent.center[0]-cx)<1e-6 and abs(ent.center[1]-cy)<1e-6:
                            circ = ent; break
                    if circ is not None:
                        self._sketch.dimensions.append(DimDiameter2D(('circle', circ), self))
                else:
                    a = d.get('a'); b = d.get('b')
                    if a is not None and b is not None:
                        pa = np.array([float(a[0]), float(a[1])], np.float32)
                        pb = np.array([float(b[0]), float(b[1])], np.float32)
                        off = float(d.get('offset', 0.0))
                        if t=='horizontal':
                            self._sketch.dimensions.append(DimHorizontal2D(pa, pb, self, offset=off))
                        elif t=='vertical':
                            self._sketch.dimensions.append(DimVertical2D(pa, pb, self, offset=off))
                        else:
                            self._sketch.dimensions.append(DimLinear2D(pa, pb, self, offset=off))
            # restore precision if present
            try:
                self._dim_precision = int(raw.get('dim_precision', getattr(self,'_dim_precision',2)))
            except Exception:
                pass
            self.view.update()
            QMessageBox.information(self, "Sketch", f"Loaded sketch from {path}")
        except Exception as e:
            try:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(self, "Sketch Load", f"Failed: {e}")
            except Exception:
                pass

    # Convenience passthroughs
    def viewport(self) -> AnalyticViewport: return self.view


def _analytic_dashboard_stylesheet() -> str:
    # Minimal dark dashboard styling (no external deps).
    return """
    QMainWindow, QWidget { background-color: #0b0f16; color: #d7e2ff; }
    QDockWidget { titlebar-close-icon: none; titlebar-normal-icon: none; }
    QDockWidget::title { background: #101827; padding: 6px; }
    QGroupBox { border: 1px solid #1c2a45; border-radius: 6px; margin-top: 10px; }
    QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px 0 4px; color: #a9c1ff; }
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit, QTableWidget {
        background-color: #0f1624;
        border: 1px solid #1c2a45;
        border-radius: 4px;
        padding: 4px;
        selection-background-color: #243a68;
    }
    QPushButton { background-color: #142238; border: 1px solid #223457; border-radius: 5px; padding: 6px 10px; }
    QPushButton:hover { background-color: #1a2c49; }
    QPushButton:pressed { background-color: #101b2c; }
    QTabWidget::pane { border: 1px solid #1c2a45; }
    QTabBar::tab { background: #0f1624; border: 1px solid #1c2a45; padding: 6px 10px; margin-right: 2px; }
    QTabBar::tab:selected { background: #162540; }
    """


class AnalyticViewportDashboardWindow(QMainWindow):
    """Dashboard-style Analytic Viewer (layout B): docks + central viewport."""

    def __init__(self, parent=None, *, aacore_scene: AACoreScene | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("AdaptiveCAD – Analytic Viewer")

        self.panel = AnalyticViewportPanel(self, aacore_scene=aacore_scene, ui_layout="docked")

        # Central viewport
        try:
            self.panel.view.setParent(self)
        except Exception:
            pass
        self.setCentralWidget(self.panel.view)

        # Docks
        left = QDockWidget("Navigator", self)
        left.setObjectName("dock_navigator")
        left.setWidget(self.panel._dock_left_scroll or QWidget())
        left.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        right = QDockWidget("Inspector", self)
        right.setObjectName("dock_inspector")
        right.setWidget(self.panel._dock_right_scroll or QWidget())
        right.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        bottom = QDockWidget("Console / Metrics", self)
        bottom.setObjectName("dock_console")
        bottom.setWidget(self.panel._dock_bottom_widget or QWidget())
        bottom.setAllowedAreas(Qt.BottomDockWidgetArea | Qt.TopDockWidgetArea)

        self.addDockWidget(Qt.LeftDockWidgetArea, left)
        self.addDockWidget(Qt.RightDockWidgetArea, right)
        self.addDockWidget(Qt.BottomDockWidgetArea, bottom)

        try:
            self.resize(1400, 900)
            self.resizeDocks([left, right], [360, 380], Qt.Horizontal)
            self.resizeDocks([bottom], [260], Qt.Vertical)
        except Exception:
            pass

        try:
            self.setStyleSheet(_analytic_dashboard_stylesheet())
        except Exception:
            pass

def create_analytic_viewport_with_panel(parent=None, aacore_scene: AACoreScene | None = None):
    return AnalyticViewportPanel(parent, aacore_scene=aacore_scene)


def preview_primitive(panel):
    """Module-level helper: CPU raymarch preview for a panel's selected primitive."""
    try:
        if panel is None:
            return
        if not (0 <= getattr(panel, '_current_sel', -1) < len(panel.view.scene.prims)):
            return
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
        from PySide6.QtGui import QImage, QPixmap
        from adaptivecad.aacore.sdf import Scene as _Scene, Prim as _Prim, mandelbulb_color_cpu, KIND_MANDELBULB
        import numpy as _np

        pr = panel.view.scene.prims[panel._current_sel]
        tmp_scene = _Scene()
        pcopy = _Prim(pr.kind, list(pr.params), beta=float(pr.beta), color=tuple(pr.color[:3]), op=pr.op)
        pcopy.xform.M = pr.xform.M.copy()
        tmp_scene.add(pcopy)

        W, H = 320, 200
        img = _np.zeros((H, W, 3), dtype=_np.uint8)
        cam_pos = getattr(panel.view, 'cam_pos', _np.array([0.0,0.0,6.0], _np.float32)).astype(_np.float64)
        R = panel.view._cam_basis()
        fov = 45.0 * (3.141592653589793 / 180.0)
        aspect = float(W) / float(H)
        max_steps = 160
        eps = 1e-3
        max_dist = 60.0

        def ray_dir(x, y):
            ndc_x = ((x + 0.5) / W) * 2.0 - 1.0
            ndc_y = ((y + 0.5) / H) * 2.0 - 1.0
            ndc_x *= aspect
            rd = _np.dot(R, _np.array([ndc_x, -ndc_y, -1.0 / _np.tan(0.5 * fov)], dtype=_np.float64))
            rd = rd / max(1e-12, _np.linalg.norm(rd))
            return rd

        for j in range(H):
            for i in range(W):
                ro = cam_pos.copy(); rd = ray_dir(i, j)
                t = 0.0; hit = False
                for _ in range(max_steps):
                    pw = ro + rd * t
                    d, _, _ = tmp_scene.sdf(pw)
                    if d < eps:
                        hit = True; break
                    t += max(d, 0.002)
                    if t > max_dist: break
                if not hit:
                    bg = (tmp_scene.bg_color * 255.0).astype(_np.uint8)
                    img[j, i, :] = bg
                else:
                    p_hit = ro + rd * t
                    delta = eps
                    nx = tmp_scene.sdf(p_hit + _np.array([delta,0,0]))[0] - tmp_scene.sdf(p_hit - _np.array([delta,0,0]))[0]
                    ny = tmp_scene.sdf(p_hit + _np.array([0,delta,0]))[0] - tmp_scene.sdf(p_hit - _np.array([0,delta,0]))[0]
                    nz = tmp_scene.sdf(p_hit + _np.array([0,0,delta]))[0] - tmp_scene.sdf(p_hit - _np.array([0,0,delta]))[0]
                    n = _np.array([nx, ny, nz], dtype=_np.float64);
                    n = n / max(1e-9, _np.linalg.norm(n))
                    if pr.kind == KIND_MANDELBULB:
                        Mi = _np.linalg.inv(pr.xform.M)
                        mparams = pr.params
                        scale = float(mparams[3]) if len(mparams) > 3 else 1.0
                        pl = (Mi @ _np.array([p_hit[0], p_hit[1], p_hit[2], 1.0]))[:3] * scale
                        surf = mandelbulb_color_cpu(pl, float(mparams[0]), float(mparams[1]), int(max(4, mparams[2])), int(panel.view.fractal_color_mode), float(panel.view.fractal_ni_scale), float(panel.view.fractal_orbit_shell))
                    else:
                        surf = _np.clip(pr.color[:3], 0.0, 1.0)
                    L = tmp_scene.env_light / max(1e-9, _np.linalg.norm(tmp_scene.env_light))
                    ndl = max(0.0, float(_np.dot(n, L)))
                    base = surf * (0.5 + 0.5 * ndl)
                    col = (_np.clip(base, 0.0, 1.0) * 255.0).astype(_np.uint8)
                    img[j, i, :] = col

        qimg = QImage(img.data.tobytes(), W, H, QImage.Format.Format_RGB888)
        dlg = QDialog(panel)
        dlg.setWindowTitle("Primitive Preview")
        lay = QVBoxLayout(dlg)
        lbl = QLabel(dlg)
        pix = QPixmap.fromImage(qimg)
        lbl.setPixmap(pix)
        lay.addWidget(lbl)
        dlg.setLayout(lay)
        dlg.exec()
    except Exception as e:
        try: log.debug(f"preview_primitive failed: {e}")
        except Exception: pass

# --- persistence helpers on AnalyticViewport ---
def _analytic_settings_defaults():
    return {
        'debug_mode':0,
        'use_analytic_aa':1,
        'use_toon':0,
        'toon_levels':4.0,
        'curv_strength':1.0,
        'use_foveated':1,
        'show_beta_overlay':0,
        'beta_overlay_intensity':0.65,
        'beta_scale':1.0,
        'beta_cmap':0,
    'fractal_color_mode': 1,
    'fractal_orbit_shell': 1.0,
    'fractal_ni_scale': 0.08,
        'wheel_enabled': True,
        'wheel_edge_fit': True,
        'wheel_overshoot_px': 14,
        'wheel_thickness_ratio': 0.10,
        'wheel_opacity': 1.0,
        'wheel_text_scale': 1.0,
        'wheel_auto_spin': False,
        'wheel_auto_spin_speed': 0.0
    }

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))

def _apply_settings(self, data):
    self.debug_mode = int(data.get('debug_mode',0))
    self.use_analytic_aa = int(data.get('use_analytic_aa',1))
    self.use_toon = int(data.get('use_toon',0))
    self.toon_levels = float(_clamp(data.get('toon_levels',4.0),1.0,16.0))
    self.curv_strength = float(_clamp(data.get('curv_strength',1.0),0.0,2.0))
    self.use_foveated = int(data.get('use_foveated',1))
    self.show_beta_overlay = int(data.get('show_beta_overlay',0))
    self.beta_overlay_intensity = float(_clamp(data.get('beta_overlay_intensity',0.65),0.0,1.0))
    self.beta_scale = float(_clamp(data.get('beta_scale',1.0),0.01,32.0))
    self.beta_cmap = int(_clamp(data.get('beta_cmap',0),0,3))
    self.fractal_color_mode = int(_clamp(data.get('fractal_color_mode', getattr(self, 'fractal_color_mode', 1)), 0, 2))
    self.fractal_orbit_shell = float(_clamp(data.get('fractal_orbit_shell', getattr(self, 'fractal_orbit_shell', 1.0)), 0.0, 4.0))
    self.fractal_ni_scale = float(_clamp(data.get('fractal_ni_scale', getattr(self, 'fractal_ni_scale', 0.08)), 0.01, 0.5))
    # dim settings
    try:
        panel = self.parent() if hasattr(self,'parent') else None
        if panel is not None:
            setattr(panel, '_dim_precision', int(data.get('dim_precision', getattr(panel,'_dim_precision',2))))
            setattr(panel, '_dim_type', str(data.get('dim_type', getattr(panel,'_dim_type','linear'))))
            if hasattr(panel, '_wheel_enabled'):
                panel._wheel_enabled = bool(data.get('wheel_enabled', panel._wheel_enabled))
                panel._wheel_edge_fit = bool(data.get('wheel_edge_fit', panel._wheel_edge_fit))
                panel._wheel_edge_overshoot = int(data.get('wheel_overshoot_px', panel._wheel_edge_overshoot))
                panel._wheel_thickness = float(_clamp(data.get('wheel_thickness_ratio', panel._wheel_thickness), 0.02, 0.40))
                panel._wheel_opacity = float(_clamp(data.get('wheel_opacity', panel._wheel_opacity), 0.0, 1.0))
                panel._wheel_text_scale = float(_clamp(data.get('wheel_text_scale', panel._wheel_text_scale), 0.5, 2.5))
                panel._wheel_auto_spin = bool(data.get('wheel_auto_spin', panel._wheel_auto_spin))
                panel._wheel_auto_spin_speed = float(_clamp(data.get('wheel_auto_spin_speed', panel._wheel_auto_spin_speed), 0.0, 360.0))
                if hasattr(panel, '_sync_wheel_controls'):
                    panel._sync_wheel_controls()
                if hasattr(panel, '_apply_wheel_settings'):
                    panel._apply_wheel_settings()
            section_vis = data.get('section_visibility')
            if isinstance(section_vis, dict):
                try:
                    panel._section_vis = {str(k): bool(v) for k, v in section_vis.items()}
                except Exception:
                    panel._section_vis = {}
                    for k, v in section_vis.items():
                        try:
                            panel._section_vis[str(k)] = bool(v)
                        except Exception:
                            pass
            elif not hasattr(panel, '_section_vis'):
                panel._section_vis = {}
            if hasattr(panel, '_sync_fractal_controls'):
                panel._sync_fractal_controls()
    except Exception:
        pass

def _load_settings(self):
    try:
        if os.path.exists(self._settings_path):
            with open(self._settings_path,'r',encoding='utf-8') as f:
                data=json.load(f)
        else:
            data=_analytic_settings_defaults()
        _apply_settings(self, data)
        # Restore sketch overlay (if any)
        try:
            panel = self.parent() if hasattr(self, 'parent') else None
            sk = data.get('sketch_overlay', None)
            if panel is not None and sk is not None and hasattr(panel, '_sketch'):
                panel._sketch.entities.clear()
                for pl in sk.get('polylines', []) or []:
                    pts = [np.array([float(p[0]), float(p[1])], np.float32) for p in pl]
                    panel._sketch.entities.append(Polyline2D(pts))
                for c in sk.get('circles', []) or []:
                    ctr = np.array([float(c.get('center',[0,0])[0]), float(c.get('center',[0,0])[1])], np.float32)
                    rad = float(c.get('radius', 0.0))
                    panel._sketch.entities.append(Circle2D(ctr, rad))
                for li in sk.get('lines', []) or []:
                    p0 = np.array([float(li.get('p0',[0,0])[0]), float(li.get('p0',[0,0])[1])], np.float32)
                    p1 = np.array([float(li.get('p1',[0,0])[0]), float(li.get('p1',[0,0])[1])], np.float32)
                    panel._sketch.entities.append(Line2D(p0, p1))
                for r in sk.get('rects', []) or []:
                    p0 = np.array([float(r.get('p0',[0,0])[0]), float(r.get('p0',[0,0])[1])], np.float32)
                    p1 = np.array([float(r.get('p1',[0,0])[0]), float(r.get('p1',[0,0])[1])], np.float32)
                    panel._sketch.entities.append(Rect2D(p0, p1))
                for a in sk.get('arcs3', []) or []:
                    p0 = np.array([float(a.get('p0',[0,0])[0]), float(a.get('p0',[0,0])[1])], np.float32)
                    p1 = np.array([float(a.get('p1',[0,0])[0]), float(a.get('p1',[0,0])[1])], np.float32)
                    p2 = np.array([float(a.get('p2',[0,0])[0]), float(a.get('p2',[0,0])[1])], np.float32)
                    panel._sketch.entities.append(Arc2D(p0, p1, p2))
                # dimensions
                try:
                    panel._sketch.dimensions = []
                    for d in sk.get('dimensions', []) or []:
                        t = d.get('type','linear')
                        if t == 'diameter':
                            # find circle by matching center exactly
                            cx,cy = d.get('center',[0,0])
                            circ = None
                            for ent in panel._sketch.entities:
                                if isinstance(ent, Circle2D) and abs(ent.center[0]-cx)<1e-6 and abs(ent.center[1]-cy)<1e-6:
                                    circ = ent; break
                            if circ is not None:
                                panel._sketch.dimensions.append(DimDiameter2D(('circle', circ), panel))
                        else:
                            a = d.get('a'); b = d.get('b')
                            if a is not None and b is not None:
                                pa = np.array([float(a[0]), float(a[1])], np.float32)
                                pb = np.array([float(b[0]), float(b[1])], np.float32)
                                off = float(d.get('offset', 0.0))
                                if t=='horizontal':
                                    panel._sketch.dimensions.append(DimHorizontal2D(pa, pb, panel, offset=off))
                                elif t=='vertical':
                                    panel._sketch.dimensions.append(DimVertical2D(pa, pb, panel, offset=off))
                                else:
                                    panel._sketch.dimensions.append(DimLinear2D(pa, pb, panel, offset=off))
                except Exception:
                    pass
                # grid settings
                try:
                    panel._sketch_grid_on = bool(sk.get('grid_on', panel._sketch_grid_on))
                    panel._sketch_snap_grid = bool(sk.get('snap_grid', panel._sketch_snap_grid))
                    panel._sketch_grid_step = float(sk.get('grid_step', panel._sketch_grid_step))
                    panel._sketch_grid_screen_lock = bool(sk.get('grid_screen_lock', getattr(panel,'_sketch_grid_screen_lock', True)))
                except Exception:
                    pass
        except Exception:
            pass
    except Exception as e:
        print(f"(analytic settings) load failed: {e}")

def _save_settings(self):
    try:
        data_update={
            'debug_mode': self.debug_mode,
            'use_analytic_aa': self.use_analytic_aa,
            'use_toon': self.use_toon,
            'toon_levels': self.toon_levels,
            'curv_strength': self.curv_strength,
            'use_foveated': self.use_foveated,
            'show_beta_overlay': self.show_beta_overlay,
            'beta_overlay_intensity': self.beta_overlay_intensity,
            'beta_scale': self.beta_scale,
            'beta_cmap': self.beta_cmap,
            'fractal_color_mode': int(getattr(self, 'fractal_color_mode', 1)),
            'fractal_orbit_shell': float(getattr(self, 'fractal_orbit_shell', 1.0)),
            'fractal_ni_scale': float(getattr(self, 'fractal_ni_scale', 0.08))
        }
        panel = self.parent() if hasattr(self, 'parent') else None
        if panel is not None and hasattr(panel, '_wheel_enabled'):
            data_update.update({
                'wheel_enabled': bool(panel._wheel_enabled),
                'wheel_edge_fit': bool(panel._wheel_edge_fit),
                'wheel_overshoot_px': int(panel._wheel_edge_overshoot),
                'wheel_thickness_ratio': float(panel._wheel_thickness),
                'wheel_opacity': float(panel._wheel_opacity),
                'wheel_text_scale': float(panel._wheel_text_scale),
                'wheel_auto_spin': bool(panel._wheel_auto_spin),
                'wheel_auto_spin_speed': float(panel._wheel_auto_spin_speed),
            })
        if panel is not None and hasattr(panel, '_section_vis') and isinstance(panel._section_vis, dict):
            data_update['section_visibility'] = {str(k): bool(v) for k, v in panel._section_vis.items()}
        # Preserve unrelated preference keys (e.g., 'analytic_as_main') by merging
        existing = {}
        if os.path.exists(self._settings_path):
            try:
                with open(self._settings_path,'r',encoding='utf-8') as f:
                    existing = json.load(f) or {}
            except Exception:
                existing = {}
        # Serialize sketch overlay
        try:
            panel = self.parent() if hasattr(self, 'parent') else None
            if panel is not None and hasattr(panel, '_sketch'):
                sk = {'polylines': [], 'circles': [], 'lines': [], 'rects': [], 'arcs3': [], 'dimensions': [], 'grid_on': bool(getattr(panel,'_sketch_grid_on', False)), 'snap_grid': bool(getattr(panel,'_sketch_snap_grid', False)), 'grid_step': float(getattr(panel,'_sketch_grid_step', 10.0)), 'grid_screen_lock': bool(getattr(panel,'_sketch_grid_screen_lock', True))}
                for ent in getattr(panel, '_sketch').entities:
                    if isinstance(ent, Polyline2D):
                        sk['polylines'].append([[float(p[0]), float(p[1])] for p in ent.pts])
                    elif isinstance(ent, Circle2D):
                        sk['circles'].append({'center':[float(ent.center[0]), float(ent.center[1])], 'radius': float(ent.radius)})
                    elif isinstance(ent, Line2D):
                        if ent.p1 is not None:
                            sk['lines'].append({'p0':[float(ent.p0[0]), float(ent.p0[1])], 'p1':[float(ent.p1[0]), float(ent.p1[1])]} )
                    elif isinstance(ent, Rect2D):
                        p0 = [float(ent.p0[0]), float(ent.p0[1])]
                        p1 = [float(ent.p1[0]), float(ent.p1[1])] if getattr(ent,'p1', None) is not None else p0
                        sk['rects'].append({'p0': p0, 'p1': p1})
                    elif isinstance(ent, Arc2D):
                        if ent.p0 is not None and ent.p1 is not None and ent.p2 is not None:
                            sk['arcs3'].append({'p0':[float(ent.p0[0]), float(ent.p0[1])], 'p1':[float(ent.p1[0]), float(ent.p1[1])], 'p2':[float(ent.p2[0]), float(ent.p2[1])]} )
                # dimensions (store basic types we support now)
                for d in getattr(panel._sketch, 'dimensions', []) or []:
                    try:
                        if isinstance(d, DimDiameter2D) and isinstance(d.circle_ref, tuple) and d.circle_ref[0]=='circle' and isinstance(d.circle_ref[1], Circle2D):
                            c = d.circle_ref[1]
                            sk['dimensions'].append({'type':'diameter', 'center':[float(c.center[0]), float(c.center[1])]})
                        elif isinstance(d, DimLinear2D):
                            a = d._xy(d.ref_a); b = d._xy(d.ref_b)
                            if a is not None and b is not None:
                                t = 'linear'
                                if isinstance(d, DimHorizontal2D): t='horizontal'
                                elif isinstance(d, DimVertical2D): t='vertical'
                                sk['dimensions'].append({'type': t, 'a':[float(a[0]), float(a[1])], 'b':[float(b[0]), float(b[1])], 'offset': float(getattr(d,'offset',0.0))})
                    except Exception:
                        pass
                data_update['sketch_overlay'] = sk
                # dimension settings
                try:
                    data_update['dim_precision'] = int(getattr(panel,'_dim_precision',2))
                    data_update['dim_type'] = str(getattr(panel,'_dim_type','linear'))
                except Exception:
                    pass
        except Exception:
            pass
        existing.update(data_update)
        with open(self._settings_path,'w',encoding='utf-8') as f:
            json.dump(existing,f,indent=2)
    except Exception as e:
        print(f"(analytic settings) save failed: {e}")

# Monkey-patch methods onto AnalyticViewport class after definition (simple, avoids editing earlier class body heavily)
AnalyticViewport._load_settings = _load_settings
AnalyticViewport._save_settings = _save_settings









