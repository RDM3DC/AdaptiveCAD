import math
from typing import List, Tuple
import numpy as np

from adaptivecad.command_defs import Feature
from adaptivecad.geom.hyperbolic import pi_a_over_pi
from adaptivecad.ndfield import NDField

# Optional dependencies
try:
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.TColgp import TColgp_Array1OfPnt
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCC.Core.GeomAPI import GeomAPI_PointsToBSplineCurve
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    HAS_OCC = True
except Exception:
    HAS_OCC = False

try:
    from scipy.integrate import odeint  # type: ignore
    HAS_SCIPY = True
except Exception:
    HAS_SCIPY = False


class BizarreCurveFeature(Feature):
    """Curve with hyperbolic distortions or a Lorentz attractor trajectory."""

    def __init__(self, base_radius: float, height: float, frequency: float,
                 distortion: float, segments: int):
        params = {
            "base_radius": base_radius,
            "height": height,
            "frequency": frequency,
            "distortion": distortion,
            "segments": segments,
        }
        shape = self._make_shape(params)
        super().__init__("BizarreCurve", params, shape)

    def _lorentz_trajectory(self, segments: int) -> np.ndarray:
        sigma = 10.0
        rho = 28.0
        beta = 8.0 / 3.0

        def deriv(state, t):
            x, y, z = state
            dx = sigma * (y - x)
            dy = x * (rho - z) - y
            dz = x * y - beta * z
            return [dx, dy, dz]

        t = np.linspace(0, 40, segments)
        init = [1.0, 1.0, 1.0]
        traj = odeint(deriv, init, t)
        return traj

    def _make_shape(self, params):
        if not HAS_OCC:
            return None

        base_radius = float(params["base_radius"])
        height = float(params["height"])
        frequency = float(params["frequency"])
        distortion = float(params["distortion"])
        segments = int(params["segments"])

        points = TColgp_Array1OfPnt(1, segments)

        if HAS_SCIPY:
            traj = self._lorentz_trajectory(segments)
            mn = np.min(traj, axis=0)
            mx = np.max(traj, axis=0)
            rng = mx - mn
            rng[rng == 0] = 1.0
            scaled = (traj - mn) / rng
            scaled = scaled * [base_radius * 2, base_radius * 2, height] - [base_radius, base_radius, 0]
            for i, (x, y, z) in enumerate(scaled):
                points.SetValue(i + 1, gp_Pnt(float(x), float(y), float(z)))
        else:
            for i in range(segments):
                t = i / (segments - 1)
                angle = 2 * math.pi * frequency * t
                try:
                    hyper = pi_a_over_pi(t * distortion)
                except Exception:
                    hyper = 1.0
                x = base_radius * math.cos(angle) * hyper
                y = base_radius * math.sin(angle) * hyper
                z = height * t + distortion * math.sin(10 * angle) * math.exp(-2 * t)
                chaos_x = 0.1 * distortion * math.sin(23 * angle + t)
                chaos_y = 0.1 * distortion * math.cos(17 * angle - t)
                chaos_z = 0.05 * distortion * math.sin(13 * angle * t)
                points.SetValue(i + 1, gp_Pnt(float(x + chaos_x), float(y + chaos_y), float(z + chaos_z)))

        try:
            spline_builder = GeomAPI_PointsToBSplineCurve(points, 3, 8, False, 1e-6)
            spline = spline_builder.Curve()
            return BRepBuilderAPI_MakeEdge(spline).Edge()
        except Exception:
            wire_builder = BRepBuilderAPI_MakeWire()
            for i in range(segments - 1):
                edge = BRepBuilderAPI_MakeEdge(points.Value(i + 1), points.Value(i + 2)).Edge()
                wire_builder.Add(edge)
            return wire_builder.Wire()


class CosmicSplineFeature(Feature):
    """B-spline curve influenced by a cosmic curvature factor."""

    def __init__(self, control_points: List[Tuple[float, float, float]], degree: int, cosmic_curvature: float):
        params = {
            "control_points": control_points,
            "degree": degree,
            "cosmic_curvature": cosmic_curvature,
        }
        shape = self._make_shape(params)
        super().__init__("CosmicSpline", params, shape)

    def _make_shape(self, params):
        if not HAS_OCC:
            return None

        cps = params["control_points"]
        degree = int(params["degree"])
        curvature = float(params["cosmic_curvature"])

        transformed = []
        for x, y, z in cps:
            r = math.sqrt(x * x + y * y + z * z)
            if r > 1e-10:
                try:
                    factor = pi_a_over_pi(r * curvature)
                except Exception:
                    factor = 1.0
                scale = 1.0 + curvature * math.exp(-r / 10.0)
                transformed.append((x * factor * scale, y * factor * scale, z * factor))
            else:
                transformed.append((x, y, z))

        pts = TColgp_Array1OfPnt(1, len(transformed))
        for i, (x, y, z) in enumerate(transformed):
            pts.SetValue(i + 1, gp_Pnt(float(x), float(y), float(z)))

        try:
            deg = min(degree, len(transformed) - 1)
            spline_builder = GeomAPI_PointsToBSplineCurve(pts, deg, 8, False, 1e-6)
            spline = spline_builder.Curve()
            return BRepBuilderAPI_MakeEdge(spline).Edge()
        except Exception:
            return None


class NDFieldExplorerFeature(Feature):
    """Simple N-dimensional field visualization."""

    def __init__(self, dimensions: int, grid_size: int, field_type: str):
        params = {
            "dimensions": dimensions,
            "grid_size": grid_size,
            "field_type": field_type,
        }
        shape = self._make_shape(params)
        super().__init__("NDFieldExplorer", params, shape)

    def _make_shape(self, params):
        dimensions = int(params["dimensions"])
        grid_size = int(params["grid_size"])
        field_type = params["field_type"]

        grid_shape = [grid_size] * dimensions
        if field_type == "scalar_wave":
            values = self._generate_scalar_wave(grid_shape)
        elif field_type == "quantum_field":
            values = self._generate_quantum_field(grid_shape)
        elif field_type == "cosmic_web":
            values = self._generate_cosmic_web(grid_shape)
        else:
            values = np.random.random(grid_shape)

        self.ndfield = NDField(grid_shape, values)

        if not HAS_OCC:
            return None

        return self._create_visualization_shape(grid_size)

    def _generate_scalar_wave(self, grid_shape):
        total = int(np.prod(grid_shape))
        idx = np.unravel_index(np.arange(total), grid_shape)
        values = np.zeros(total)
        for i in range(len(grid_shape)):
            coord = idx[i] / grid_shape[i] * 2 * np.pi
            values += np.sin(coord * (i + 1))
        return values.reshape(grid_shape)

    def _generate_quantum_field(self, grid_shape):
        total = int(np.prod(grid_shape))
        real = np.random.normal(0, 1, total)
        imag = np.random.normal(0, 1, total)
        values = np.sqrt(real ** 2 + imag ** 2)
        return values.reshape(grid_shape)

    def _generate_cosmic_web(self, grid_shape):
        total = int(np.prod(grid_shape))
        idx = np.unravel_index(np.arange(total), grid_shape)
        values = np.ones(total)
        for i in range(len(grid_shape)):
            coord = idx[i] / grid_shape[i]
            values *= 1 + 0.5 * np.sin(coord * np.pi * (i + 2))
        return values.reshape(grid_shape)

    def _create_visualization_shape(self, grid_size):
        try:
            return BRepPrimAPI_MakeBox(grid_size, grid_size, grid_size).Shape()
        except Exception:
            return None

