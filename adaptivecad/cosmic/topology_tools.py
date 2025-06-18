"""Topology Exploration Tools for AdaptiveCAD.

Provides interactive tools for analyzing topological features, invariants,
and transformations in geometric and physical spaces.
"""

import numpy as np
import math
from typing import List, Tuple, Optional, Dict, Any, Set
from dataclasses import dataclass
from enum import Enum

try:
    from adaptivecad.ndfield import NDField
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False


class TopologicalSpace(Enum):
    """Types of topological spaces."""
    EUCLIDEAN = "euclidean"
    SPHERICAL = "spherical"
    TOROIDAL = "toroidal"
    HYPERBOLIC = "hyperbolic"
    KLEIN_BOTTLE = "klein_bottle"
    MOBIUS_STRIP = "mobius_strip"


@dataclass
class TopologicalInvariant:
    """Container for topological invariants."""
    
    name: str
    value: Any
    space_type: TopologicalSpace
    dimension: int
    description: str = ""


class HomologyCalculator:
    """Calculate homology groups and Betti numbers."""
    
    def __init__(self, dimension: int = 3):
        self.dimension = dimension
        
    def calculate_betti_numbers(self, point_cloud: np.ndarray) -> List[int]:
        """Calculate Betti numbers from point cloud data."""
        # Simplified implementation - real version would use persistent homology
        n_points = len(point_cloud)
        
        if n_points < 3:
            return [1, 0, 0]  # Just isolated points
            
        # Estimate connectivity structure
        betti_0 = self._estimate_connected_components(point_cloud)
        betti_1 = self._estimate_loops(point_cloud)
        betti_2 = self._estimate_voids(point_cloud) if self.dimension >= 3 else 0
        
        return [betti_0, betti_1, betti_2]
    
    def _estimate_connected_components(self, points: np.ndarray) -> int:
        """Estimate number of connected components."""
        # Build approximate connectivity graph
        n_points = len(points)
        threshold = np.percentile(self._pairwise_distances(points), 10)  # 10th percentile
        
        # Simple clustering approach
        visited = set()
        components = 0
        
        for i in range(n_points):
            if i not in visited:
                components += 1
                self._dfs_component(i, points, threshold, visited)
                
        return max(1, components)
    
    def _estimate_loops(self, points: np.ndarray) -> int:
        """Estimate number of 1-dimensional holes (loops)."""
        # Very simplified - look for roughly circular arrangements
        n_points = len(points)
        if n_points < 4:
            return 0
            
        # Calculate center of mass
        center = np.mean(points, axis=0)
        
        # Check for points arranged in circular patterns
        distances = np.linalg.norm(points - center, axis=1)
        
        # Look for consistent distances (circular arrangement)
        mean_dist = np.mean(distances)
        std_dist = np.std(distances)
        
        # If points are roughly equidistant from center, might be a loop
        if std_dist < 0.3 * mean_dist and n_points > 6:
            return 1
        
        return 0
    
    def _estimate_voids(self, points: np.ndarray) -> int:
        """Estimate number of 2-dimensional holes (voids)."""
        # Very simplified - look for hollow regions
        n_points = len(points)
        if n_points < 8:
            return 0
            
        # Calculate convex hull volume vs point density
        try:
            from scipy.spatial import ConvexHull
            hull = ConvexHull(points)
            hull_volume = hull.volume
            
            # Estimate if interior is sparse (indicating void)
            point_density = n_points / hull_volume
            
            # If density is very low, might have voids
            if point_density < 0.1:
                return 1
        except:
            pass
            
        return 0
    
    def _pairwise_distances(self, points: np.ndarray) -> np.ndarray:
        """Calculate all pairwise distances."""
        n_points = len(points)
        distances = []
        
        for i in range(n_points):
            for j in range(i+1, n_points):
                dist = np.linalg.norm(points[i] - points[j])
                distances.append(dist)
                
        return np.array(distances)
    
    def _dfs_component(self, start_idx: int, points: np.ndarray, 
                      threshold: float, visited: Set[int]):
        """Depth-first search for connected component."""
        visited.add(start_idx)
        
        for i in range(len(points)):
            if i not in visited:
                dist = np.linalg.norm(points[start_idx] - points[i])
                if dist < threshold:
                    self._dfs_component(i, points, threshold, visited)


