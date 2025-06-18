"""Advanced 3D Slicing Module for AdaptiveCAD.

This module provides advanced 3D slicing capabilities for converting 3D models 
into G-code for 3D printing. It includes:

1. A 3D slicer class that can generate layer contours
2. A path planner for generating efficient tool paths
3. A G-code exporter for generating printer-specific commands
4. Parametric surface slicer for direct slicing of parametric surfaces
"""
from __future__ import annotations

import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union, Callable, Protocol

import numpy as np

try:
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepTools import breptools_Read, breptools_Write
    from OCC.Core.TopoDS import TopoDS_Shape, TopoDS_Compound
    from OCC.Core.Bnd import Bnd_Box
    from OCC.Core.BRepBndLib import brepbndlib_Add
    from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Ax3, gp_Pln
    from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Section
    # Check if we have GPU acceleration available
    try:
        import cupy as cp
        HAS_GPU = True
    except ImportError:
        HAS_GPU = False
except ImportError:
    # For type checking and documentation only
    TopoDS_Shape = object
    HAS_GPU = False

# Try importing scipy for KDTree, used in parametric surface slicing
try:
    from scipy.spatial import cKDTree
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False


@dataclass
class PrinterSettings:
    """Settings for 3D printer."""
    
    nozzle_diameter: float = 0.4
    layer_height: float = 0.2
    filament_diameter: float = 1.75
    extrusion_multiplier: float = 1.0
    retraction_amount: float = 0.5
    retraction_speed: float = 40.0
    print_speed: float = 60.0
    travel_speed: float = 120.0
    first_layer_speed: float = 30.0
    first_layer_height: float = 0.3
    bed_temperature: float = 60.0
    extruder_temperature: float = 200.0
    fan_speed: int = 255  # 0-255 range
    infill_percentage: float = 20.0  # 0-100%
    wall_count: int = 3
    top_layers: int = 3
    bottom_layers: int = 3
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to a dictionary."""
        return {k: v for k, v in self.__dict__.items()}


class Slicer3D:
    """Advanced 3D slicer for converting 3D models into layer contours."""
    
    def __init__(self, model: TopoDS_Shape, settings: Optional[PrinterSettings] = None):
        """Initialize the 3D slicer.
        
        Parameters
        ----------
        model : TopoDS_Shape
            The 3D model to slice (OCC shape or mesh).
        settings : PrinterSettings, optional
            Printer settings to use for slicing.
        """
        self.model = model
        self.settings = settings or PrinterSettings()
        self._bounds = None
        self._slice_cache = {}
        
        # Performance monitoring
        self.performance_metrics = {
            "slice_time": 0.0,
            "layers_processed": 0,
            "contours_generated": 0
        }
    
    @property
    def bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Get model bounds as ((min_x, min_y, min_z), (max_x, max_y, max_z))."""
        if self._bounds is None:
            try:
                # Use OCC bounding box
                bbox = Bnd_Box()
                brepbndlib_Add(self.model, bbox)
                xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
                self._bounds = ((xmin, ymin, zmin), (xmax, ymax, zmax))
            except Exception as e:
                # Fallback for non-OCC meshes
                raise ValueError(f"Could not determine model bounds: {e}")
        return self._bounds
    
    def slice_model(self, 
                   layer_height: Optional[float] = None, 
                   first_layer_height: Optional[float] = None,
                   callback: Optional[Callable[[int, int], None]] = None) -> List[Tuple[float, List[List[Tuple[float, float]]]]]:
        """Slice the model into layers.
        
        Parameters
        ----------
        layer_height : float, optional
            Height of each layer. Defaults to settings.layer_height.
        first_layer_height : float, optional
            Height of first layer. Defaults to settings.first_layer_height.
        callback : callable, optional
            Function to call with progress updates (current_layer, total_layers).
            
        Returns
        -------
        List[Tuple[float, List[List[Tuple[float, float]]]]]
            List of tuples containing (z_height, contours) where contours is a 
            list of closed paths, and each path is a list of (x, y) points.
        """
        start_time = time.time()
        
        layer_height = layer_height or self.settings.layer_height
        first_layer_height = first_layer_height or self.settings.first_layer_height
        
        z_min, z_max = self.bounds[0][2], self.bounds[1][2]
        
        # Create layer heights starting with first layer height
        layers = [first_layer_height]
        current_z = first_layer_height
        
        while current_z + layer_height <= z_max:
            current_z += layer_height
            layers.append(current_z)
            
        total_layers = len(layers)
        slice_contours = []
        
        for i, z in enumerate(layers):
            if callback and i % 5 == 0:  # Update every 5 layers
                callback(i, total_layers)
                
            contours = self.get_layer_contours(z)
            slice_contours.append((z, contours))
            self.performance_metrics["layers_processed"] += 1
            self.performance_metrics["contours_generated"] += len(contours)
            
        self.performance_metrics["slice_time"] = time.time() - start_time
        
        if callback:
            callback(total_layers, total_layers)  # Final update
            
        return slice_contours

    def get_layer_contours(self, z: float) -> List[List[Tuple[float, float]]]:
        """Get contours for a specific layer.
        
        Parameters
        ----------
        z : float
            Z height to slice at.
            
        Returns
        -------
        List[List[Tuple[float, float]]]
            List of contours, where each contour is a list of (x, y) points.
        """
        # Check cache first
        if z in self._slice_cache:
            return self._slice_cache[z]
            
        try:
            # Create slicing plane
            plane = gp_Pln(gp_Ax3(gp_Pnt(0, 0, z), gp_Dir(0, 0, 1)))
            
            # Create section
            section = BRepAlgoAPI_Section(self.model, plane)
            section.ComputePCurveOn1(True)
            section.Approximation(True)
            section.Build()
            section_shape = section.Shape()
            
            # Convert section to contours
            contours = self._extract_contours_from_section(section_shape)
            
            # Cache result
            self._slice_cache[z] = contours
            return contours
            
        except Exception as e:
            print(f"Error slicing at z={z}: {e}")
            return []
    
    def _extract_contours_from_section(self, section_shape: TopoDS_Shape) -> List[List[Tuple[float, float]]]:
        """Extract contours from a section shape.
        
        Parameters
        ----------
        section_shape : TopoDS_Shape
            The section shape to extract contours from.
            
        Returns
        -------
        List[List[Tuple[float, float]]]
            List of contours, where each contour is a list of (x, y) points.
        """
        # This method requires proper implementation to extract and organize
        # the contours from the OCC section shape
        # For demonstration, we'll return a placeholder implementation
        try:
            from OCC.Core.TopExp import TopExp_Explorer
            from OCC.Core.TopAbs import TopAbs_EDGE, TopAbs_VERTEX
            from OCC.Core.TopoDS import topods_Edge, topods_Vertex
            from OCC.Core.BRep import BRep_Tool
            from OCC.Core.GeomAdaptor import GeomAdaptor_Curve
            from OCC.Core.GCPnts import GCPnts_QuasiUniformDeflection
            
            contours = []
            explorer = TopExp_Explorer(section_shape, TopAbs_EDGE)
            
            # Group connected edges into contours
            while explorer.More():
                edge = topods_Edge(explorer.Current())
                curve, u_min, u_max = BRep_Tool.Curve(edge)
                
                if curve is None:
                    explorer.Next()
                    continue
                    
                adaptor = GeomAdaptor_Curve(curve)
                discretizer = GCPnts_QuasiUniformDeflection(adaptor, 0.01, u_min, u_max)
                
                if discretizer.IsDone() and discretizer.NbPoints() > 1:
                    contour = []
                    for i in range(1, discretizer.NbPoints() + 1):
                        point = discretizer.Value(i)
                        # Extract X and Y, ignore Z since we're in a plane
                        contour.append((point.X(), point.Y()))
                    contours.append(contour)
                    
                explorer.Next()
                
            return contours
            
        except Exception as e:
            print(f"Error extracting contours: {e}")
            return []
            
    def get_performance_report(self) -> str:
        """Get a report of slicing performance metrics."""
        if self.performance_metrics["slice_time"] == 0:
            return "No slicing performed yet."
            
        report = f"Slicing Performance Report:\n"
        report += f"- Total time: {self.performance_metrics['slice_time']:.2f} seconds\n"
        report += f"- Layers processed: {self.performance_metrics['layers_processed']}\n"
        report += f"- Contours generated: {self.performance_metrics['contours_generated']}\n"
        
        if self.performance_metrics["layers_processed"] > 0:
            time_per_layer = self.performance_metrics["slice_time"] / self.performance_metrics["layers_processed"]
            report += f"- Average time per layer: {time_per_layer:.4f} seconds\n"
            
        report += f"- Using GPU acceleration: {HAS_GPU}\n"
        
        return report


