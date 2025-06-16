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
