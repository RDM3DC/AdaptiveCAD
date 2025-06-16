import numpy as np

from adaptivecad.snap_points import SNAP_TYPES

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
                d = np.linalg.norm(np.array(pt) - np.array(world_pt))
                if d < getattr(view, 'snap_world_tol', 1e-3):
                    return (np.array(pt), "◆")  # ◆ for endpoint
    return None


def midpoint_snap(world_pt, view):
    from adaptivecad.commands import DOCUMENT
    for feat in DOCUMENT:
        if hasattr(feat, 'snap_points_2d'):
            for pt, typ in feat.snap_points_2d():
                if typ != 'Midpoint':
                    continue
                d = np.linalg.norm(np.array(pt) - np.array(world_pt))
                if d < getattr(view, 'snap_world_tol', 1e-3):
                    return (np.array(pt), '●')
    return None


def center_snap(world_pt, view):
    from adaptivecad.commands import DOCUMENT
    for feat in DOCUMENT:
        if hasattr(feat, 'snap_points_2d'):
            for pt, typ in feat.snap_points_2d():
                if typ != 'Center':
                    continue
                d = np.linalg.norm(np.array(pt) - np.array(world_pt))
                if d < getattr(view, 'snap_world_tol', 1e-3):
                    return (np.array(pt), '◎')
    return None