class HomotopyAnalyzer:
    """Analyze homotopy groups and fundamental groups."""
    
    def __init__(self):
        self.known_spaces = {
            TopologicalSpace.EUCLIDEAN: {"pi_1": 0, "pi_2": 0},
            TopologicalSpace.SPHERICAL: {"pi_1": 0, "pi_2": 1},
            TopologicalSpace.TOROIDAL: {"pi_1": "Z x Z", "pi_2": 0},
            TopologicalSpace.KLEIN_BOTTLE: {"pi_1": "Z/2Z * Z", "pi_2": 0},
        }
    
    def analyze_fundamental_group(self, space_type: TopologicalSpace) -> str:
        """Get fundamental group π₁ for known topological spaces."""
        if space_type in self.known_spaces:
            return str(self.known_spaces[space_type]["pi_1"])
        return "Unknown"
    
    def analyze_loops(self, curve_points: List[np.ndarray]) -> Dict[str, Any]:
        """Analyze loops and their homotopy classes."""
        if len(curve_points) < 2:
            return {"is_loop": False, "homotopy_class": None}
            
        first_curve = curve_points[0]
        last_curve = curve_points[-1]
        
        # Check if curve is closed
        start_point = first_curve[0]
        end_point = last_curve[-1]
        
        is_closed = np.linalg.norm(start_point - end_point) < 1e-6
        
        if not is_closed:
            return {"is_loop": False, "homotopy_class": None}
        
        # Simplified homotopy analysis
        # Real implementation would compute linking numbers, winding numbers, etc.
        
        # Calculate total "winding" around z-axis (2D projection)
        total_angle = 0.0
        center = np.mean(np.vstack(curve_points), axis=0)
        
        for curve in curve_points:
            for i in range(len(curve) - 1):
                p1 = curve[i] - center
                p2 = curve[i+1] - center
                
                # Angle in xy-plane
                angle1 = math.atan2(p1[1], p1[0])
                angle2 = math.atan2(p2[1], p2[0])
                
                angle_diff = angle2 - angle1
                
                # Handle angle wrapping
                if angle_diff > math.pi:
                    angle_diff -= 2*math.pi
                elif angle_diff < -math.pi:
                    angle_diff += 2*math.pi
                    
                total_angle += angle_diff
        
        winding_number = int(round(total_angle / (2*math.pi)))
        
        return {
            "is_loop": True,
            "winding_number": winding_number,
            "homotopy_class": f"[γ^{winding_number}]" if winding_number != 0 else "[1]"
        }


class ManifoldAnalyzer:
    """Analyze differential geometric properties of manifolds."""
    
    def __init__(self):
        self.curvature_threshold = 1e-6
        
    def analyze_surface_topology(self, surface_points: np.ndarray,
                                triangulation: List[Tuple[int, int, int]]) -> Dict[str, Any]:
        """Analyze topological properties of a triangulated surface."""
        V = len(surface_points)  # Vertices
        E = len(set(self._get_edges(triangulation)))  # Edges
        F = len(triangulation)  # Faces
        
        # Euler characteristic
        euler_char = V - E + F
        
        # Classify surface based on Euler characteristic
        surface_type = self._classify_surface_by_euler(euler_char)
        
        # Calculate genus (for closed orientable surfaces)
        genus = (2 - euler_char) // 2 if euler_char <= 2 else 0
        
        return {
            "vertices": V,
            "edges": E,
            "faces": F,
            "euler_characteristic": euler_char,
            "surface_type": surface_type,
            "genus": genus
        }
    
    def _get_edges(self, triangulation: List[Tuple[int, int, int]]) -> List[Tuple[int, int]]:
        """Extract edges from triangle mesh."""
        edges = []
        for tri in triangulation:
            edges.extend([
                (min(tri[0], tri[1]), max(tri[0], tri[1])),
                (min(tri[1], tri[2]), max(tri[1], tri[2])),
                (min(tri[2], tri[0]), max(tri[2], tri[0]))
            ])
        return edges
    
    def _classify_surface_by_euler(self, euler_char: int) -> str:
        """Classify surface type by Euler characteristic."""
        if euler_char == 2:
            return "Sphere"
        elif euler_char == 0:
            return "Torus"
        elif euler_char == 1:
            return "Projective Plane"
        elif euler_char < 0:
            return f"Surface of genus {(2 - euler_char) // 2}"
        else:
            return "Unknown surface"
    
    def detect_topological_defects(self, field: NDField, 
                                  defect_type: str = "vortex") -> List[Dict[str, Any]]:
        """Detect topological defects in field configurations."""
        if field.ndim < 2:
            return []
            
        defects = []
        
        if defect_type == "vortex" and field.ndim >= 2:
            defects = self._detect_vortices(field)
        elif defect_type == "monopole" and field.ndim >= 3:
            defects = self._detect_monopoles(field)
        elif defect_type == "skyrmion" and field.ndim >= 3:
            defects = self._detect_skyrmions(field)
            
        return defects
    
    def _detect_vortices(self, field: NDField) -> List[Dict[str, Any]]:
        """Detect vortex defects in 2D field."""
        # Simplified vortex detection
        field_2d = field.values.reshape(field.grid_shape[:2])
        vortices = []
        
        # Look for points where field circulation is non-zero
        ny, nx = field_2d.shape
        
        for i in range(1, ny-1):
            for j in range(1, nx-1):
                # Calculate circulation around point
                circulation = self._calculate_circulation_2d(field_2d, i, j)
                
                if abs(circulation) > 2*math.pi * 0.8:  # Threshold for vortex
                    vortex_strength = circulation / (2*math.pi)
                    vortices.append({
                        "position": (i, j),
                        "strength": round(vortex_strength),
                        "circulation": circulation
                    })
                    
        return vortices
    
    def _calculate_circulation_2d(self, field: np.ndarray, i: int, j: int) -> float:
        """Calculate circulation around a point in 2D field."""
        # Sample points around (i,j) in a small loop
        points = [
            (i-1, j), (i-1, j+1), (i, j+1), (i+1, j+1),
            (i+1, j), (i+1, j-1), (i, j-1), (i-1, j-1), (i-1, j)
        ]
        
        circulation = 0.0
        for k in range(len(points)-1):
            p1 = points[k]
            p2 = points[k+1]
            
            if (0 <= p1[0] < field.shape[0] and 0 <= p1[1] < field.shape[1] and
                0 <= p2[0] < field.shape[0] and 0 <= p2[1] < field.shape[1]):
                
                # Treat field values as phases
                phase1 = math.atan2(field[p1].imag, field[p1].real) if hasattr(field[p1], 'imag') else field[p1]
                phase2 = math.atan2(field[p2].imag, field[p2].real) if hasattr(field[p2], 'imag') else field[p2]
                
                phase_diff = phase2 - phase1
                
                # Handle phase wrapping
                if phase_diff > math.pi:
                    phase_diff -= 2*math.pi
                elif phase_diff < -math.pi:
                    phase_diff += 2*math.pi
                    
                circulation += phase_diff
                
        return circulation
    
    def _detect_monopoles(self, field: NDField) -> List[Dict[str, Any]]:
        """Detect monopole defects in 3D field."""
        # Simplified monopole detection
        return []  # Placeholder
    
    def _detect_skyrmions(self, field: NDField) -> List[Dict[str, Any]]:
        """Detect skyrmion defects in 3D field."""
        # Simplified skyrmion detection
        return []  # Placeholder


