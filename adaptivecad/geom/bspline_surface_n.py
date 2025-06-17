"""N-dimensional B-spline surface fitting from point cloud (for AdaptiveCAD)."""
import numpy as np
from adaptivecad.vecn import VecN

class BSplineCurveN:
    def __init__(self, control_points, degree, knots):
        self.control_points = control_points  # list of VecN
        self.degree = degree
        self.knots = knots
        self.n = len(control_points)

    def evaluate(self, u):
        # de Boor's algorithm (vectorized for VecN)
        k = self.degree
        knots = self.knots
        cp = self.control_points
        n = self.n
        # Find knot span
        m = len(knots) - 1
        if u >= knots[-1]:
            i = n - 1
        else:
            for idx in range(k, n):
                if knots[idx] <= u < knots[idx+1]:
                    i = idx
                    break
            else:
                i = n - 1
        d = [cp[j] for j in range(i - k, i + 1)]
        for r in range(1, k + 1):
            for j in range(k, r - 1, -1):
                alpha = 0.0
                denom = knots[i + j + 1 - r] - knots[i + j - k]
                if denom != 0:
                    alpha = (u - knots[i + j - k]) / denom
                d[j] = d[j - 1] * (1 - alpha) + d[j] * alpha
        return d[k]

class BSplineSurfaceN:
    def __init__(self, control_points_grid, degree_u, degree_v, knots_u, knots_v):
        self.control_points = control_points_grid  # 2D list: [ [VecN, ...], ... ]
        self.degree_u = degree_u
        self.degree_v = degree_v
        self.knots_u = knots_u
        self.knots_v = knots_v
        self.n_u = len(control_points_grid)
        self.n_v = len(control_points_grid[0])

    def evaluate(self, u, v):
        """Evaluate surface at normalized (u,v) in [0,1]×[0,1]."""
        temp = []
        for j in range(self.n_v):
            col = [self.control_points[i][j] for i in range(self.n_u)]
            curve = BSplineCurveN(col, self.degree_u, self.knots_u)
            temp.append(curve.evaluate(u))
        cross_curve = BSplineCurveN(temp, self.degree_v, self.knots_v)
        return cross_curve.evaluate(v)

def pca_uv(points):
    # points: list of VecN
    X = np.array([p.coords for p in points])
    X_mean = X.mean(axis=0)
    Xc = X - X_mean
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    uv = Xc @ Vt[:2].T  # First two principal components
    u = (uv[:,0] - uv[:,0].min()) / (uv[:,0].max() - uv[:,0].min() + 1e-12)
    v = (uv[:,1] - uv[:,1].min()) / (uv[:,1] - uv[:,1].min() + 1e-12)
    return list(zip(u, v))

def open_uniform_knots(n, p):
    knots = [0]*p + list(np.linspace(0,1,n-p+1)) + [1]*p
    return knots

def bspline_basis(i, p, knots, u):
    # Cox-de Boor recursion (scalar version)
    if p == 0:
        return 1.0 if knots[i] <= u < knots[i+1] else 0.0
    left = 0.0
    if knots[i+p] > knots[i]:
        left = (u - knots[i])/(knots[i+p] - knots[i]) * bspline_basis(i, p-1, knots, u)
    right = 0.0
    if knots[i+p+1] > knots[i+1]:
        right = (knots[i+p+1] - u)/(knots[i+p+1] - knots[i+1]) * bspline_basis(i+1, p-1, knots, u)
    return left + right

def fit_bspline_surface(points, uv_params, grid_shape=(10,10), degree=3, reg=0.0):
    n_u, n_v = grid_shape
    knots_u = open_uniform_knots(n_u, degree)
    knots_v = open_uniform_knots(n_v, degree)
    N = len(points)
    D = len(points[0])
    A = np.zeros((N, n_u * n_v))
    for k, (u, v) in enumerate(uv_params):
        for i in range(n_u):
            bu = bspline_basis(i, degree, knots_u, u)
            for j in range(n_v):
                bv = bspline_basis(j, degree, knots_v, v)
                A[k, i*n_v + j] = bu * bv
    rhs = np.array([p.coords for p in points])
    # Regularized least squares: (A^T A + reg*I) X = A^T rhs
    ATA = A.T @ A
    if reg > 0:
        ATA += reg * np.eye(ATA.shape[0])
    ATb = A.T @ rhs
    X = np.linalg.solve(ATA, ATb)
    ctrl_pts = []
    for i in range(n_u):
        row = []
        for j in range(n_v):
            row.append(VecN(X[i*n_v + j]))
        ctrl_pts.append(row)
    return BSplineSurfaceN(ctrl_pts, degree, degree, knots_u, knots_v)

def from_stl_mesh(filename):
    from adaptivecad.simple_stl import load_stl
    tris = load_stl(filename)
    points = [VecN(v) for tri in tris for v in tri]
    return points
