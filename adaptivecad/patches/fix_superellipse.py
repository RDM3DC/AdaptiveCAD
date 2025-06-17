#!/usr/bin/env python

from adaptivecad.command_defs import Feature

# Define the missing SuperellipseFeature class
class SuperellipseFeature(Feature):
    def __init__(self, rx, ry, n, segments=60):
        params = {
            "rx": rx,
            "ry": ry,
            "n": n,
            "segments": segments,
        }
        shape = self._make_shape(params)
        super().__init__("Superellipse", params, shape)

    @staticmethod
    def _make_shape(params):
        from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakeEdge
        from OCC.Core.gp import gp_Pnt
        import numpy as np
        rx = params["rx"]
        ry = params["ry"]
        n = params["n"]
        segments = params["segments"]
        
        # Generate points for superellipse: |x/rx|^n + |y/ry|^n = 1
        ts = np.linspace(0, 2 * np.pi, segments)
        # Convert parametric equations for superellipse
        pts = []
        for t in ts:
            # Parametric form with power of 2/n
            cos_t = np.cos(t)
            sin_t = np.sin(t)
            cos_t_abs = abs(cos_t)
            sin_t_abs = abs(sin_t)
            
            # Handle zero case to avoid division by zero
            if cos_t_abs < 1e-10:
                x = 0
            else:
                x = rx * np.sign(cos_t) * (cos_t_abs ** (2/n))
                
            if sin_t_abs < 1e-10:
                y = 0
            else:
                y = ry * np.sign(sin_t) * (sin_t_abs ** (2/n))
            
            pts.append(gp_Pnt(x, y, 0))
        
        # Create a wire from the points
        wire = BRepBuilderAPI_MakeWire()
        for i in range(segments):
            edge = BRepBuilderAPI_MakeEdge(pts[i], pts[(i + 1) % segments]).Edge()
            wire.Add(edge)
        
        # Create a face from the wire
        face = BRepBuilderAPI_MakeFace(wire.Wire()).Face()
        return face

    def rebuild(self):
        self.shape = self._make_shape(self.params)

# Define the missing NewSuperellipseCmd class
class NewSuperellipseCmd:
    def __init__(self):
        pass
    def run(self, mw):
        from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Superellipse Parameters")
                layout = QFormLayout(self)
                self.rx = QDoubleSpinBox()
                self.rx.setRange(0.1, 1000)
                self.rx.setValue(20.0)
                self.ry = QDoubleSpinBox()
                self.ry.setRange(0.1, 1000)
                self.ry.setValue(10.0)
                self.n = QDoubleSpinBox()
                self.n.setRange(0.1, 10.0)
                self.n.setValue(2.5)
                self.n.setSingleStep(0.1)
                self.segments = QSpinBox()
                self.segments.setRange(12, 200)
                self.segments.setValue(60)
                layout.addRow("Radius X", self.rx)
                layout.addRow("Radius Y", self.ry)
                layout.addRow("Exponent (n)", self.n)
                layout.addRow("Segments", self.segments)
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addWidget(buttons)
        
        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        rx = dlg.rx.value()
        ry = dlg.ry.value()
        n = dlg.n.value()
        segments = dlg.segments.value()
        
        feat = SuperellipseFeature(rx, ry, n, segments)
        try:
            from adaptivecad.command_defs import DOCUMENT
            DOCUMENT.append(feat)
        except Exception:
            pass
        mw.view._display.EraseAll()
        mw.view._display.DisplayShape(feat.shape, update=True)
        mw.view._display.FitAll()
        mw.win.statusBar().showMessage(f"Superellipse created: rx={rx}, ry={ry}, n={n}", 3000)

# Patch the adaptivecad.gui.playground module
import adaptivecad.gui.playground
adaptivecad.gui.playground.SuperellipseFeature = SuperellipseFeature
adaptivecad.gui.playground.NewSuperellipseCmd = NewSuperellipseCmd

print("Patched missing SuperellipseFeature and NewSuperellipseCmd classes in playground module.")
