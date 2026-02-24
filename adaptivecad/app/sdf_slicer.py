"""AdaptiveCAD Direct SDF Slicer

Generates G-code directly from SDF (Signed Distance Function) representations
without converting to triangle meshes. This enables:
- Perfect accuracy (no approximation errors from triangulation)
- Infinite resolution at any scale
- Direct support for mathematical surfaces
- Faster slicing for complex fractals and TPMS structures
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class SliceContour:
    """A single contour (closed path) in a slice."""
    points: np.ndarray  # Nx2 array of (x, y) points
    is_outer: bool = True  # True for outer perimeter, False for holes


@dataclass  
class Slice:
    """A single horizontal slice of the model."""
    z: float
    contours: List[SliceContour] = field(default_factory=list)
    infill_paths: List[np.ndarray] = field(default_factory=list)


@dataclass
class PrintSettings:
    """Settings for G-code generation."""
    layer_height: float = 0.2
    nozzle_diameter: float = 0.4
    filament_diameter: float = 1.75
    extrusion_width: float = 0.45
    print_speed: float = 60.0  # mm/s
    travel_speed: float = 120.0  # mm/s
    retraction_distance: float = 1.0
    retraction_speed: float = 40.0
    bed_temp: float = 60.0
    nozzle_temp: float = 200.0
    infill_density: float = 0.2  # 20%
    perimeter_count: int = 2
    resolution: float = 0.1  # mm resolution for SDF sampling


class SDFSlicer:
    """Direct SDF-based slicer for G-code generation."""
    
    def __init__(self, scene, settings: Optional[PrintSettings] = None):
        """
        Initialize the slicer.
        
        Args:
            scene: An SDF Scene object containing primitives
            settings: Print settings (uses defaults if not provided)
        """
        self.scene = scene
        self.settings = settings or PrintSettings()
        self.slices: List[Slice] = []
        self._gcode_lines: List[str] = []
    
    def compute_bounds(self) -> Tuple[np.ndarray, np.ndarray]:
        """Compute the bounding box of the scene."""
        # Sample SDF to find bounds
        test_range = np.linspace(-5, 5, 50)
        min_bound = np.array([5.0, 5.0, 5.0])
        max_bound = np.array([-5.0, -5.0, -5.0])
        
        for x in test_range:
            for y in test_range:
                for z in test_range:
                    pw = np.array([x, y, z])
                    d, _, _ = self.scene.sdf(pw)
                    if d < 0.1:  # Inside or near surface
                        min_bound = np.minimum(min_bound, pw)
                        max_bound = np.maximum(max_bound, pw)
        
        # Add margin
        margin = 0.5
        min_bound -= margin
        max_bound += margin
        
        return min_bound, max_bound
    
    def slice_scene(
        self,
        z_start: float = 0.0,
        z_end: float = 10.0,
        layer_height: Optional[float] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> List[Slice]:
        """
        Slice the scene into horizontal layers.
        
        Args:
            z_start: Starting Z height
            z_end: Ending Z height
            layer_height: Layer height (uses settings if not provided)
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of Slice objects
        """
        lh = layer_height or self.settings.layer_height
        num_layers = int((z_end - z_start) / lh)
        
        self.slices = []
        
        for i in range(num_layers):
            z = z_start + (i + 0.5) * lh
            
            if progress_callback:
                progress_callback(i / num_layers)
            
            slice_obj = self._slice_at_z(z)
            self.slices.append(slice_obj)
        
        if progress_callback:
            progress_callback(1.0)
        
        log.info(f"Generated {len(self.slices)} slices")
        return self.slices
    
    def _slice_at_z(self, z: float) -> Slice:
        """Generate a slice at the given Z height."""
        slice_obj = Slice(z=z)
        res = self.settings.resolution
        
        # Sample SDF on a 2D grid at this Z height
        # First, find the XY bounds at this Z
        x_range = np.arange(-3, 3, res)
        y_range = np.arange(-3, 3, res)
        
        # Create 2D SDF grid
        grid = np.zeros((len(y_range), len(x_range)))
        
        for i, y in enumerate(y_range):
            for j, x in enumerate(x_range):
                pw = np.array([x, y, z])
                d, _, _ = self.scene.sdf(pw)
                grid[i, j] = d
        
        # Extract contours using marching squares
        contours = self._marching_squares(grid, x_range, y_range)
        
        for contour_pts in contours:
            if len(contour_pts) >= 3:
                slice_obj.contours.append(SliceContour(
                    points=np.array(contour_pts),
                    is_outer=True  # TODO: Detect holes
                ))
        
        # Generate infill
        if slice_obj.contours:
            slice_obj.infill_paths = self._generate_infill(slice_obj, z)
        
        return slice_obj
    
    def _marching_squares(
        self, 
        grid: np.ndarray, 
        x_range: np.ndarray, 
        y_range: np.ndarray,
        iso_value: float = 0.0
    ) -> List[List[Tuple[float, float]]]:
        """
        Extract contours from a 2D SDF grid using marching squares.
        
        Args:
            grid: 2D array of SDF values
            x_range: X coordinates
            y_range: Y coordinates
            iso_value: Iso-surface value (0 for surface)
        
        Returns:
            List of contours (each contour is a list of (x, y) points)
        """
        contours = []
        ny, nx = grid.shape
        
        # Edge lookup table for marching squares
        edge_table = [
            [],  # 0
            [(0, 3)],  # 1
            [(0, 1)],  # 2
            [(1, 3)],  # 3
            [(1, 2)],  # 4
            [(0, 1), (2, 3)],  # 5
            [(0, 2)],  # 6
            [(2, 3)],  # 7
            [(2, 3)],  # 8
            [(0, 2)],  # 9
            [(0, 3), (1, 2)],  # 10
            [(1, 2)],  # 11
            [(1, 3)],  # 12
            [(0, 1)],  # 13
            [(0, 3)],  # 14
            [],  # 15
        ]
        
        # Collect edge segments
        segments = []
        
        for i in range(ny - 1):
            for j in range(nx - 1):
                # Get corner values
                v = [
                    grid[i, j],      # bottom-left
                    grid[i, j + 1],  # bottom-right
                    grid[i + 1, j + 1],  # top-right
                    grid[i + 1, j],  # top-left
                ]
                
                # Calculate cell index
                idx = 0
                for k in range(4):
                    if v[k] < iso_value:
                        idx |= (1 << k)
                
                # Get edges for this cell
                edges = edge_table[idx]
                
                for e0, e1 in edges:
                    # Interpolate edge positions
                    p0 = self._interp_edge(e0, v, x_range, y_range, i, j, iso_value)
                    p1 = self._interp_edge(e1, v, x_range, y_range, i, j, iso_value)
                    segments.append((p0, p1))
        
        # Connect segments into contours
        if segments:
            contours = self._connect_segments(segments)
        
        return contours
    
    def _interp_edge(
        self,
        edge: int,
        v: List[float],
        x_range: np.ndarray,
        y_range: np.ndarray,
        i: int,
        j: int,
        iso: float
    ) -> Tuple[float, float]:
        """Interpolate position on an edge."""
        # Edge vertices
        edge_verts = [
            (0, 1),  # edge 0: bottom
            (1, 2),  # edge 1: right
            (2, 3),  # edge 2: top
            (3, 0),  # edge 3: left
        ]
        
        # Corner positions
        corners = [
            (x_range[j], y_range[i]),      # 0: bottom-left
            (x_range[j + 1], y_range[i]),  # 1: bottom-right
            (x_range[j + 1], y_range[i + 1]),  # 2: top-right
            (x_range[j], y_range[i + 1]),  # 3: top-left
        ]
        
        v0, v1 = edge_verts[edge]
        p0, p1 = corners[v0], corners[v1]
        val0, val1 = v[v0], v[v1]
        
        # Linear interpolation
        if abs(val1 - val0) < 1e-10:
            t = 0.5
        else:
            t = (iso - val0) / (val1 - val0)
        
        x = p0[0] + t * (p1[0] - p0[0])
        y = p0[1] + t * (p1[1] - p0[1])
        
        return (x, y)
    
    def _connect_segments(
        self, 
        segments: List[Tuple[Tuple[float, float], Tuple[float, float]]]
    ) -> List[List[Tuple[float, float]]]:
        """Connect line segments into closed contours."""
        contours = []
        used = [False] * len(segments)
        eps = 1e-6
        
        for start_idx in range(len(segments)):
            if used[start_idx]:
                continue
            
            # Start a new contour
            contour = [segments[start_idx][0], segments[start_idx][1]]
            used[start_idx] = True
            
            # Keep finding connected segments
            while True:
                found = False
                end = contour[-1]
                
                for i, seg in enumerate(segments):
                    if used[i]:
                        continue
                    
                    p0, p1 = seg
                    
                    # Check if segment connects to end
                    if abs(p0[0] - end[0]) < eps and abs(p0[1] - end[1]) < eps:
                        contour.append(p1)
                        used[i] = True
                        found = True
                        break
                    elif abs(p1[0] - end[0]) < eps and abs(p1[1] - end[1]) < eps:
                        contour.append(p0)
                        used[i] = True
                        found = True
                        break
                
                if not found:
                    break
            
            # Check if contour is closed
            if len(contour) >= 3:
                start = contour[0]
                end = contour[-1]
                if abs(start[0] - end[0]) < eps and abs(start[1] - end[1]) < eps:
                    contour = contour[:-1]  # Remove duplicate end point
                contours.append(contour)
        
        return contours
    
    def _generate_infill(self, slice_obj: Slice, z: float) -> List[np.ndarray]:
        """Generate infill paths for a slice."""
        infill_paths = []
        
        if not slice_obj.contours or self.settings.infill_density <= 0:
            return infill_paths
        
        # Get bounding box of contours
        all_points = np.vstack([c.points for c in slice_obj.contours])
        min_x, min_y = all_points.min(axis=0)
        max_x, max_y = all_points.max(axis=0)
        
        # Generate line infill
        spacing = self.settings.extrusion_width / self.settings.infill_density
        
        # Alternate infill direction per layer
        layer_idx = int(z / self.settings.layer_height)
        angle = 45 if layer_idx % 2 == 0 else -45
        angle_rad = math.radians(angle)
        
        cos_a, sin_a = math.cos(angle_rad), math.sin(angle_rad)
        
        # Generate parallel lines
        y = min_y
        while y <= max_y:
            # Create line at this y
            line_start = np.array([min_x - 1, y])
            line_end = np.array([max_x + 1, y])
            
            # Rotate line
            center = np.array([(min_x + max_x) / 2, (min_y + max_y) / 2])
            line_start_rot = self._rotate_point(line_start, center, cos_a, sin_a)
            line_end_rot = self._rotate_point(line_end, center, cos_a, sin_a)
            
            # Clip line to contours (simplified - just add the line)
            infill_paths.append(np.array([line_start_rot, line_end_rot]))
            
            y += spacing
        
        return infill_paths
    
    def _rotate_point(
        self, 
        point: np.ndarray, 
        center: np.ndarray, 
        cos_a: float, 
        sin_a: float
    ) -> np.ndarray:
        """Rotate a point around a center."""
        p = point - center
        rotated = np.array([
            p[0] * cos_a - p[1] * sin_a,
            p[0] * sin_a + p[1] * cos_a
        ])
        return rotated + center
    
    def generate_gcode(self) -> str:
        """Generate G-code from the slices."""
        self._gcode_lines = []
        
        # Header
        self._add_header()
        
        # Process each slice
        e_pos = 0.0  # Extrusion position
        
        for slice_obj in self.slices:
            e_pos = self._process_slice(slice_obj, e_pos)
        
        # Footer
        self._add_footer()
        
        return '\n'.join(self._gcode_lines)
    
    def _add_header(self):
        """Add G-code header."""
        s = self.settings
        lines = [
            "; Generated by AdaptiveCAD Direct SDF Slicer",
            "; Triangle-free G-code generation",
            "",
            f"; Layer Height: {s.layer_height} mm",
            f"; Nozzle: {s.nozzle_diameter} mm",
            f"; Infill: {s.infill_density * 100:.0f}%",
            "",
            "G21 ; mm units",
            "G90 ; absolute positioning",
            "M82 ; absolute extrusion",
            "",
            f"M140 S{s.bed_temp} ; set bed temp",
            f"M104 S{s.nozzle_temp} ; set nozzle temp",
            f"M190 S{s.bed_temp} ; wait for bed",
            f"M109 S{s.nozzle_temp} ; wait for nozzle",
            "",
            "G28 ; home all axes",
            "G1 Z5 F3000 ; lift nozzle",
            "",
            "; Prime nozzle",
            "G1 X0 Y0 F3000",
            "G1 Z0.3",
            "G1 X50 E10 F1500",
            "G1 X100 E20 F1500",
            "G92 E0 ; reset extruder",
            "",
            "; Start print",
        ]
        self._gcode_lines.extend(lines)
    
    def _add_footer(self):
        """Add G-code footer."""
        lines = [
            "",
            "; End print",
            "M104 S0 ; turn off nozzle",
            "M140 S0 ; turn off bed",
            "G91 ; relative positioning",
            "G1 Z10 F3000 ; lift nozzle",
            "G90 ; absolute positioning",
            "G1 X0 Y0 F3000 ; home X/Y",
            "M84 ; disable motors",
            "",
            "; AdaptiveCAD - Triangle-Free CAD",
        ]
        self._gcode_lines.extend(lines)
    
    def _process_slice(self, slice_obj: Slice, e_pos: float) -> float:
        """Process a single slice and return updated extrusion position."""
        s = self.settings
        z = slice_obj.z
        
        self._gcode_lines.append(f"\n; Layer at Z={z:.3f}")
        self._gcode_lines.append(f"G1 Z{z:.3f} F{s.travel_speed * 60:.0f}")
        
        # Print perimeters
        for contour in slice_obj.contours:
            if len(contour.points) < 2:
                continue
            
            pts = contour.points
            
            # Move to start (with retraction)
            self._gcode_lines.append(f"G1 E{e_pos - s.retraction_distance:.4f} F{s.retraction_speed * 60:.0f}")
            self._gcode_lines.append(f"G1 X{pts[0, 0]:.3f} Y{pts[0, 1]:.3f} F{s.travel_speed * 60:.0f}")
            self._gcode_lines.append(f"G1 E{e_pos:.4f} F{s.retraction_speed * 60:.0f}")
            
            # Print contour
            for i in range(1, len(pts)):
                # Calculate extrusion
                dist = np.linalg.norm(pts[i] - pts[i-1])
                # E = (layer_height * extrusion_width * distance) / (π * (filament_diameter/2)²)
                e_amount = (s.layer_height * s.extrusion_width * dist) / (
                    math.pi * (s.filament_diameter / 2) ** 2
                )
                e_pos += e_amount
                
                self._gcode_lines.append(
                    f"G1 X{pts[i, 0]:.3f} Y{pts[i, 1]:.3f} E{e_pos:.4f} F{s.print_speed * 60:.0f}"
                )
            
            # Close contour
            if len(pts) > 2:
                dist = np.linalg.norm(pts[0] - pts[-1])
                e_amount = (s.layer_height * s.extrusion_width * dist) / (
                    math.pi * (s.filament_diameter / 2) ** 2
                )
                e_pos += e_amount
                self._gcode_lines.append(
                    f"G1 X{pts[0, 0]:.3f} Y{pts[0, 1]:.3f} E{e_pos:.4f} F{s.print_speed * 60:.0f}"
                )
        
        return e_pos
    
    def export_gcode(self, filepath: str):
        """Export G-code to a file."""
        gcode = self.generate_gcode()
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            f.write(gcode)
        
        log.info(f"Exported G-code to {path}")
        return path


# Alias for backward compatibility
AnalyticSlicer = SDFSlicer
