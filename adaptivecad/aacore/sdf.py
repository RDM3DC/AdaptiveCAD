import numpy as np

from .math import Xform, clamp

# ---- Limits ----
MAX_PRIMS = 48  # keep in sync with shader arrays

# ---- Kinds & Ops ----
(
    KIND_NONE,
    KIND_SPHERE,
    KIND_BOX,
    KIND_CAPSULE,
    KIND_TORUS,
    KIND_MOBIUS,
    KIND_SUPERELLIPSOID,
    KIND_QUASICRYSTAL,
    KIND_TORUS4D,
    KIND_MANDELBULB,
    KIND_KLEIN,
    KIND_MENGER,
    KIND_HYPERBOLIC,
    KIND_GYROID,
    KIND_TREFOIL,
    KIND_HELICOID,
    KIND_ORBITAL,
    KIND_MESH_IMPORT,
    KIND_PI_BLOOM,
) = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18)
OP_SOLID, OP_SUBTRACT, OP_INTERSECT = 0, 1, 2


def pia_scale(r, beta):  # toy metric scaling
    return r * (1.0 + 0.125 * beta * r * r)


def _gen_laguerre(k: int, alpha: float, x: float) -> float:
    """Generalized Laguerre polynomial L_k^alpha(x) via recurrence."""

    k = int(k)
    if k <= 0:
        return 1.0
    if k == 1:
        return 1.0 + float(alpha) - float(x)
    Lkm2 = 1.0
    Lkm1 = 1.0 + float(alpha) - float(x)
    for n in range(1, k):
        # (n+1) L_{n+1} = (2n+1+alpha-x) L_n - (n+alpha) L_{n-1}
        Ln1 = ((2.0 * n + 1.0 + float(alpha) - float(x)) * Lkm1 - (n + float(alpha)) * Lkm2) / (n + 1.0)
        Lkm2, Lkm1 = Lkm1, Ln1
    return float(Lkm1)


def _real_sph_harm(l: int, m: int, theta: float, phi: float) -> float:
    """Real, orthonormal spherical harmonics for l<=3.

    Convention: m>0 uses cos(m*phi), m<0 uses sin(|m|*phi), m=0 zonal.
    """

    import math

    l = int(l)
    m = int(m)
    ct = math.cos(theta)
    st = math.sin(theta)
    if l == 0:
        return 0.2820947918
    if l == 1:
        if m == 0:
            return 0.4886025119 * ct
        if m == 1:
            return 0.4886025119 * st * math.cos(phi)
        if m == -1:
            return 0.4886025119 * st * math.sin(phi)
        return 0.0
    if l == 2:
        if m == 0:
            return 0.3153915653 * (3.0 * ct * ct - 1.0)
        if m == 1:
            return 1.0925484306 * st * ct * math.cos(phi)
        if m == -1:
            return 1.0925484306 * st * ct * math.sin(phi)
        if m == 2:
            return 0.5462742153 * st * st * math.cos(2.0 * phi)
        if m == -2:
            return 0.5462742153 * st * st * math.sin(2.0 * phi)
        return 0.0
    if l == 3:
        if m == 0:
            return 0.3731763326 * (5.0 * ct * ct * ct - 3.0 * ct)
        if m == 1:
            return 0.4570457995 * st * (5.0 * ct * ct - 1.0) * math.cos(phi)
        if m == -1:
            return 0.4570457995 * st * (5.0 * ct * ct - 1.0) * math.sin(phi)
        if m == 2:
            return 1.4453057213 * st * st * ct * math.cos(2.0 * phi)
        if m == -2:
            return 1.4453057213 * st * st * ct * math.sin(2.0 * phi)
        if m == 3:
            return 0.5900435899 * st * st * st * math.cos(3.0 * phi)
        if m == -3:
            return 0.5900435899 * st * st * st * math.sin(3.0 * phi)
        return 0.0
    return 0.0


def hydrogenic_density(p: np.ndarray, n: int, l: int, m: int) -> float:
    """Unnormalized hydrogenic orbital density |psi|^2 (a0=1).

    Intended for geometry: take an isosurface of density at a user-chosen threshold.
    """

    import math

    n = int(n)
    l = int(l)
    m = int(m)
    if n < 1:
        return 0.0
    if l < 0 or l >= n:
        return 0.0
    if abs(m) > l:
        return 0.0

    x, y, z = float(p[0]), float(p[1]), float(p[2])
    r = math.sqrt(x * x + y * y + z * z)
    r_safe = max(1e-9, r)
    theta = math.acos(max(-1.0, min(1.0, z / r_safe)))
    phi = math.atan2(y, x)

    # rho = 2r/(n a0), with a0=1
    rho = 2.0 * r_safe / float(n)
    k = n - l - 1
    alpha = 2.0 * float(l) + 1.0
    L = _gen_laguerre(k, alpha, rho)
    R = math.exp(-0.5 * rho) * (rho ** float(l)) * L
    Y = _real_sph_harm(l, m, theta, phi)
    psi = R * Y
    return float(psi * psi)


