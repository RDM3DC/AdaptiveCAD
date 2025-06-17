import numpy as np

def identity4():
    return np.eye(4)

def translation(dx, dy, dz):
    T = identity4()
    T[:3, 3] = [dx, dy, dz]
    return T

def rotation_matrix(axis, angle):
    axis = np.asarray(axis)
    axis = axis / np.linalg.norm(axis)
    x, y, z = axis
    c, s = np.cos(angle), np.sin(angle)
    C = 1 - c
    R = np.array([
        [c + x*x*C, x*y*C - z*s, x*z*C + y*s, 0],
        [y*x*C + z*s, c + y*y*C, y*z*C - x*s, 0],
        [z*x*C - y*s, z*y*C + x*s, c + z*z*C, 0],
        [0, 0, 0, 1]
    ])
    return R

def apply_transform(pt, mat):
    vec = np.append(pt, 1)
    return (mat @ vec)[:3]

def identityN(n):
    return np.eye(n+1)

def translationN(offset):
    n = len(offset)
    T = identityN(n)
    T[:-1, -1] = offset
    return T

def scalingN(factor, dim):
    """Return an N-dimensional scaling matrix."""
    import numpy as np
    if np.isscalar(factor):
        factors = [factor] * dim
    else:
        factors = list(factor)
        if len(factors) != dim:
            raise ValueError("Scaling factors length must match dimension")
    S = identityN(dim)
    for i, f in enumerate(factors):
        S[i, i] = f
    return S

def apply_transformN(pt, mat):
    vec = np.append(pt, 1)
    return (mat @ vec)[:-1]

def get_world_transform(feature, parent=None):
    T = feature.local_transform
    if parent is not None:
        T = parent.local_transform @ T
    return T


def stable_pi_a_over_pi(u: float) -> float:
    """Return a bounded πₐ/π scaling factor.

    Parameters
    ----------
    u:
        The pre-scaled input ``kappa * abs(x)`` or similar quantity.

    Returns
    -------
    float
        A scaling factor in the range [0.5, 1.5] with graceful handling of
        non-finite values.
    """
    import math

    amplitude = 0.5    # Maximum deviation from 1.0
    sensitivity = 0.1  # Controls slope of tanh around zero

    scaling = 1.0 + amplitude * math.tanh(sensitivity * u)
    if not math.isfinite(scaling):
        return 1.0
    return max(0.5, min(1.5, scaling))

def pi_a_over_pi(r: float, kappa: float = 1.0) -> float:
    """
    Ratio  πₐ(r, κ) / π  for a circle of geodesic radius *r*
    on a surface of constant Gaussian curvature *κ*.

    ▸ κ > 0  →  hyperbolic   (πₐ > π  : circumference grows faster)
    ▸ κ < 0  →  spherical    (πₐ < π  : circumference grows slower)
    ▸ κ = 0  →  Euclidean    (ratio = 1)

    Formula:
        πₐ/π =  S(√|κ| r) / (√|κ| r)

        where  S(t) = sinh(t)   if κ > 0   (hyperbolic)
                     = sin(t)    if κ < 0   (spherical)
                     = t         if κ = 0   (limit → 1)

    Edge cases r → 0 handled with 1st‑order limit.
    """
    import math
    
    if abs(r) < 1e-12 or kappa == 0.0:
        return 1.0

    root = math.sqrt(abs(kappa)) * r
    if kappa > 0:               # hyperbolic geometry  (κ = +|κ|)
        return math.sinh(root) / root
    else:                       # spherical geometry   (κ = −|κ|)
        return math.sin(root)  / root