# Integration with AdaptiveCAD
class TopologyExplorationCmd:
    """Command to add topology exploration tools to AdaptiveCAD."""
    
    def __init__(self):
        self.name = "Topology Exploration"
        
    def run(self, mw):
        """Add topology exploration tools to the main window."""
        if not HAS_DEPENDENCIES:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(mw.win, "Missing Dependencies", 
                              "Topology exploration dependencies not available.")
            return
            
        try:
            # Create topology analyzers
            homology_calc = HomologyCalculator()
            homotopy_analyzer = HomotopyAnalyzer()
            manifold_analyzer = ManifoldAnalyzer()
            
            # Generate sample point cloud
            n_points = 100
            theta = np.linspace(0, 2*np.pi, n_points)
            # Torus-like point cloud
            R, r = 3.0, 1.0
            x = (R + r*np.cos(theta)) * np.cos(theta)
            y = (R + r*np.cos(theta)) * np.sin(theta)
            z = r * np.sin(theta)
            
            torus_points = np.column_stack([x, y, z])
            
            # Analyze topology
            betti_numbers = homology_calc.calculate_betti_numbers(torus_points)
            
            # Analyze fundamental group for torus
            fundamental_group = homotopy_analyzer.analyze_fundamental_group(TopologicalSpace.TOROIDAL)
            
            # Create sample field with vortices
            field_size = (32, 32)
            field_values = np.random.complex128(field_size)
            
            # Add a vortex at center
            center_x, center_y = field_size[0]//2, field_size[1]//2
            y_coords, x_coords = np.mgrid[0:field_size[0], 0:field_size[1]]
            
            # Create vortex field
            dx = x_coords - center_x
            dy = y_coords - center_y
            r = np.sqrt(dx**2 + dy**2)
            theta_field = np.arctan2(dy, dx)
            
            vortex_field = np.exp(1j * theta_field)  # Single vortex
            test_field = NDField(field_size, vortex_field.flatten())
            
            # Detect topological defects
            vortices = manifold_analyzer.detect_topological_defects(test_field, "vortex")
            
            mw.win.statusBar().showMessage(
                f"Topology analysis: Betti numbers {betti_numbers}, "
                f"π₁(Torus) = {fundamental_group}, {len(vortices)} vortices found", 5000
            )
            
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(mw.win, "Error", f"Topology exploration error: {str(e)}")
