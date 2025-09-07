import numpy as np

def circle_sdf(p, R):
    """Signed distance from 2D point(s) p to circle of radius R centered at origin.

    Parameters
    ----------
    p : np.ndarray (..., 2)
        Points.
    R : float
        Radius.
    """
    return np.linalg.norm(p, axis=-1) - R

def param_circle(R, n=2048):
    t = np.linspace(0, 2*np.pi, n)
    return R*np.cos(t), R*np.sin(t)
