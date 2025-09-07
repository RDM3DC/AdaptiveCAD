# AdaptiveCAD Bench Configuration
# Target “no visible faceting” tolerance in pixels (silhouette error bound)
PX_TOL = 0.5

# Screen mapping: world unit -> pixels (for silhouette measurements)
WORLD_TO_PX = 600

# Render resolution for timing (keep modest to start)
WIDTH, HEIGHT = 640, 360

# Radii to scan (world units) for scaling tests
RADII = [0.2, 0.5, 1.0, 1.5]

# SDF ray-march settings
SDF_MAX_STEPS = 256
SDF_TMAX = 4.0  # world units
