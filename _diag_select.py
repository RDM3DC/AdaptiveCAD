"""Diagnose selection in AnalyticViewport."""
import os, sys, logging

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
logging.basicConfig(level=logging.WARNING, stream=sys.stdout)

from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from adaptivecad.gui.analytic_viewport import AnalyticViewportPanel

panel = AnalyticViewportPanel()
v = panel.view
print(f"view type: {type(v).__name__}")
print(f"view.prog: {v.prog}")
print(f"view._picking_fbo: {v._picking_fbo}")
print(f"view._pick_tex: {v._pick_tex}")
print(f"view.selected_index: {v.selected_index}")
print(f"scene prims: {len(v.scene.prims)}")
for i, p in enumerate(v.scene.prims):
    print(f"  [{i}] kind={p.kind} params={list(p.params[:2])}")
print(f"parent is panel: {v.parent() is panel}")
print(f"parent has _select_prim: {hasattr(v.parent(), '_select_prim')}")

# Try to trigger pick at center
try:
    cx, cy = v.width() // 2, v.height() // 2
    print(f"\nAttempting pick at ({cx}, {cy}), widget size=({v.width()}, {v.height()})")
    v._perform_pick(cx, cy)
    print(f"After pick: selected_index = {v.selected_index}")
except Exception as e:
    print(f"Pick failed: {e}")
    import traceback; traceback.print_exc()

# Try explicit GL context check
try:
    v.makeCurrent()
    from OpenGL.GL import glGetIntegerv, GL_FRAMEBUFFER_BINDING
    fbo = glGetIntegerv(GL_FRAMEBUFFER_BINDING)
    print(f"Current FBO binding: {fbo}")
except Exception as e:
    print(f"GL context check failed: {e}")
