import FreeCAD
import FreeCADGui
import Part
from PySide import QtGui

# Ensure AdaptiveCAD is on sys.path (best to install/symlink repo instead of editing here)
# Try relative path heuristic if running from inside the repo
try:
    from adaptivecad.pi.kernel import PiAParams, make_adaptive_circle
except Exception:
    FreeCAD.Console.PrintWarning("adaptivecad import failed; check sys.path / Mod setup\n")
    raise


def _ask_settings(load_settings, save_settings):
    cfg = load_settings()
    dlg = QtGui.QDialog()
    dlg.setWindowTitle("PiA Settings")
    layout = QtGui.QFormLayout(dlg)
    sb_beta = QtGui.QDoubleSpinBox()
    sb_beta.setRange(0.0, 10.0)
    sb_beta.setValue(cfg.get("beta", 0.2))
    sb_beta.setDecimals(4)
    sb_s0 = QtGui.QDoubleSpinBox()
    sb_s0.setRange(1e-6, 1e6)
    sb_s0.setValue(cfg.get("s0", 1.0))
    sb_s0.setDecimals(6)
    sb_cl = QtGui.QDoubleSpinBox()
    sb_cl.setRange(0.0, 1.0)
    sb_cl.setValue(cfg.get("clamp", 0.3))
    sb_cl.setDecimals(3)
    sb_seg = QtGui.QSpinBox()
    sb_seg.setRange(8, 4096)
    sb_seg.setValue(cfg.get("segments", 128))
    layout.addRow("beta", sb_beta)
    layout.addRow("s0 (m)", sb_s0)
    layout.addRow("clamp", sb_cl)
    layout.addRow("segments", sb_seg)
    btns = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel)
    layout.addRow(btns)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    if dlg.exec_() == QtGui.QDialog.Accepted:
        cfg = {
            "beta": sb_beta.value(),
            "s0": sb_s0.value(),
            "clamp": sb_cl.value(),
            "segments": sb_seg.value(),
        }
        save_settings(cfg)
    return cfg


class _CmdAdaptiveCircle:
    def __init__(self, load_settings):
        self.load_settings = load_settings

    def Activated(self):
        cfg = self.load_settings()
        r_mm, ok = QtGui.QInputDialog.getDouble(
            None, "Adaptive Circle", "Radius (mm):", 10.0, 0.001, 1e9, 3
        )
        if not ok:
            return
        n = int(cfg.get("segments", 128))
        params = PiAParams(beta=cfg["beta"], s0=cfg["s0"], clamp=cfg["clamp"])
        pts = make_adaptive_circle(
            r_mm / 1000.0, n=n, kappa=0.0, scale=r_mm / 1000.0, params=params
        )
        vts = [FreeCAD.Vector(float(x * 1000.0), float(y * 1000.0), 0.0) for x, y in pts]
        wire = Part.makePolygon(vts + [vts[0]])
        Part.show(wire)

    def GetResources(self):
        return {"MenuText": "Adaptive Circle", "ToolTip": "Create circle with adaptive π scaling"}


class _CmdSettings:
    def __init__(self, load_settings, save_settings):
        self.load_settings = load_settings
        self.save_settings = save_settings

    def Activated(self):
        _ask_settings(self.load_settings, self.save_settings)

    def GetResources(self):
        return {"MenuText": "PiA Settings", "ToolTip": "Configure β, s₀, clamp, and segments"}


def register_commands(load_settings, save_settings):
    FreeCADGui.addCommand("PiA_AdaptiveCircle", _CmdAdaptiveCircle(load_settings))
    FreeCADGui.addCommand("PiA_Settings", _CmdSettings(load_settings, save_settings))
