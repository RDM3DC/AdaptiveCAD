import numpy as np
from .base import BaseCmd

class MoveWithSnapCmd(BaseCmd):
    title = "Move (Snap)"

    def run(self, mw):
        feat = mw.selected_feature()
        if feat is None:
            mw.statusBar().showMessage("Select object to move")
            return

        orig_ref = feat.get_reference_point()

        def on_mouse_move(world_pt):
            snapped, label = mw.snap_manager.snap(world_pt, mw.view)
            show_move_preview(feat, snapped or world_pt, label)

        def on_mouse_release(world_pt):
            snapped, label = mw.snap_manager.snap(world_pt, mw.view)
            dest = snapped if snapped is not None else world_pt
            delta = np.array(dest) - np.array(orig_ref)
            feat.apply_translation(delta)
            mw.rebuild_scene()

        mw.viewer.set_temp_mouse_handlers(on_mouse_move, on_mouse_release)
