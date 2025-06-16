import numpy as np

def grid_snap(world_pt, view):
    s = getattr(view, 'grid_spacing', 10.0)  # Default grid spacing if not set
    snapped = np.round(np.array(world_pt) / s) * s
    return (snapped, "#")  # '#' for grid

def endpoint_snap(world_pt, view):
    # Use all_snap_points from each feature in DOCUMENT
    from adaptivecad.commands import DOCUMENT
    for feat in DOCUMENT:
        if hasattr(feat, 'all_snap_points'):
            for pt in feat.all_snap_points():
                arr_pt = np.array(pt)
                arr_world = np.array(world_pt)
                min_dim = min(arr_pt.shape[0], arr_world.shape[0])
                d = np.linalg.norm(arr_pt[:min_dim] - arr_world[:min_dim])
                if d < getattr(view, 'snap_world_tol', 1e-3):
                    return (arr_pt, "◆")  # ◆ for endpoint
    return None