def sd_hydrogenic_orbital(p: np.ndarray, n: int, l: int, m: int, iso: float, thickness: float) -> float:
    """Distance estimate for isosurface hydrogenic_density(p)=iso.

    Uses finite-difference gradient of F(p)=density-iso:
      d ~= |F| / |grad F| - thickness
    """

    import math

    iso = float(iso)
    thickness = float(max(1e-6, thickness))

    x, y, z = float(p[0]), float(p[1]), float(p[2])
    r = math.sqrt(x * x + y * y + z * z)
    eps = 1e-3 * (1.0 + 0.25 * r)

    def F(pt: np.ndarray) -> float:
        return hydrogenic_density(pt, n, l, m) - iso

    f0 = F(p)
    ex = np.array([eps, 0.0, 0.0], dtype=np.float64)
    ey = np.array([0.0, eps, 0.0], dtype=np.float64)
    ez = np.array([0.0, 0.0, eps], dtype=np.float64)
    gx = (F(p + ex) - F(p - ex)) / (2.0 * eps)
    gy = (F(p + ey) - F(p - ey)) / (2.0 * eps)
    gz = (F(p + ez) - F(p - ez)) / (2.0 * eps)
    g = math.sqrt(gx * gx + gy * gy + gz * gz)
    g = max(g, 1e-8)
    return abs(f0) / g - thickness


# --- Primitive SDFs (local space) ---
def sd_sphere(p, r):
    return np.linalg.norm(p) - r


def sd_box(p, b):  # b = (sx,sy,sz)
    q = np.abs(p) - b
    return np.linalg.norm(np.maximum(q, 0.0)) + min(q.max(), 0.0)


def sd_capsule_y(p, r, h):  # Y-axis capsule height=h
    a = np.array([0.0, -0.5 * h, 0.0])
    b = np.array([0.0, 0.5 * h, 0.0])
    pa = p - a
    ba = b - a
    t = clamp(np.dot(pa, ba) / (np.dot(ba, ba) + 1e-12), 0.0, 1.0)
    return np.linalg.norm(pa - ba * t) - r


def sd_torus_y(p, R, r):
    qx = np.sqrt(p[0] * p[0] + p[2] * p[2]) - R
    return np.sqrt(qx * qx + p[1] * p[1]) - r


def sd_helicoid_ribbon(p, r_inner: float, r_outer: float, pitch: float, turns: float, thickness: float) -> float:
    """Approximate helicoid ribbon (solid) SDF.

    This models a thickened helicoid *surface* as a finite annulus in XY with a
    limited Z extent corresponding to `turns` revolutions.

    Params:
      r_inner, r_outer: radial bounds
      pitch: height per full turn (2π)
      turns: number of turns to include
      thickness: ribbon thickness around the surface
    """
    x, y, z = float(p[0]), float(p[1]), float(p[2])
    r = float(np.hypot(x, y))
    r_safe = max(1e-8, r)

    pitch = float(pitch)
    k = pitch / (2.0 * np.pi)
    if abs(k) < 1e-9:
        return 1e9

    theta = float(np.arctan2(y, x))  # [-pi, pi]
    u = z / k
    dtheta = u - theta
    # wrap to [-pi, pi]
    dtheta = (dtheta + np.pi) % (2.0 * np.pi) - np.pi
    d_surface = 2.0 * r_safe * float(np.sin(0.5 * abs(dtheta)))

    thickness = max(1e-6, float(thickness))
    d = d_surface - thickness

    r_in = float(min(r_inner, r_outer))
    r_out = float(max(r_inner, r_outer))
    d = max(d, r_in - r)
    d = max(d, r - r_out)

    height = abs(float(pitch)) * float(max(0.0, turns))
    z0 = -0.5 * height
    z1 = 0.5 * height
    d = max(d, z0 - z)
    d = max(d, z - z1)
    return d


def sd_torus4d(p, R1, R2, r, w_slice=0.0):
    """4D torus (duocylinder) with 3D cross-section at w=w_slice
    R1, R2 are major radii of two orthogonal circles
    r is minor radius (tube thickness)
    w_slice is the 4th dimension coordinate for cross-section
    """
    # In 4D: x²+y² and z²+w² form two perpendicular circles
    # For 3D visualization, we treat z as the 4th dimension w
    circle1_radius = np.sqrt(p[0] * p[0] + p[1] * p[1])
    circle2_radius = np.sqrt(p[2] * p[2] + w_slice * w_slice)

    # Distance to the 4D torus surface
    d1 = circle1_radius - R1
    d2 = circle2_radius - R2
    return np.sqrt(d1 * d1 + d2 * d2) - r


def sd_mandelbulb(p, power=8.0, bailout=2.0, max_iter=16):
    """3D Mandelbulb fractal distance estimation
    power: fractal power (8.0 is classic)
    bailout: escape radius
    max_iter: iteration limit for performance
    """
    z = p.copy()
    dr = 1.0
    r = 0.0

    for i in range(int(max_iter)):
        r = np.linalg.norm(z)
        if r > bailout:
            break

        # Convert to spherical coordinates (avoid singularities)
        if r < 1e-6:
            break

        theta = np.arctan2(np.sqrt(z[0] * z[0] + z[1] * z[1]), z[2])
        phi = np.arctan2(z[1], z[0])

        # Scale and rotate the point
        zr = r ** (power - 1.0)
        dr = zr * power * dr + 1.0

        # Convert back to cartesian coordinates
        zr *= r
        sin_theta = np.sin(theta * power)
        z[0] = zr * sin_theta * np.cos(phi * power)
        z[1] = zr * sin_theta * np.sin(phi * power)
        z[2] = zr * np.cos(theta * power)

        # Add original point (Mandelbulb iteration)
        z += p

    # Improved distance estimation
    if r < bailout:
        return 0.0  # Inside the set
    else:
        return 0.5 * np.log(r) * r / max(dr, 1e-6)


