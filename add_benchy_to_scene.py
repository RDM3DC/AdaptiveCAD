"""Add benchy boat to current AdaptiveCAD scene via console."""

from adaptivecad.aacore.sdf import KIND_BOX, KIND_CAPSULE, Prim, Xform


def create_prim(kind, size, position, color=(0.2, 0.6, 0.8), op='solid'):
    """Helper to create primitives."""
    prim = Prim(kind=kind, params=list(size), xform=Xform(), op=op, color=color)
    prim.set_transform(pos=position)
    return prim

# Create boat parts
boat_prims = []

# Hull and deck
boat_prims.append(create_prim(KIND_BOX, [30.0, 15.0, 10.0], [0.0, 0.0, 5.0]))
boat_prims.append(create_prim(KIND_BOX, [8.0, 12.0, 10.0], [19.0, 0.0, 5.0]))
boat_prims.append(create_prim(KIND_BOX, [28.0, 13.0, 2.0], [0.0, 0.0, 11.0]))

# Cabin
boat_prims.append(create_prim(KIND_BOX, [12.0, 8.0, 8.0], [-3.0, 0.0, 16.0]))
boat_prims.append(create_prim(KIND_BOX, [13.0, 9.0, 1.5], [-3.0, 0.0, 20.75]))

# Smokestack
boat_prims.append(create_prim(KIND_CAPSULE, [1.5, 1.5, 6.0], [-3.0, 0.0, 24.5]))
boat_prims.append(create_prim(KIND_CAPSULE, [2.0, 2.0, 1.0], [-3.0, 0.0, 28.0]))

# Wheelhouse
boat_prims.append(create_prim(KIND_BOX, [6.0, 6.0, 4.0], [5.0, 0.0, 14.0]))

# Windows and door (subtract)
boat_prims.append(create_prim(KIND_CAPSULE, [1.2, 1.2, 2.0], [8.5, 0.0, 15.5], color=(0.0, 0.0, 0.0), op='subtract'))
boat_prims.append(create_prim(KIND_CAPSULE, [1.0, 1.0, 2.0], [5.0, -3.5, 15.5], color=(0.0, 0.0, 0.0), op='subtract'))
boat_prims.append(create_prim(KIND_CAPSULE, [1.0, 1.0, 2.0], [5.0, 3.5, 15.5], color=(0.0, 0.0, 0.0), op='subtract'))
boat_prims.append(create_prim(KIND_BOX, [2.0, 3.5, 1.0], [-3.0, -4.5, 14.0], color=(0.0, 0.0, 0.0), op='subtract'))

# Shaft hole
boat_prims.append(create_prim(KIND_CAPSULE, [1.0, 1.0, 12.0], [-12.0, 0.0, 3.0], color=(0.0, 0.0, 0.0), op='subtract'))

print(f"Created {len(boat_prims)} boat primitives")
print("Copy boat_prims to add to your scene!")
