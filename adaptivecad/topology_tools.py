"""Topology exploration tools for AdaptiveCAD.

This module provides utilities for analysing topological properties of
point clouds, curves and surfaces. Optional libraries such as ``gudhi``
are used if available for more accurate homology calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Dict, Iterable, List, Tuple, Set, Optional

import numpy as np

try:
    from .ndfield import NDField
    HAS_DEPENDENCIES = True
except Exception:  # pragma: no cover - optional dependency missing
    HAS_DEPENDENCIES = False


class TopologicalSpace(Enum):
    """Basic supported topological spaces."""

    EUCLIDEAN = "euclidean"
    SPHERICAL = "spherical"
    TOROIDAL = "toroidal"
    HYPERBOLIC = "hyperbolic"
    KLEIN_BOTTLE = "klein_bottle"
    MOBIUS_STRIP = "mobius_strip"


@dataclass
class TopologicalInvariant:
    """Simple container for a topological invariant."""

    name: str
    value: Any
    space_type: TopologicalSpace
    dimension: int
    description: str = ""


class HomologyCalculator:
    """Calculate Betti numbers for point clouds."""

    def __init__(self, dimension: int = 3) -> None:
        self.dimension = dimension

    def calculate_betti_numbers(self, point_cloud: np.ndarray) -> List[int]:
        """Return ``[beta0, beta1, beta2]`` for ``point_cloud``."""

        if not isinstance(point_cloud, np.ndarray) or point_cloud.ndim != 2:
            raise ValueError("point_cloud must be a 2D numpy array")

        try:
            import gudhi  # type: ignore

            rips_complex = gudhi.RipsComplex(points=point_cloud)
            simplex_tree = rips_complex.create_simplex_tree(max_dimension=2)
            persistence = simplex_tree.persistence()
            betti_0 = len([p for p in persistence if p[0] == 0 and p[1][1] == float('inf')])
            betti_1 = len([p for p in persistence if p[0] == 1 and p[1][1] == float('inf')])
            betti_2 = len([p for p in persistence if p[0] == 2 and p[1][1] == float('inf')])
            return [betti_0, betti_1, betti_2]
        except Exception:  # pragma: no cover - optional path
            return self._simplified_betti_numbers(point_cloud)

    def _simplified_betti_numbers(self, point_cloud: np.ndarray) -> List[int]:
        """Heuristic fallback for Betti numbers."""

        n_points = len(point_cloud)
        if n_points < 3:
            return [1, 0, 0]
        b0 = self._estimate_connected_components(point_cloud)
        b1 = self._estimate_loops(point_cloud)
        b2 = self._estimate_voids(point_cloud) if self.dimension >= 3 else 0
        return [b0, b1, b2]

    def _estimate_connected_components(self, points: np.ndarray) -> int:
        """Estimate connected components with a naive DFS."""

        n_points = len(points)
        threshold = np.percentile(self._pairwise_distances(points), 10)
        visited: Set[int] = set()
        components = 0
        for i in range(n_points):
            if i not in visited:
                components += 1
                self._dfs_component(i, points, threshold, visited)
        return max(1, components)

    def _dfs_component(self, start_idx: int, points: np.ndarray, threshold: float, visited: Set[int]) -> None:
        """Depth-first traversal for component detection."""
        visited.add(start_idx)
        for i in range(len(points)):
            if i not in visited:
                dist = np.linalg.norm(points[start_idx] - points[i])
                if dist < threshold:
                    self._dfs_component(i, points, threshold, visited)

    def _estimate_loops(self, points: np.ndarray) -> int:
        """Simple heuristic for 1D holes."""

        n_points = len(points)
        if n_points < 4:
            return 0
        center = np.mean(points, axis=0)
        dists = np.linalg.norm(points - center, axis=1)
        mean_dist = np.mean(dists)
        std_dist = np.std(dists)
        if std_dist < 0.3 * mean_dist and n_points > 6:
            return 1
        return 0

    def _estimate_voids(self, points: np.ndarray) -> int:
        """Heuristic for 2D voids in 3D clouds."""

        n_points = len(points)
        if n_points < 8:
            return 0
        try:
            from scipy.spatial import ConvexHull  # type: ignore

            hull = ConvexHull(points)
            density = n_points / hull.volume
            if density < 0.1:
                return 1
        except Exception:
            pass
        return 0

    def _pairwise_distances(self, points: np.ndarray) -> np.ndarray:
        """Return all pairwise distances."""

        n_points = len(points)
        distances: List[float] = []
        for i in range(n_points):
            for j in range(i + 1, n_points):
                distances.append(float(np.linalg.norm(points[i] - points[j])))
        return np.asarray(distances)


class HomotopyAnalyzer:
    """Utilities for simple homotopy analysis."""

    def __init__(self) -> None:
        self.known_spaces: Dict[TopologicalSpace, Dict[str, Any]] = {
            TopologicalSpace.EUCLIDEAN: {"pi_1": 0, "pi_2": 0},
            TopologicalSpace.SPHERICAL: {"pi_1": 0, "pi_2": 1},
            TopologicalSpace.TOROIDAL: {"pi_1": "Z x Z", "pi_2": 0},
            TopologicalSpace.KLEIN_BOTTLE: {"pi_1": "Z/2Z * Z", "pi_2": 0},
        }

    def analyze_fundamental_group(self, space_type: TopologicalSpace) -> str:
        """Return ``pi_1`` for ``space_type`` if known."""
        if space_type in self.known_spaces:
            return str(self.known_spaces[space_type]["pi_1"])
        return "Unknown"

    def analyze_loops(self, curve_points: List[np.ndarray]) -> Dict[str, Any]:
        """Return winding info for ``curve_points``."""
        if len(curve_points) < 2:
            return {"is_loop": False, "homotopy_class": None}

        first_curve = curve_points[0]
        last_curve = curve_points[-1]
        start_point = first_curve[0]
        end_point = last_curve[-1]
        is_closed = np.linalg.norm(start_point - end_point) < 1e-6
        if not is_closed:
            return {"is_loop": False, "homotopy_class": None}

        total_angle = 0.0
        center = np.mean(np.vstack(curve_points), axis=0)
        for curve in curve_points:
            for i in range(len(curve) - 1):
                p1 = curve[i] - center
                p2 = curve[i + 1] - center
                a1 = math.atan2(p1[1], p1[0])
                a2 = math.atan2(p2[1], p2[0])
                da = a2 - a1
                if da > math.pi:
                    da -= 2 * math.pi
                elif da < -math.pi:
                    da += 2 * math.pi
                total_angle += da

        winding_number = int(round(total_angle / (2 * math.pi)))
        return {
            "is_loop": True,
            "winding_number": winding_number,
            "homotopy_class": f"[\u03b3^{winding_number}]" if winding_number != 0 else "[1]",
        }

    def compute_linking_number(self, curve1: List[np.ndarray], curve2: List[np.ndarray]) -> int:
        """Approximate the Gauss linking integral for two closed curves."""
        if len(curve1) < 2 or len(curve2) < 2:
            raise ValueError("Each curve must have at least 2 points")

        n1 = len(curve1)
        n2 = len(curve2)
        linking_sum = 0.0
        for i in range(n1):
            for j in range(n2):
                r1 = curve1[i]
                r2 = curve2[j]
                dr1 = curve1[(i + 1) % n1] - r1
                dr2 = curve2[(j + 1) % n2] - r2
                r12 = r2 - r1
                norm_r12 = np.linalg.norm(r12)
                if norm_r12 > 1e-6:
                    cross_prod = np.cross(dr1, dr2)
                    dot_prod = float(np.dot(cross_prod, r12))
                    linking_sum += dot_prod / (norm_r12 ** 3)
        linking_number = linking_sum / (4 * math.pi)
        return int(round(linking_number))

    def generate_linked_curves(self, num_points: int = 100) -> Tuple[List[np.ndarray], List[np.ndarray]]:
        """Return two simple linked curves for testing."""
        t = np.linspace(0.0, 2.0 * math.pi, num_points)
        curve1 = np.array([np.cos(t), np.sin(t), np.zeros_like(t)]).T
        curve2 = np.array([np.zeros_like(t), np.cos(t), np.sin(t)]).T
        return curve1, curve2


class ManifoldAnalyzer:
    """Analyze triangulated surfaces and field defects."""

    def __init__(self) -> None:
        self.curvature_threshold = 1e-6

    def analyze_surface_topology(
        self,
        surface_points: np.ndarray,
        triangulation: List[Tuple[int, int, int]],
        is_orientable: bool = True,
    ) -> Dict[str, Any]:
        """Return Euler characteristic and surface type."""
        if (
            not isinstance(surface_points, np.ndarray)
            or surface_points.ndim != 2
            or surface_points.shape[1] != 3
        ):
            raise ValueError("surface_points must be a 2D numpy array with 3 columns")
        if not triangulation or not all(len(tri) == 3 for tri in triangulation):
            raise ValueError("triangulation must be a non-empty list of 3-tuples")

        V = len(surface_points)
        E = len(set(self._get_edges(triangulation)))
        F = len(triangulation)
        euler_char = V - E + F
        if is_orientable:
            genus = (2 - euler_char) // 2
            surface_type = f"Surface of genus {genus}" if genus >= 0 else "Unknown"
        else:
            if euler_char == 0:
                surface_type = "Klein bottle"
            elif euler_char == 1:
                surface_type = "Projective plane"
            else:
                surface_type = "Non-orientable surface"
            genus = None
        return {
            "vertices": V,
            "edges": E,
            "faces": F,
            "euler_characteristic": euler_char,
            "surface_type": surface_type,
            "genus": genus,
        }

    def _get_edges(self, triangulation: List[Tuple[int, int, int]]) -> Iterable[Tuple[int, int]]:
        """Yield unique edges from the triangle mesh."""
        edges: List[Tuple[int, int]] = []
        for tri in triangulation:
            edges.extend([
                (min(tri[0], tri[1]), max(tri[0], tri[1])),
                (min(tri[1], tri[2]), max(tri[1], tri[2])),
                (min(tri[2], tri[0]), max(tri[2], tri[0])),
            ])
        return edges

    def detect_topological_defects(self, field: NDField, defect_type: str = "vortex") -> List[Dict[str, Any]]:
        """Detect simple topological defects in a complex field."""
        if not HAS_DEPENDENCIES or field.ndim < 2:
            return []

        defects: List[Dict[str, Any]] = []
        if defect_type == "vortex" and field.ndim >= 2:
            defects = self._detect_vortices(field)
        elif defect_type == "monopole" and field.ndim >= 3:
            defects = self._detect_monopoles(field)
        elif defect_type == "skyrmion" and field.ndim >= 3:
            defects = self._detect_skyrmions(field)
        return defects

    def _detect_vortices(self, field: NDField) -> List[Dict[str, Any]]:
        """Detect vortex defects in a 2D field."""
        field_2d = field.values.reshape(field.grid_shape[:2])
        vortices: List[Dict[str, Any]] = []
        ny, nx = field_2d.shape
        for i in range(1, ny - 1):
            for j in range(1, nx - 1):
                circ = self._calculate_circulation_2d(field_2d, i, j)
                if abs(circ) > 2 * math.pi * 0.8:
                    vortices.append({
                        "position": (i, j),
                        "strength": round(circ / (2 * math.pi)),
                        "circulation": circ,
                    })
        return vortices

    def _calculate_circulation_2d(self, field: np.ndarray, i: int, j: int) -> float:
        """Calculate discrete circulation around ``(i, j)``."""
        points = [
            (i - 1, j), (i - 1, j + 1), (i, j + 1), (i + 1, j + 1),
            (i + 1, j), (i + 1, j - 1), (i, j - 1), (i - 1, j - 1), (i - 1, j)
        ]
        circ = 0.0
        for k in range(len(points) - 1):
            p1 = points[k]
            p2 = points[k + 1]
            if (
                0 <= p1[0] < field.shape[0] and 0 <= p1[1] < field.shape[1] and
                0 <= p2[0] < field.shape[0] and 0 <= p2[1] < field.shape[1]
            ):
                v1 = field[p1]
                v2 = field[p2]
                ph1 = math.atan2(v1.imag, v1.real) if hasattr(v1, 'imag') else float(v1)
                ph2 = math.atan2(v2.imag, v2.real) if hasattr(v2, 'imag') else float(v2)
                dp = ph2 - ph1
                if dp > math.pi:
                    dp -= 2 * math.pi
                elif dp < -math.pi:
                    dp += 2 * math.pi
                circ += dp
        return circ

    def _detect_monopoles(self, field: NDField) -> List[Dict[str, Any]]:
        """Placeholder for monopole detection."""
        return []

    def _detect_skyrmions(self, field: NDField) -> List[Dict[str, Any]]:
        """Placeholder for skyrmion detection."""
        return []


class TopologyExplorationCmd:
    """Example GUI command demonstrating topology tools."""

    def __init__(self) -> None:
        self.name = "Topology Exploration"

    def run(self, mw: Any) -> None:  # pragma: no cover - GUI path
        """Execute the command."""
        if not HAS_DEPENDENCIES:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                mw.win,
                "Missing Dependencies",
                "Topology exploration dependencies not available.",
            )
            return
        try:
            homology_calc = HomologyCalculator()
            homotopy_analyzer = HomotopyAnalyzer()
            manifold_analyzer = ManifoldAnalyzer()

            n_points = 100
            theta = np.linspace(0.0, 2.0 * math.pi, n_points)
            R, r = 3.0, 1.0
            x = (R + r * np.cos(theta)) * np.cos(theta)
            y = (R + r * np.cos(theta)) * np.sin(theta)
            z = r * np.sin(theta)
            torus_points = np.column_stack([x, y, z])

            try:
                import gudhi  # noqa: F401
                betti_numbers = homology_calc.calculate_betti_numbers(torus_points)
                betti_source = "gudhi"
            except Exception:
                betti_numbers = homology_calc._simplified_betti_numbers(torus_points)
                betti_source = "simplified"

            fundamental_group = homotopy_analyzer.analyze_fundamental_group(
                TopologicalSpace.TOROIDAL
            )

            field_size = (32, 32)
            y_coords, x_coords = np.mgrid[0:field_size[0], 0:field_size[1]]
            cx, cy = field_size[0] // 2, field_size[1] // 2
            dx = x_coords - cx
            dy = y_coords - cy
            theta_field = np.arctan2(dy, dx)
            vortex_field = np.exp(1j * theta_field)
            test_field = NDField(field_size, vortex_field.flatten())

            vortices = manifold_analyzer.detect_topological_defects(test_field, "vortex")

            curve1, curve2 = homotopy_analyzer.generate_linked_curves()
            linking_number = homotopy_analyzer.compute_linking_number(curve1, curve2)

            mw.win.statusBar().showMessage(
                f"Topology analysis ({betti_source}): Betti numbers {betti_numbers}, "
                f"\u03c0\u2081(Torus) = {fundamental_group}, {len(vortices)} vortices found, "
                f"linking number = {linking_number}",
                5000,
            )
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(mw.win, "Error", f"Topology exploration error: {exc}")