def sd_klein_bottle(p, a=1.0, n=2.0, t_offset=0.0):
    """Klein bottle 4D->3D projection with rotation
    a: scale parameter
    n: figure-8 parameter
    t_offset: 4D rotation phase
    """
    # Klein bottle parametric equations projected to 3D
    # Using a simplified approach for real-time rendering
    x, y, z = p[0], p[1], p[2]

    # Convert to cylindrical-ish coordinates
    r = np.sqrt(x * x + y * y)
    theta = np.arctan2(y, x)

    # Klein bottle surface approximation with 4D rotation
    u = theta + t_offset
    v = z / a

    # Simplified Klein bottle equations
    cos_u, sin_u = np.cos(u), np.sin(u)
    cos_v, sin_v = np.cos(v), np.sin(v)

    # Target surface points
    target_r = a * (2.0 + cos_u) * (1.0 + 0.5 * cos_v)
    target_z = a * sin_u * (1.0 + 0.5 * cos_v) + a * 0.5 * sin_v

    # Distance to Klein bottle surface
    dr = r - target_r
    dz = z - target_z

    return np.sqrt(dr * dr + dz * dz) - 0.1  # Small thickness


def sd_menger_sponge(p, iterations=3, size=1.0):
    """Menger sponge fractal - infinite detail CSG operations
    iterations: number of recursive subdivisions
    size: overall scale of the sponge
    """
    # Start with a box
    d = sd_box(p, np.array([size, size, size]))

    # Recursively subtract smaller boxes
    s = size
    for i in range(int(iterations)):
        # Scale for this iteration
        s /= 3.0

        # Create holes pattern for this level

        # Generate hole positions for 3x3x3 grid
        for x in [-1, 0, 1]:
            for y in [-1, 0, 1]:
                for z in [-1, 0, 1]:
                    # Skip corners (they remain solid)
                    hole_count = abs(x) + abs(y) + abs(z)
                    if hole_count >= 2:  # Remove center faces and edges
                        hole_pos = s * np.array([x, y, z])

                        # Create holes in different orientations
                        if abs(x) == 1 and y == 0 and z == 0:  # X-axis holes
                            hole_size = np.array([size * 2, s * 0.33, s * 0.33])
                        elif x == 0 and abs(y) == 1 and z == 0:  # Y-axis holes
                            hole_size = np.array([s * 0.33, size * 2, s * 0.33])
                        elif x == 0 and y == 0 and abs(z) == 1:  # Z-axis holes
                            hole_size = np.array([s * 0.33, s * 0.33, size * 2])
                        else:  # Corner holes
                            hole_size = np.array([s * 0.33, s * 0.33, s * 0.33])

                        # Subtract hole from main shape
                        hole_dist = sd_box(p - hole_pos, hole_size)
                        d = max(d, -hole_dist)  # CSG subtraction

        # Scale point for next iteration
        p_scaled = p * 3.0

        # Apply modulo operation for fractal repetition
        p_mod = np.zeros_like(p_scaled)
        for j in range(3):
            p_mod[j] = np.mod(p_scaled[j] + s * 1.5, s * 3.0) - s * 1.5

        # Continue with scaled point
        p = p_mod

    return d


def sd_hyperbolic_tiling(p, scale=1.0, order=7, symmetry=3):
    """Hyperbolic {order,symmetry} tiling projected to Poincaré disk
    order: number of sides per polygon (7 for heptagon)
    symmetry: number of polygons meeting at each vertex (3)
    scale: overall size scaling
    This creates a {7,3} tiling - the classic hyperbolic tessellation
    """
    import math

    # Transform to complex plane (x + iy)
    x, y = float(p[0]) / scale, float(p[1]) / scale
    z = complex(x, y)

    # Apply Poincaré disk model transformations
    r = abs(z)
    if r > 0.98:  # Boundary of hyperbolic disk
        return (r - 0.98) * scale

    # Hyperbolic distance from origin
    if r < 1e-6:
        hyperbolic_r = 0.0
    else:
        hyperbolic_r = math.atanh(min(r, 0.999))

    # Generate fundamental domain for {7,3} tiling
    angle = math.atan2(y, x) if r > 1e-6 else 0.0

    # Apply rotational symmetry (7-fold)
    sector_angle = 2.0 * math.pi / order
    normalized_angle = (angle % sector_angle) - sector_angle * 0.5

    # Distance to sector boundaries
    boundary_dist = abs(normalized_angle) - sector_angle * 0.5

    # Hyperbolic polygon edges using distance in Poincaré model
    edge_spacing = 0.8  # Spacing between concentric heptagons
    ring_number = int(hyperbolic_r / edge_spacing)
    dist_to_ring = abs(hyperbolic_r - ring_number * edge_spacing) - 0.05

    # Combine radial and angular distances
    angular_dist = abs(boundary_dist) * hyperbolic_r - 0.02

    # Apply hyperbolic metric correction
    metric_factor = 1.0 / (1.0 - r * r + 1e-6)

    # Final distance (minimum of radial and angular features)
    dist = min(dist_to_ring, angular_dist) * metric_factor

    # Add 3D height modulation for visualization
    z_height = float(p[2]) / scale
    height_modulation = 0.1 * math.cos(hyperbolic_r * 10.0) * math.cos(normalized_angle * order)

    return (dist + abs(z_height - height_modulation) - 0.1) * scale


