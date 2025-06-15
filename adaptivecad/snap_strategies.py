import numpy as np

def grid_snap(world_pt, view):
    s = view.grid_spacing
    snapped = np.round(np.array(world_pt) / s) * s
    return (snapped, "#")  # '#' for grid

def endpoint_snap(world_pt, view):
    for pt in view.model.all_endpoints():
        d = np.linalg.norm(np.array(pt) - np.array(world_pt))
        if d < getattr(view, 'snap_world_tol', 1e-3):
            return (np.array(pt), "◆")  # ◆ for endpoint
    return None