class PathPlanner:
    """Plan tool paths for 3D printing based on slice contours."""
    
    def __init__(self, slice_contours: List[Tuple[float, List[List[Tuple[float, float]]]]], 
                settings: Optional[PrinterSettings] = None):
        """Initialize the path planner.
        
        Parameters
        ----------
        slice_contours : List[Tuple[float, List[List[Tuple[float, float]]]]]
            List of tuples containing (z_height, contours) from the slicer.
        settings : PrinterSettings, optional
            Printer settings to use for path planning.
        """
        self.slice_contours = slice_contours
        self.settings = settings or PrinterSettings()
        self.paths = []
        
    def plan_paths(self, 
                  optimize_travel: bool = True, 
                  callback: Optional[Callable[[int, int], None]] = None) -> List[Dict]:
        """Plan tool paths for all layers.
        
        Parameters
        ----------
        optimize_travel : bool
            Whether to optimize travel moves between features.
        callback : callable, optional
            Function to call with progress updates (current_layer, total_layers).
            
        Returns
        -------
        List[Dict]
            List of layer data dictionaries containing paths and parameters.
        """
        self.paths = []
        total_layers = len(self.slice_contours)
        
        for i, (z_height, contours) in enumerate(self.slice_contours):
            if callback and i % 5 == 0:  # Update every 5 layers
                callback(i, total_layers)
                
            # Determine if this is the first layer
            is_first_layer = (i == 0)
            
            # Plan paths for this layer
            layer_paths = self._plan_layer_paths(
                z_height, 
                contours, 
                is_first_layer=is_first_layer,
                optimize_travel=optimize_travel
            )
            
            # Store layer data
            layer_data = {
                "z_height": z_height,
                "paths": layer_paths,
                "is_first_layer": is_first_layer,
                "print_speed": self.settings.first_layer_speed if is_first_layer else self.settings.print_speed,
                "extrusion_multiplier": self.settings.extrusion_multiplier * (1.2 if is_first_layer else 1.0)
            }
            
            self.paths.append(layer_data)
            
        if callback:
            callback(total_layers, total_layers)  # Final update
            
        return self.paths
    
    def _plan_layer_paths(self, 
                         z_height: float, 
                         contours: List[List[Tuple[float, float]]], 
                         is_first_layer: bool = False,
                         optimize_travel: bool = True) -> List[Dict]:
        """Plan paths for a single layer.
        
        Parameters
        ----------
        z_height : float
            Z height of the layer.
        contours : List[List[Tuple[float, float]]]
            List of contours for this layer.
        is_first_layer : bool
            Whether this is the first layer (affects settings).
        optimize_travel : bool
            Whether to optimize travel moves between features.
            
        Returns
        -------
        List[Dict]
            List of path dictionaries containing type, points, and parameters.
        """
        layer_paths = []
        
        if not contours:
            return layer_paths
            
        # Sort contours by area/perimeter to identify outer and inner contours
        sorted_contours = self._sort_contours_by_hierarchy(contours)
        
        # Add outer perimeter paths
        for contour in sorted_contours:
            perimeter_path = {
                "type": "perimeter",
                "points": contour,
                "speed": self.settings.print_speed * 0.8,  # Slower for perimeters
                "extrusion": True
            }
            layer_paths.append(perimeter_path)
            
            # Add inner wall paths if needed
            if self.settings.wall_count > 1:
                inner_walls = self._generate_inner_walls(contour, self.settings.wall_count)
                for wall in inner_walls:
                    wall_path = {
                        "type": "wall",
                        "points": wall,
                        "speed": self.settings.print_speed * 0.9,  # Slightly faster
                        "extrusion": True
                    }
                    layer_paths.append(wall_path)
            
            # Add infill if needed
            if self.settings.infill_percentage > 0:
                infill_paths = self._generate_infill(contour, self.settings.infill_percentage)
                for infill in infill_paths:
                    infill_path = {
                        "type": "infill",
                        "points": infill,
                        "speed": self.settings.print_speed * 1.1,  # Faster for infill
                        "extrusion": True
                    }
                    layer_paths.append(infill_path)
        
        # Optimize path order if requested
        if optimize_travel:
            layer_paths = self._optimize_path_order(layer_paths)
            
        return layer_paths
    
    def _sort_contours_by_hierarchy(self, contours: List[List[Tuple[float, float]]]) -> List[List[Tuple[float, float]]]:
        """Sort contours by nesting hierarchy (outer contours first).
        
        This is a placeholder implementation. In a real slicer, we would analyze
        the contours to determine their nesting relationship.
        """
        # Simple approximation - sort by area as a proxy for nesting
        def approx_area(contour):
            # Simple polygon area calculation using shoelace formula
            if not contour:
                return 0
                
            n = len(contour)
            area = 0.0
            for i in range(n):
                j = (i + 1) % n
                area += contour[i][0] * contour[j][1]
                area -= contour[j][0] * contour[i][1]
            return abs(area) / 2.0
            
        return sorted(contours, key=approx_area, reverse=True)
    
    def _generate_inner_walls(self, 
                             contour: List[Tuple[float, float]], 
                             wall_count: int) -> List[List[Tuple[float, float]]]:
        """Generate inner wall contours by offsetting the outer contour.
        
        In a real implementation, we would use a proper offset algorithm.
        This is a placeholder implementation.
        """
        # Placeholder implementation
        walls = []
        for i in range(1, wall_count):
            # Simple offset - not geometrically accurate
            offset = self.settings.nozzle_diameter * i
            scaled_contour = []
            
            # Find center point
            cx = sum(p[0] for p in contour) / len(contour)
            cy = sum(p[1] for p in contour) / len(contour)
            
            # Scale points toward center
            scale_factor = max(0.1, 1.0 - (i * 0.1))
            for x, y in contour:
                # Vector from center to point
                dx = x - cx
                dy = y - cy
                # Scaled position
                new_x = cx + dx * scale_factor
                new_y = cy + dy * scale_factor
                scaled_contour.append((new_x, new_y))
                
            walls.append(scaled_contour)
            
        return walls
    
    def _generate_infill(self, 
                        contour: List[Tuple[float, float]], 
                        infill_percentage: float) -> List[List[Tuple[float, float]]]:
        """Generate infill paths for a contour.
        
        This is a placeholder implementation for a simple grid infill.
        """
        # Placeholder - in a real implementation we would:
        # 1. Calculate the bounding box of the contour
        # 2. Generate a grid of lines based on infill density
        # 3. Clip lines to the contour boundary
        
        # For now, just return a simple placeholder
        infill_paths = []
        if infill_percentage <= 0:
            return infill_paths
            
        # Find bounding box
        min_x = min(p[0] for p in contour)
        max_x = max(p[0] for p in contour)
        min_y = min(p[1] for p in contour)
        max_y = max(p[1] for p in contour)
        
        # Calculate line spacing based on infill percentage
        # Higher percentage = more lines = smaller spacing
        spacing = self.settings.nozzle_diameter * 10 * (100 / max(1, infill_percentage))
        
        # Generate horizontal lines
        y = min_y
        while y <= max_y:
            infill_paths.append([(min_x, y), (max_x, y)])
            y += spacing
            
        # Generate vertical lines
        x = min_x
        while x <= max_x:
            infill_paths.append([(x, min_y), (x, max_y)])
            x += spacing
            
        return infill_paths
    
    def _optimize_path_order(self, paths: List[Dict]) -> List[Dict]:
        """Optimize the order of paths to minimize travel distance.
        
        This is a placeholder implementation using a simple greedy algorithm.
        """
        if not paths:
            return []
            
        # Simple greedy optimization
        result = [paths[0]]
        remaining = paths[1:]
        
        # Get last point of the current path
        last_path = result[-1]
        last_point = last_path["points"][-1] if last_path["points"] else (0, 0)
        
        while remaining:
            # Find the closest path
            closest_idx = 0
            closest_dist = float("inf")
            
            for i, path in enumerate(remaining):
                if not path["points"]:
                    continue
                    
                # Distance to start of this path
                dist = self._point_distance(last_point, path["points"][0])
                if dist < closest_dist:
                    closest_dist = dist
                    closest_idx = i
                    
            # Add the closest path
            next_path = remaining.pop(closest_idx)
            result.append(next_path)
            
            # Update last point
            last_point = next_path["points"][-1] if next_path["points"] else last_point
            
        return result
    
    def _point_distance(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two points."""
        return ((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2) ** 0.5


class GCodeExporter:
    """Export G-code for 3D printing from planned paths."""
    
    def __init__(self, path_data: List[Dict], settings: Optional[PrinterSettings] = None):
        """Initialize G-code exporter.
        
        Parameters
        ----------
        path_data : List[Dict]
            List of layer data dictionaries from the path planner.
        settings : PrinterSettings, optional
            Printer settings to use for G-code generation.
        """
        self.path_data = path_data
        self.settings = settings or PrinterSettings()
        self.extrusion_amount = 0.0
        self.current_position = (0, 0, 0)
        self.retracted = True
    
    def generate_gcode(self, 
                      include_comments: bool = True,
                      minimize_file_size: bool = False,
                      printer_type: str = "generic") -> str:
        """Generate G-code for the planned paths.
        
        Parameters
        ----------
        include_comments : bool
            Whether to include comments in the G-code.
        minimize_file_size : bool
            Whether to minimize file size by removing unnecessary commands.
        printer_type : str
            Type of printer to generate G-code for (affects start/end G-code).
            
        Returns
        -------
        str
            Generated G-code as a string.
        """
        gcode_lines = []
        
        # Add header
        self._add_header(gcode_lines, include_comments, printer_type)
        
        # Process each layer
        for i, layer_data in enumerate(self.path_data):
            z_height = layer_data["z_height"]
            is_first_layer = layer_data["is_first_layer"]
            print_speed = layer_data["print_speed"]
            
            # Add layer comment
            if include_comments:
                gcode_lines.append(f"\n; LAYER {i}: Z = {z_height:.3f}")
                
            # Add layer change command
            if is_first_layer:
                gcode_lines.append(f"G1 Z{z_height:.3f} F{self.settings.travel_speed * 60}")
            else:
                gcode_lines.append(f"G1 Z{z_height:.3f}")
                
            # Fan control
            if is_first_layer:
                gcode_lines.append("M106 S0 ; Turn off fan for first layer")
            elif self.settings.fan_speed > 0:
                fan_value = min(255, self.settings.fan_speed)
                gcode_lines.append(f"M106 S{fan_value} ; Set fan speed")
                
            # Process paths for this layer
            self._process_layer_paths(
                layer_data["paths"], 
                gcode_lines, 
                z_height, 
                include_comments, 
                minimize_file_size,
                print_speed
            )
                
        # Add footer
        self._add_footer(gcode_lines, include_comments, printer_type)
        
        return "\n".join(gcode_lines)
    
    def _add_header(self, gcode_lines: List[str], include_comments: bool, printer_type: str):
        """Add header G-code."""
        import datetime
        
        if include_comments:
            gcode_lines.extend([
                "; G-code generated by AdaptiveCAD Slicer",
                f"; Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                f"; Layer Height: {self.settings.layer_height:.3f}mm",
                f"; Nozzle Diameter: {self.settings.nozzle_diameter:.2f}mm",
                f"; Filament Diameter: {self.settings.filament_diameter:.2f}mm",
                "; Print Settings:",
                f";   - Print Speed: {self.settings.print_speed:.1f}mm/s",
                f";   - First Layer Speed: {self.settings.first_layer_speed:.1f}mm/s",
                f";   - Travel Speed: {self.settings.travel_speed:.1f}mm/s",
                f";   - Bed Temperature: {self.settings.bed_temperature:.1f}°C",
                f";   - Extruder Temperature: {self.settings.extruder_temperature:.1f}°C",
                f";   - Infill: {self.settings.infill_percentage:.1f}%",
                f";   - Walls: {self.settings.wall_count}",
                ""
            ])
        
        # Standard G-code header
        gcode_lines.extend([
            "M201 X500 Y500 Z100 E5000 ; Set acceleration",
            "M203 X500 Y500 Z10 E50 ; Set maximum feedrates",
            "G21 ; Set units to millimeters",
            "G90 ; Use absolute coordinates",
            "M83 ; Use relative distances for extrusion",
        ])
        
        # Heating commands
        gcode_lines.extend([
            f"M140 S{self.settings.bed_temperature} ; Set bed temperature",
            f"M104 S{self.settings.extruder_temperature} ; Set extruder temperature",
            "M190 S{self.settings.bed_temperature} ; Wait for bed temperature",
            "M109 S{self.settings.extruder_temperature} ; Wait for extruder temperature"
        ])
        
        # Home and prepare
        gcode_lines.extend([
            "G28 ; Home all axes",
            "G1 Z5 F1200 ; Move Z up a bit",
            "G1 X0 Y0 F3000 ; Move to front corner",
            "G92 E0 ; Reset extruder position",
            "G1 Z0.2 F1200 ; Get ready to prime",
            "G1 X100 E12 F1000 ; Prime",
            "G92 E0 ; Reset extruder position again",
            "G1 F200 E-1 ; Retract a bit to prevent oozing",
            "G1 X120 F5000 ; Quickly wipe away from prime line",
            ""
        ])
        
    def _add_footer(self, gcode_lines: List[str], include_comments: bool, printer_type: str):
        """Add footer G-code."""
        if include_comments:
            gcode_lines.append("\n; End G-Code")
            
        # Standard end G-code
        gcode_lines.extend([
            "G91 ; Relative positioning",
            "G1 E-2 F2700 ; Retract",
            "G1 Z10 ; Raise Z",
            "G90 ; Absolute positioning",
            "G1 X0 Y220 ; Present print",
            "M106 S0 ; Turn off fan",
            "M104 S0 ; Turn off extruder",
            "M140 S0 ; Turn off bed",
            "M84 ; Disable motors",
            "M300 S440 P200 ; Beep to notify print is done"
        ])
        
    def _process_layer_paths(self, 
                            paths: List[Dict], 
                            gcode_lines: List[str],
                            z_height: float,
                            include_comments: bool,
                            minimize_file_size: bool,
                            print_speed: float):
        """Process paths for a single layer and add commands to gcode_lines."""
        for path in paths:
            path_type = path.get("type", "unknown")
            points = path.get("points", [])
            extrusion = path.get("extrusion", False)
            speed = path.get("speed", print_speed)
            
            if not points:
                continue
                
            # Add comment for path type
            if include_comments:
                gcode_lines.append(f"; {path_type.upper()} path")
                
            # Move to start of path (travel move)
            start = points[0]
            self._add_travel(gcode_lines, start[0], start[1], z_height)
            
            # Prepare for extrusion if needed
            if extrusion and self.retracted:
                gcode_lines.append(f"G1 F{self.settings.retraction_speed * 60} E{self.settings.retraction_amount}")
                self.retracted = False
                
            # Process the path points
            for i in range(1, len(points)):
                x, y = points[i]
                
                if extrusion:
                    # Calculate extrusion amount
                    prev_x, prev_y = points[i-1]
                    extrusion_length = self._calculate_extrusion(
                        prev_x, prev_y, x, y, 
                        self.settings.layer_height,
                        self.settings.nozzle_diameter,
                        self.settings.filament_diameter
                    )
                    
                    # Add extrusion move
                    gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f} E{extrusion_length:.4f} F{speed * 60}")
                else:
                    # Add travel move
                    gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f} F{self.settings.travel_speed * 60}")
                    
                # Update current position
                self.current_position = (x, y, z_height)
            
            # Retract after path if needed
            if extrusion:
                gcode_lines.append(f"G1 F{self.settings.retraction_speed * 60} E-{self.settings.retraction_amount}")
                self.retracted = True
    
    def _add_travel(self, gcode_lines: List[str], x: float, y: float, z: float):
        """Add a travel move to the G-code."""
        # Retract if not already retracted
        if not self.retracted:
            gcode_lines.append(f"G1 F{self.settings.retraction_speed * 60} E-{self.settings.retraction_amount}")
            self.retracted = True
            
        # Travel move
        gcode_lines.append(f"G1 X{x:.3f} Y{y:.3f} F{self.settings.travel_speed * 60}")
        
        # Update position
        self.current_position = (x, y, z)
    
    def _calculate_extrusion(self, 
                           x1: float, y1: float, 
                           x2: float, y2: float, 
                           layer_height: float,
                           nozzle_diameter: float,
                           filament_diameter: float) -> float:
        """Calculate extrusion amount for a move.
        
        Uses a volumetric calculation based on line length, layer height, and nozzle width.
        """
        # Calculate line length
        line_length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        
        # Volume of filament needed = line cross-section * length
        line_cross_section = layer_height * nozzle_diameter
        volume = line_cross_section * line_length
        
        # Convert to length of filament
        filament_cross_section = np.pi * (filament_diameter / 2) ** 2
        filament_length = volume / filament_cross_section
        
        # Apply extrusion multiplier
        filament_length *= self.settings.extrusion_multiplier
        
        return filament_length


class ParametricSurface(Protocol):
    """Protocol for parametric surfaces that can be sliced."""
    
    def evaluate(self, u: float, v: float) -> Tuple[float, float, float]:
        """Evaluate surface at parameter (u, v).
        
        Parameters
        ----------
        u : float
            U parameter.
        v : float
            V parameter.
            
        Returns
        -------
        Tuple[float, float, float]
            (x, y, z) point on surface.
        """
        ...
    
    def u_range(self) -> Tuple[float, float]:
        """Get the range of u parameter.
        
        Returns
        -------
        Tuple[float, float]
            (u_min, u_max) parameter bounds.
        """
        ...
        
    def v_range(self) -> Tuple[float, float]:
        """Get the range of v parameter.
        
        Returns
        -------
        Tuple[float, float]
            (v_min, v_max) parameter bounds.
        """
        ...


class ParametricSlicer:
    """Slicer for parametric surfaces that implement the ParametricSurface protocol."""
    
    def __init__(self, 
                 surface: ParametricSurface, 
                 settings: Optional[PrinterSettings] = None,
                 u_samples: int = 200,
                 v_samples: int = 200):
        """Initialize parametric slicer.
        
        Parameters
        ----------
        surface : ParametricSurface
            The parametric surface to slice.
        settings : PrinterSettings, optional
            Printer settings to use for slicing.
        u_samples : int
            Number of samples in u direction.
        v_samples : int
            Number of samples in v direction.
        """
        self.surface = surface
        self.settings = settings or PrinterSettings()
        self.u_samples = u_samples
        self.v_samples = v_samples
        self._bounds = None
        self._slice_cache = {}
        
        # Performance monitoring
        self.performance_metrics = {
            "slice_time": 0.0,
            "layers_processed": 0,
            "contours_generated": 0
        }
    
    @property
    def bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        """Get model bounds as ((min_x, min_y, min_z), (max_x, max_y, max_z))."""
        if self._bounds is None:
            # Sample the surface to find bounds
            u0, u1 = self.surface.u_range()
            v0, v1 = self.surface.v_range()
            
            u_vals = np.linspace(u0, u1, min(20, self.u_samples))
            v_vals = np.linspace(v0, v1, min(20, self.v_samples))
            
            x_vals, y_vals, z_vals = [], [], []
            
            for u in u_vals:
                for v in v_vals:
                    x, y, z = self.surface.evaluate(u, v)
                    x_vals.append(x)
                    y_vals.append(y)
                    z_vals.append(z)
            
            self._bounds = (
                (min(x_vals), min(y_vals), min(z_vals)),
                (max(x_vals), max(y_vals), max(z_vals))
            )
        
        return self._bounds
    
    def slice_surface_at_z(self, z_height: float) -> np.ndarray:
        """Slice the surface at a specific Z height.
        
        Parameters
        ----------
        z_height : float
            Z height to slice at.
            
        Returns
        -------
        np.ndarray
            Array of points (N, 3) where each row is (x, y, z).
        """
        # Check cache first
        if z_height in self._slice_cache:
            return self._slice_cache[z_height]
        
        u0, u1 = self.surface.u_range()
        v0, v1 = self.surface.v_range()
        u_vals = np.linspace(u0, u1, self.u_samples)
        v_vals = np.linspace(v0, v1, self.v_samples)
        segments = []
        
        for i in range(self.u_samples - 1):
            for j in range(self.v_samples - 1):
                uv = [
                    (u_vals[i], v_vals[j]),
                    (u_vals[i+1], v_vals[j]),
                    (u_vals[i+1], v_vals[j+1]),
                    (u_vals[i], v_vals[j+1]),
                ]
                z = [self.surface.evaluate(u, v)[2] for u, v in uv]
                
                # For each edge of the quad
                for k in range(4):
                    u1_, v1_ = uv[k]
                    u2_, v2_ = uv[(k+1)%4]
                    z1_, z2_ = z[k], z[(k+1)%4]
                    
                    # Check if edge crosses the slice plane
                    if (z1_ - z_height) * (z2_ - z_height) < 0:
                        # Linear interpolation to find intersection point
                        t = (z_height - z1_) / (z2_ - z1_)
                        u_interp = u1_ + t * (u2_ - u1_)
                        v_interp = v1_ + t * (v2_ - v1_)
                        
                        # Evaluate surface at interpolated parameters
                        xyz = self.surface.evaluate(u_interp, v_interp)
                        segments.append(tuple(xyz))
        
        result = np.array(segments)
        
        # Cache result
        self._slice_cache[z_height] = result
        return result
        
    def link_contour_points(self, points: np.ndarray, close_threshold: float = 1.0) -> np.ndarray:
        """Link the contour points into a continuous path.
        
        Parameters
        ----------
        points : np.ndarray
            Array of points (N, 3) where each row is (x, y, z).
        close_threshold : float
            Distance threshold for closing the contour loop.
            
        Returns
        -------
        np.ndarray
            Ordered array of points forming a continuous path.
        """
        if len(points) == 0:
            return np.array([])
            
        if not HAS_SCIPY:
            # Simple nearest-neighbor without scipy
            points = np.array(points)
            used = np.zeros(len(points), dtype=bool)
            path = [0]
            used[0] = True
            
            for _ in range(1, len(points)):
                last = path[-1]
                last_point = points[last]
                
                # Find nearest unused point
                min_dist = float('inf')
                min_idx = -1
                
                for i, point in enumerate(points):
                    if not used[i]:
                        dist = np.sum((point - last_point)**2)  # squared distance
                        if dist < min_dist:
                            min_dist = dist
                            min_idx = i
                
                if min_idx != -1:
                    path.append(min_idx)
                    used[min_idx] = True
                else:
                    break
        else:
            # Use scipy's KDTree for efficient nearest-neighbor search
            points = np.array(points)
            used = np.zeros(len(points), dtype=bool)
            path = [0]
            used[0] = True
            tree = cKDTree(points)
            
            for _ in range(1, len(points)):
                last = path[-1]
                dists, idxs = tree.query(points[last], k=len(points))
                
                for idx in idxs:
                    if not used[idx]:
                        path.append(idx)
                        used[idx] = True
                        break
        
        # Optionally, close loop if ends are close
        if np.linalg.norm(points[path[0]] - points[path[-1]]) < close_threshold:
            path.append(path[0])
            
        return points[path]
    
    def optimize_toolpath(self, points: np.ndarray) -> np.ndarray:
        """Optimize the toolpath to minimize travel distance.
        
        Parameters
        ----------
        points : np.ndarray
            Array of points (N, 3) where each row is (x, y, z).
            
        Returns
        -------
        np.ndarray
            Optimized array of points.
        """
        # For now, return the input points
        # In a future implementation, this could use ElasticTSPOptimizer
        return points
    
    def slice_model(self, 
                   layer_height: Optional[float] = None, 
                   first_layer_height: Optional[float] = None,
                   callback: Optional[Callable[[int, int], None]] = None) -> List[Tuple[float, List[List[Tuple[float, float]]]]]:
        """Slice the parametric surface into layers.
        
        Parameters
        ----------
        layer_height : float, optional
            Height of each layer. Defaults to settings.layer_height.
        first_layer_height : float, optional
            Height of first layer. Defaults to settings.first_layer_height.
        callback : callable, optional
            Function to call with progress updates (current_layer, total_layers).
            
        Returns
        -------
        List[Tuple[float, List[List[Tuple[float, float]]]]]
            List of tuples containing (z_height, contours) where contours is a 
            list of closed paths, and each path is a list of (x, y) points.
        """
        start_time = time.time()
        
        layer_height = layer_height or self.settings.layer_height
        first_layer_height = first_layer_height or self.settings.first_layer_height
        
        z_min, z_max = self.bounds[0][2], self.bounds[1][2]
        
        # Create layer heights starting with first layer height
        layers = [first_layer_height]
        current_z = first_layer_height
        
        while current_z + layer_height <= z_max:
            current_z += layer_height
            layers.append(current_z)
            
        total_layers = len(layers)
        slice_contours = []
        
        for i, z in enumerate(layers):
            if callback and i % 5 == 0:  # Update every 5 layers
                callback(i, total_layers)
                
            # Get contour points at this Z height
            contour_points = self.slice_surface_at_z(z)
            
            # No contours at this height
            if len(contour_points) == 0:
                slice_contours.append((z, []))
                continue
                
            # Link points into continuous paths
            linked_path = self.link_contour_points(contour_points)
            
            # Extract 2D points (x, y) for compatibility with existing code
            path_2d = [(float(p[0]), float(p[1])) for p in linked_path]
            
            # Add to results
            slice_contours.append((z, [path_2d]))
            
            self.performance_metrics["layers_processed"] += 1
            self.performance_metrics["contours_generated"] += 1
            
        self.performance_metrics["slice_time"] = time.time() - start_time
        
        if callback:
            callback(total_layers, total_layers)  # Final update
            
        return slice_contours
    
    def get_performance_report(self) -> str:
        """Get a report of slicing performance metrics."""
        if self.performance_metrics["slice_time"] == 0:
            return "No slicing performed yet."
            
        report = f"Parametric Slicing Performance Report:\n"
        report += f"- Total time: {self.performance_metrics['slice_time']:.2f} seconds\n"
        report += f"- Layers processed: {self.performance_metrics['layers_processed']}\n"
        report += f"- Contours generated: {self.performance_metrics['contours_generated']}\n"
        
        if self.performance_metrics["layers_processed"] > 0:
            time_per_layer = self.performance_metrics["slice_time"] / self.performance_metrics["layers_processed"]
            report += f"- Average time per layer: {time_per_layer:.4f} seconds\n"
            
        report += f"- Using SciPy acceleration: {HAS_SCIPY}\n"
        
        return report


def slice_model_to_gcode(
    model: Any,
    output_path: str,
    settings: Optional[PrinterSettings] = None,
    show_progress: bool = True
) -> str:
    """
    Slice a 3D model and generate G-code in one operation.
    
    Parameters
    ----------
    model : Any
        The 3D model to slice (OCC shape or mesh).
    output_path : str
        Path to save G-code output.
    settings : PrinterSettings, optional
        Printer settings to use for slicing and G-code generation.
    show_progress : bool
        Whether to print progress updates to console.
    
    Returns
    -------
    str
        Path to the generated G-code file.
    """
    settings = settings or PrinterSettings()
    
    # Progress callback
    def progress_callback(current, total):
        if show_progress:
            print(f"Progress: {current}/{total} ({current/total*100:.1f}%)")
    
    # Create slicer and slice model
    if show_progress:
        print("Slicing model...")
    slicer = Slicer3D(model, settings)
    slice_contours = slicer.slice_model(callback=progress_callback if show_progress else None)
    
    if show_progress:
        print(f"Generated {len(slice_contours)} layers")
        print("Planning tool paths...")
    
    # Plan tool paths
    path_planner = PathPlanner(slice_contours, settings)
    paths = path_planner.plan_paths(callback=progress_callback if show_progress else None)
    
    if show_progress:
        print("Generating G-code...")
    
    # Generate G-code
    gcode_exporter = GCodeExporter(paths, settings)
    gcode = gcode_exporter.generate_gcode()
    
    # Save to file
    with open(output_path, 'w') as f:
        f.write(gcode)
    
    if show_progress:
        print(f"G-code saved to: {output_path}")
        print(slicer.get_performance_report())
    
    return output_path