def sd_mobius(p, R, w, samples=64):
    """Approximate distance to a Möbius strip centered on origin.

    Parameterization S(u,v) = A(u) + v*B(u) where
      A(u) = (R*cos(u), R*sin(u), 0)
      B(u) = (cos(u/2)*cos(u), cos(u/2)*sin(u), sin(u/2))

    For each sampled u, v* = dot(p-A, B)/dot(B,B) (clamped to [-w/2,w/2]).
    Then distance = min over u of |p - (A + v*B)|.
    """
    import math

    best = 1e18
    px, py, pz = float(p[0]), float(p[1]), float(p[2])
    for i in range(samples):
        u = 2.0 * math.pi * i / samples
        c = math.cos(u)
        s = math.sin(u)
        c2 = math.cos(u * 0.5)
        s2 = math.sin(u * 0.5)
        Ax = R * c
        Ay = R * s
        Az = 0.0
        Bx = c2 * c
        By = c2 * s
        Bz = s2
        vx = px - Ax
        vy = py - Ay
        vz = pz - Az
        bb = Bx * Bx + By * By + Bz * Bz + 1e-12
        vstar = (vx * Bx + vy * By + vz * Bz) / bb
        # clamp
        halfw = 0.5 * w
        if vstar < -halfw:
            vstar = -halfw
        if vstar > halfw:
            vstar = halfw
        sx = Ax + vstar * Bx
        sy = Ay + vstar * By
        sz = Az + vstar * Bz
        dx = px - sx
        dy = py - sy
        dz = pz - sz
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        if d < best:
            best = d
    return best


def sd_superellipsoid(p, r, power):
    """Approximate SDF for superellipsoid using L_p norm.

    r: scalar base radius; anisotropy handled by external scale in transform.
    power: p >= 1. Larger p -> boxier.
    We approximate distance as (||p||_p / r - 1) * r.
    """
    px, py, pz = abs(float(p[0])), abs(float(p[1])), abs(float(p[2]))
    pwr = max(1.0, float(power))
    rp = max(1e-6, float(r))
    val = (px**pwr + py**pwr + pz**pwr) ** (1.0 / pwr)
    return (val / rp - 1.0) * rp


def qc_value_and_bound(p, scale, dirs=None):
    """Compute quasi-crystal value f and a conservative gradient bound K.

    f(x) = sum_i cos(dot(k_i, x*scale)); with |grad f| <= sum_i |k_i|*scale
    We choose |k_i|=1 so K = n*scale.
    """
    import math

    if dirs is None:
        # 7 directions using golden angle spread
        phis = [i * 2.39996322973 for i in range(7)]  # golden angle
        dirs = [
            np.array(
                [math.cos(a) * math.sin(b), math.sin(a) * math.sin(b), math.cos(b)],
                dtype=np.float64,
            )
            for a, b in [(0.0, 0.0)]
        ]
        dirs = []
        for i in range(7):
            a = phis[i]
            z = 1.0 - 2.0 * (i + 0.5) / 7.0
            rxy = math.sqrt(max(1e-6, 1.0 - z * z))
            dirs.append(np.array([math.cos(a) * rxy, math.sin(a) * rxy, z], dtype=np.float64))
    ps = float(scale)
    f = 0.0
    for k in dirs:
        f += math.cos(ps * float(np.dot(k, p)))
    K = len(dirs) * abs(ps)
    return f, max(K, 1e-3)


# --- New Primitives ---
def sd_gyroid(p, scale=1.0, tau=0.0, thickness=0.05):
    """Approximate SDF of a gyroid TPMS shell.
    f(x,y,z) = sin(x)cos(y) + sin(y)cos(z) + sin(z)cos(x) - tau
    Distance ~ |f|/|grad f|, then offset by thickness to create shell.
    scale: frequency multiplier; tau: iso-level; thickness: half-thickness.
    """
    import math

    x, y, z = (np.asarray(p, dtype=np.float64) * float(scale)).tolist()
    sx, cx = math.sin(x), math.cos(x)
    sy, cy = math.sin(y), math.cos(y)
    sz, cz = math.sin(z), math.cos(z)
    f = sx * cy + sy * cz + sz * cx - float(tau)
    gx = cx * cy - sz * sx
    gy = cz * cy - sx * sy
    gz = cx * cz - sy * sz
    g = math.sqrt(gx * gx + gy * gy + gz * gz) + 1e-6
    sdf = abs(f) / g
    return sdf / max(1e-6, float(scale)) - float(thickness)


