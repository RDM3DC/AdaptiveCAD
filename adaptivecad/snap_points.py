SNAP_TYPES = {
    "Endpoint": True,
    "Midpoint": True,
    "Center": True,
}


def snap_points_2d(feature):
    """Return list of (point, type) snap candidates for simple features."""
    points = []
    params = getattr(feature, "params", {})
    name = getattr(feature, "name", "")
    if name == "Box":
        l = float(params.get("l", 1))
        w = float(params.get("w", 1))
        z = float(params.get("z", 0))
        corners = [[0, 0, z], [l, 0, z], [l, w, z], [0, w, z]]
        if SNAP_TYPES.get("Endpoint", False):
            points += [(pt, "Endpoint") for pt in corners]
        if SNAP_TYPES.get("Midpoint", False):
            mids = [[l/2, 0, z], [l, w/2, z], [l/2, w, z], [0, w/2, z]]
            points += [(pt, "Midpoint") for pt in mids]
        if SNAP_TYPES.get("Center", False):
            points.append(([l/2, w/2, z], "Center"))
    elif name == "Line":
        p1, p2 = params.get("points", ([0, 0, 0], [0, 0, 0]))
        if SNAP_TYPES.get("Endpoint", False):
            points.append((p1, "Endpoint"))
            points.append((p2, "Endpoint"))
        if SNAP_TYPES.get("Midpoint", False):
            mid = [(p1[i] + p2[i]) / 2 for i in range(len(p1))]
            points.append((mid, "Midpoint"))
    elif name in ("Cyl", "Circle"):
        center = params.get("center", [0, 0, 0])
        if SNAP_TYPES.get("Center", False):
            points.append((center, "Center"))
    return points