def sd_trefoil_knot(p, scale=1.0, tube=0.1, samples=96):
    """Approximate distance to a trefoil knot tube using sampled closest point.
    Trefoil centerline C(t) = ((2+cos 3t) cos 2t, (2+cos 3t) sin 2t, sin 3t)
    We search along t in [0,2pi) and take min distance.
    scale scales the curve; tube is tube radius.
    """
    import math

    pt = np.asarray(p, dtype=np.float64) / max(1e-6, float(scale))
    two_pi = 2.0 * math.pi
    n1 = max(24, int(samples) // 2)
    best = 1e18
    t_best = 0.0
    for i in range(n1):
        t = two_pi * (i / max(1, n1))
        c3, s3 = math.cos(3 * t), math.sin(3 * t)
        c2, s2 = math.cos(2 * t), math.sin(2 * t)
        r = 2.0 + c3
        q = np.array([r * c2, r * s2, s3], dtype=np.float64)
        d = np.linalg.norm(pt - q)
        if d < best:
            best = d
            t_best = t
    # refine around best with smaller window
    n2 = max(24, int(samples))
    window = two_pi / float(n2)
    for j in range(n2):
        t = (t_best - 0.5 * window) + (j / max(1, n2 - 1)) * window
        # wrap
        if t < 0.0:
            t += two_pi
        if t >= two_pi:
            t -= two_pi
        c3, s3 = math.cos(3 * t), math.sin(3 * t)
        c2, s2 = math.cos(2 * t), math.sin(2 * t)
        r = 2.0 + c3
        q = np.array([r * c2, r * s2, s3], dtype=np.float64)
        d = np.linalg.norm(pt - q)
        if d < best:
            best = d
    return best * float(scale) - float(tube)


def sd_pi_bloom(p, radius=1.0, bloom=0.28, petals=7.0, crown=0.22):
    """Adaptive-π bloom shell with equatorial petals and a twisted polar crown."""

    import math

    q = np.asarray(p, dtype=np.float64)
    r = float(np.linalg.norm(q))
    petals_n = max(2, int(round(float(petals))))
    bloom_raw = max(0.0, float(bloom))
    crown_raw = float(crown)
    bloom_gain = bloom_raw * max(0.0, 1.0 - 0.3 * bloom_raw * bloom_raw)

    if r < 1e-9:
        core = max(0.2, 1.0 - 0.35 * bloom_gain + 0.25 * crown_raw)
        return -float(radius) * core

    theta = math.acos(max(-1.0, min(1.0, q[2] / r)))
    phi = math.atan2(q[1], q[0])
    sin_t = math.sin(theta)
    equator = sin_t * sin_t
    petal_band = equator * (0.5 + 0.5 * equator)
    twist_gate = math.sqrt(max(sin_t, 0.0))

    petal_wave = math.sin(float(petals_n) * phi + math.pi * crown_raw * math.cos(theta))
    crown_wave = math.cos((0.5 * float(petals_n) + 1.0) * theta - 0.5 * phi)
    seam_wave = math.sin((float(petals_n) - 1.0) * phi + 2.0 * theta)

    local = 1.0 + bloom_gain * petal_band * petal_wave
    local += crown_raw * (
        0.55 * twist_gate * crown_wave
        + 0.25 * twist_gate * seam_wave
        + 0.2 * math.cos(math.pi * math.cos(theta))
    )
    local = max(0.2, min(2.5, local))
    return r - float(radius) * local


class Prim:
    def __init__(
        self, kind, params, xform=None, beta=0.0, pid=0, op="solid", color=(0.8, 0.7, 0.6)
    ):
        self.kind = kind
        self.params = np.asarray(params, dtype=np.float64)
        self.xform = xform or Xform()
        self.beta = float(beta)
        self.pid = int(pid)
        self.op = op  # 'solid' | 'subtract'
        self.color = np.asarray(color, dtype=np.float64)
        # Added Euler + non-uniform scale tracking
        self.euler = np.array([0.0, 0.0, 0.0], dtype=np.float32)  # degrees (rx, ry, rz)
        self.scale = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        # SDF modifiers (Phase 1)
        self.shell = 0.0       # shell thickness (0 = off)
        self.round = 0.0       # round radius (0 = off)
        self.twist = 0.0       # twist rate (radians per unit Y, 0 = off)
        self.bend = 0.0        # bend rate (0 = off)
        self.taper = 0.0       # taper rate along Y (0 = off)
        self.elongate = np.array([0.0, 0.0, 0.0], dtype=np.float32)  # elongation half-extents
        self.mirror = np.array([False, False, False])  # mirror axes (X, Y, Z)
        # For imported meshes
        self.mesh_sdf = None  # MeshSDF instance for KIND_MESH_IMPORT

    def set_transform(self, pos=None, euler=None, scale=None):
        from .math import rot_x, rot_y, rot_z, scale3

        if pos is None:
            pos = self.xform.M[:3, 3]
        if euler is None:
            euler = self.euler
        if scale is None:
            scale = self.scale
        S = scale3(float(scale[0]), float(scale[1]), float(scale[2]))
        Rx = rot_x(float(euler[0]))
        Ry = rot_y(float(euler[1]))
        Rz = rot_z(float(euler[2]))
        M = (S @ Rz @ Ry @ Rx).astype(np.float32)
        M[:3, 3] = np.array(pos, dtype=np.float32)
        self.xform.M = M
        self.euler[:] = euler
        self.scale[:] = scale
        # Optional: precompute inverse for shader (future optimization)
        try:
            self.xform.M_inv = np.linalg.inv(self.xform.M)
        except Exception:
            self.xform.M_inv = None


class Scene:
    def __init__(self):
        self.prims = []
        self.global_beta = 0.0
        # Added for viewport compatibility
        self.bg_color = np.array([0.06, 0.07, 0.10], dtype=np.float32)
        # Using this as a light direction/tint; shader normalizes it
        self.env_light = np.array([0.7, 1.0, 0.4], dtype=np.float32)
        self._listeners: list = []

    def on_changed(self, cb):
        if callable(cb):
            self._listeners.append(cb)

    def _notify(self):
        for cb in list(self._listeners):
            try:
                cb()
            except Exception:
                pass

    def add(self, prim):
        self.prims.append(prim)
        self._notify()
        return prim.pid

    def clear(self):
        self.prims.clear()
        self._notify()

    def remove_index(self, idx: int):
        if 0 <= idx < len(self.prims):
            self.prims.pop(idx)
            self._notify()

    def sdf(self, pw):  # CPU fold (union + subtract)
        d = 1e18
        for pr in self.prims:
            Mi = np.linalg.inv(pr.xform.M)
            pl = (Mi @ np.array([pw[0], pw[1], pw[2], 1.0]))[:3]
            if pr.kind in (KIND_SPHERE, "sphere"):
                r = pia_scale(pr.params[0], pr.beta + self.global_beta)
                di = sd_sphere(pl, r)
            elif pr.kind in (KIND_BOX, "box"):
                di = sd_box(pl, pr.params[:3]) - pr.beta
            elif pr.kind in (KIND_CAPSULE, "capsule"):
                r = pia_scale(pr.params[0], pr.beta + self.global_beta)
                di = sd_capsule_y(pl, r, pr.params[1])
            elif pr.kind in (KIND_TORUS, "torus"):
                R, r0 = pr.params[0], pr.params[1]
                r = pia_scale(r0, pr.beta + self.global_beta)
                di = sd_torus_y(pl, R, r)
            elif pr.kind in (KIND_MOBIUS, "mobius"):
                R, w = pr.params[0], pr.params[1]
                di = sd_mobius(pl, float(R), float(w), samples=64)
            elif pr.kind in (KIND_SUPERELLIPSOID, "superellipsoid"):
                r, power = pr.params[0], max(1.0, pr.params[1])
                # Allow beta to modulate soft rounding slightly
                di = sd_superellipsoid(pl, r, power)
            elif pr.kind in (KIND_QUASICRYSTAL, "quasicrystal"):
                # Params: [scale, iso, thickness, 0]
                sc, iso, th = (
                    float(pr.params[0]),
                    float(pr.params[1]),
                    float(max(1e-3, pr.params[2])),
                )
                val, K = qc_value_and_bound(pl, sc)
                di = (abs(val - iso) / max(K, 1e-6)) - th
            elif pr.kind in (KIND_TORUS4D, "torus4d"):
                # Params: [R1, R2, r, w_slice] - two major radii, minor radius, 4D slice position
                R1, R2, r = pr.params[0], pr.params[1], pr.params[2]
                w_slice = pr.params[3] if len(pr.params) > 3 else 0.0
                di = sd_torus4d(pl, R1, R2, r, w_slice)
            elif pr.kind in (KIND_MANDELBULB, "mandelbulb"):
                # Params: [power, bailout, max_iter, scale]
                power = max(2.0, pr.params[0]) if len(pr.params) > 0 else 8.0
                bailout = max(1.0, pr.params[1]) if len(pr.params) > 1 else 2.0
                max_iter = int(max(4, pr.params[2])) if len(pr.params) > 2 else 16
                scale = pr.params[3] if len(pr.params) > 3 else 1.0
                di = sd_mandelbulb(pl * scale, power, bailout, max_iter) / scale
            elif pr.kind in (KIND_KLEIN, "klein"):
                # Params: [scale, n, t_offset, thickness]
                scale = pr.params[0] if len(pr.params) > 0 else 1.0
                n = pr.params[1] if len(pr.params) > 1 else 2.0
                t_offset = pr.params[2] if len(pr.params) > 2 else 0.0
                di = sd_klein_bottle(pl, scale, n, t_offset)
            elif pr.kind in (KIND_MENGER, "menger"):
                # Params: [iterations, size, 0, 0]
                iterations = max(1, pr.params[0]) if len(pr.params) > 0 else 3
                size = max(0.1, pr.params[1]) if len(pr.params) > 1 else 1.0
                di = sd_menger_sponge(pl, iterations, size)
            elif pr.kind in (KIND_HYPERBOLIC, "hyperbolic"):
                # Params: [scale, order, symmetry, 0]
                scale = max(0.1, pr.params[0]) if len(pr.params) > 0 else 1.0
                order = max(3, pr.params[1]) if len(pr.params) > 1 else 7
                symmetry = max(3, pr.params[2]) if len(pr.params) > 2 else 3
                di = sd_hyperbolic_tiling(pl, scale, order, symmetry)
            elif pr.kind in (KIND_GYROID, "gyroid"):
                # Params: [scale, tau, thickness, 0]
                scale = pr.params[0] if len(pr.params) > 0 else 1.0
                tau = pr.params[1] if len(pr.params) > 1 else 0.0
                thickness = pr.params[2] if len(pr.params) > 2 else 0.05
                di = sd_gyroid(pl, scale, tau, thickness)
            elif pr.kind in (KIND_TREFOIL, "trefoil"):
                # Params: [scale, tube, samples, 0]
                scale = pr.params[0] if len(pr.params) > 0 else 1.0
                tube = pr.params[1] if len(pr.params) > 1 else 0.1
                samples = int(pr.params[2]) if len(pr.params) > 2 else 96
                di = sd_trefoil_knot(pl, scale, tube, samples)
            elif pr.kind in (KIND_HELICOID, "helicoid"):
                # Params: [r_inner, r_outer, pitch, turns]; thickness comes from beta
                r_inner = pr.params[0] if len(pr.params) > 0 else 0.15
                r_outer = pr.params[1] if len(pr.params) > 1 else 0.55
                pitch = pr.params[2] if len(pr.params) > 2 else 0.35
                turns = pr.params[3] if len(pr.params) > 3 else 2.0
                thickness = max(1e-6, pr.beta)
                di = sd_helicoid_ribbon(pl, r_inner, r_outer, pitch, turns, thickness)
            elif pr.kind in (KIND_ORBITAL, "orbital", "hydrogenic_orbital"):
                # Params: [n, l, m, iso]; thickness comes from beta
                n = int(pr.params[0]) if len(pr.params) > 0 else 2
                l = int(pr.params[1]) if len(pr.params) > 1 else 1
                m = int(pr.params[2]) if len(pr.params) > 2 else 0
                iso = float(pr.params[3]) if len(pr.params) > 3 else 0.02
                thickness = max(1e-6, pr.beta)
                di = sd_hydrogenic_orbital(pl, n, l, m, iso, thickness)
            elif pr.kind in (KIND_PI_BLOOM, "pi_bloom"):
                # Params: [radius, bloom, petals, crown]
                radius = pia_scale(pr.params[0], pr.beta + self.global_beta) if len(pr.params) > 0 else 1.0
                bloom = float(pr.params[1]) if len(pr.params) > 1 else 0.28
                petals = float(pr.params[2]) if len(pr.params) > 2 else 7.0
                crown = float(pr.params[3]) if len(pr.params) > 3 else 0.22
                di = sd_pi_bloom(pl, radius, bloom, petals, crown)
            elif pr.kind in (KIND_MESH_IMPORT, "mesh_import"):
                # Imported mesh SDF
                if pr.mesh_sdf is not None:
                    di = pr.mesh_sdf.evaluate(pl)
                else:
                    continue
            else:
                continue
            if pr.op == "subtract":
                d = max(d, -di)
            elif pr.op == "intersect":
                d = max(d, di)
            else:
                d = min(d, di)
        return d, -1, None

    # ---------- GPU packing ----------
    def to_gpu_structs(self, max_prims=MAX_PRIMS):
        n = min(len(self.prims), max_prims)
        kind = np.zeros(max_prims, dtype=np.int32)
        op = np.zeros(max_prims, dtype=np.int32)
        beta = np.zeros(max_prims, dtype=np.float32)
        color = np.zeros((max_prims, 3), dtype=np.float32)
        params = np.zeros((max_prims, 4), dtype=np.float32)
        xform = np.zeros((max_prims, 16), dtype=np.float32)
        xform_inv = np.zeros((max_prims, 16), dtype=np.float32)
        mod = np.zeros((max_prims, 4), dtype=np.float32)   # shell, round, twist, taper
        mod2 = np.zeros((max_prims, 4), dtype=np.float32)  # elongate xyz, mirror_flags
        for i, pr in enumerate(self.prims[:n]):
            if pr.kind in (KIND_SPHERE, "sphere"):
                kind[i] = KIND_SPHERE
                params[i] = [pr.params[0], 0, 0, 0]
            elif pr.kind in (KIND_BOX, "box"):
                kind[i] = KIND_BOX
                params[i] = [pr.params[0], pr.params[1], pr.params[2], 0]
            elif pr.kind in (KIND_CAPSULE, "capsule"):
                kind[i] = KIND_CAPSULE
                params[i] = [pr.params[0], pr.params[1], 0, 0]
            elif pr.kind in (KIND_TORUS, "torus"):
                kind[i] = KIND_TORUS
                params[i] = [pr.params[0], pr.params[1], 0, 0]
            elif pr.kind in (KIND_MOBIUS, "mobius"):
                kind[i] = KIND_MOBIUS
                params[i] = [pr.params[0], pr.params[1], 0, 0]
            elif pr.kind in (KIND_SUPERELLIPSOID, "superellipsoid"):
                kind[i] = KIND_SUPERELLIPSOID
                params[i] = [pr.params[0], pr.params[1], 0, 0]
            elif pr.kind in (KIND_QUASICRYSTAL, "quasicrystal"):
                kind[i] = KIND_QUASICRYSTAL
                params[i] = [pr.params[0], pr.params[1], pr.params[2], 0]
            elif pr.kind in (KIND_TORUS4D, "torus4d"):
                kind[i] = KIND_TORUS4D
                # Pack R1, R2, r, w_slice
                w_slice = pr.params[3] if len(pr.params) > 3 else 0.0
                params[i] = [pr.params[0], pr.params[1], pr.params[2], w_slice]
            elif pr.kind in (KIND_MANDELBULB, "mandelbulb"):
                kind[i] = KIND_MANDELBULB
                # Pack power, bailout, max_iter, scale
                power = max(2.0, pr.params[0]) if len(pr.params) > 0 else 8.0
                bailout = max(1.0, pr.params[1]) if len(pr.params) > 1 else 2.0
                max_iter = max(4, pr.params[2]) if len(pr.params) > 2 else 16
                scale = pr.params[3] if len(pr.params) > 3 else 1.0
                params[i] = [power, bailout, max_iter, scale]
            elif pr.kind in (KIND_KLEIN, "klein"):
                kind[i] = KIND_KLEIN
                # Pack scale, n, t_offset, thickness
                scale = pr.params[0] if len(pr.params) > 0 else 1.0
                n = pr.params[1] if len(pr.params) > 1 else 2.0
                t_offset = pr.params[2] if len(pr.params) > 2 else 0.0
                thickness = pr.params[3] if len(pr.params) > 3 else 0.1
                params[i] = [scale, n, t_offset, thickness]
            elif pr.kind in (KIND_MENGER, "menger"):
                kind[i] = KIND_MENGER
                # Pack iterations, size, 0, 0
                iterations = max(1, pr.params[0]) if len(pr.params) > 0 else 3
                size = max(0.1, pr.params[1]) if len(pr.params) > 1 else 1.0
                params[i] = [iterations, size, 0, 0]
            elif pr.kind in (KIND_HYPERBOLIC, "hyperbolic"):
                kind[i] = KIND_HYPERBOLIC
                # Pack scale, order, symmetry, 0
                scale = max(0.1, pr.params[0]) if len(pr.params) > 0 else 1.0
                order = max(3, pr.params[1]) if len(pr.params) > 1 else 7
                symmetry = max(3, pr.params[2]) if len(pr.params) > 2 else 3
                params[i] = [scale, order, symmetry, 0]
            elif pr.kind in (KIND_GYROID, "gyroid"):
                kind[i] = KIND_GYROID
                # Pack scale, tau, thickness, 0
                scale = pr.params[0] if len(pr.params) > 0 else 1.0
                tau = pr.params[1] if len(pr.params) > 1 else 0.0
                thickness = pr.params[2] if len(pr.params) > 2 else 0.05
                params[i] = [scale, tau, thickness, 0]
            elif pr.kind in (KIND_TREFOIL, "trefoil"):
                kind[i] = KIND_TREFOIL
                # Pack scale, tube, samples, 0 (samples as float)
                scale = pr.params[0] if len(pr.params) > 0 else 1.0
                tube = pr.params[1] if len(pr.params) > 1 else 0.1
                samples = pr.params[2] if len(pr.params) > 2 else 96
                params[i] = [scale, tube, samples, 0]
            elif pr.kind in (KIND_HELICOID, "helicoid"):
                kind[i] = KIND_HELICOID
                # Pack r_inner, r_outer, pitch, turns; thickness uses beta.
                r_inner = pr.params[0] if len(pr.params) > 0 else 0.15
                r_outer = pr.params[1] if len(pr.params) > 1 else 0.55
                pitch = pr.params[2] if len(pr.params) > 2 else 0.35
                turns = pr.params[3] if len(pr.params) > 3 else 2.0
                params[i] = [r_inner, r_outer, pitch, turns]
            elif pr.kind in (KIND_ORBITAL, "orbital", "hydrogenic_orbital"):
                kind[i] = KIND_ORBITAL
                # Pack n, l, m, iso
                n = float(pr.params[0]) if len(pr.params) > 0 else 2.0
                l = float(pr.params[1]) if len(pr.params) > 1 else 1.0
                m = float(pr.params[2]) if len(pr.params) > 2 else 0.0
                iso = float(pr.params[3]) if len(pr.params) > 3 else 0.02
                params[i] = [n, l, m, iso]
            elif pr.kind in (KIND_PI_BLOOM, "pi_bloom"):
                kind[i] = KIND_PI_BLOOM
                radius = float(pr.params[0]) if len(pr.params) > 0 else 1.0
                bloom = float(pr.params[1]) if len(pr.params) > 1 else 0.28
                petals = float(pr.params[2]) if len(pr.params) > 2 else 7.0
                crown = float(pr.params[3]) if len(pr.params) > 3 else 0.22
                params[i] = [radius, bloom, petals, crown]
            else:
                kind[i] = KIND_NONE

            if pr.op == "subtract":
                op[i] = OP_SUBTRACT
            elif pr.op == "intersect":
                op[i] = OP_INTERSECT
            else:
                op[i] = OP_SOLID
            beta[i] = np.float32(pr.beta + self.global_beta)
            color[i] = pr.color[:3].astype(np.float32)
            # Pack SDF modifiers
            mod[i] = [float(pr.shell), float(pr.round), float(pr.twist), float(pr.taper)]
            mirror_bits = (int(bool(pr.mirror[0]))
                           | (int(bool(pr.mirror[1])) << 1)
                           | (int(bool(pr.mirror[2])) << 2))
            mod2[i] = [float(pr.elongate[0]), float(pr.elongate[1]),
                        float(pr.elongate[2]), float(mirror_bits)]
            # Pack transforms column-major for GLSL compatibility
            fwd = pr.xform.M.astype(np.float32)
            try:
                inv = np.linalg.inv(fwd)
            except Exception:
                inv = np.eye(4, dtype=np.float32)
            xform[i] = fwd.flatten(order="F")
            xform_inv[i] = inv.flatten(order="F")

        return {
            "count": np.int32(n),
            "kind": kind,
            "op": op,
            "beta": beta,
            "color": color,
            "params": params,
            "xform": xform,
            "xform_inv": xform_inv,
            "mod": mod,
            "mod2": mod2,
            "bg": self.bg_color.astype(np.float32),
            "env": self.env_light.astype(np.float32),
        }
