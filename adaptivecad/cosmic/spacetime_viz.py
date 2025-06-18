"""Spacetime Visualization Toolkit for AdaptiveCAD.

Extends the existing adaptivecad.spacetime module with advanced 4D+ visualization,
light cone exploration, and curvature simulation capabilities.
"""

import numpy as np
import math
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

try:
    from adaptivecad.spacetime import Event, minkowski_interval, light_cone, apply_boost
    from adaptivecad.ndfield import NDField
    from adaptivecad.geom.hyperbolic import pi_a_over_pi
    HAS_SPACETIME = True
except ImportError:
    HAS_SPACETIME = False


@dataclass
class SpacetimeField:
    """A field defined over 4D spacetime with physical properties."""
    
    events: List[Event]
    field_values: np.ndarray
    field_type: str  # 'scalar', 'vector', 'tensor'
    units: str = ""
    name: str = ""
    
    def value_at_event(self, event: Event) -> float:
        """Interpolate field value at a given spacetime event."""
        # Simple nearest-neighbor for now - could upgrade to proper interpolation
        min_dist = float('inf')
        closest_idx = 0
        
        for i, e in enumerate(self.events):
            dist = abs(minkowski_interval(event, e))
            if dist < min_dist:
                min_dist = dist
                closest_idx = i
                
        return self.field_values[closest_idx]


class LightConeExplorer:
    """Interactive light cone visualization and causality analysis."""
    
    def __init__(self, origin_event: Event):
        self.origin = origin_event
        self.light_speed = 1.0  # c = 1 in natural units
        
    def generate_light_cone_surface(self, max_radius: float = 5.0, 
                                   resolution: int = 50) -> Tuple[List[Event], List[Event]]:
        """Generate points on future and past light cones."""
        return light_cone(self.origin, max_radius, resolution)
    
    def is_causally_connected(self, event1: Event, event2: Event) -> str:
        """Determine causal relationship between two events."""
        interval = minkowski_interval(event1, event2)
        
        if interval > 0:
            return "timelike_separated"  # Causal connection possible
        elif interval < 0:
            return "spacelike_separated"  # No causal connection
        else:
            return "lightlike_separated"  # On light cone
    
    def generate_worldline(self, velocity: Tuple[float, float, float],
                          duration: float, steps: int = 100) -> List[Event]:
        """Generate a worldline for an object with constant velocity."""
        vx, vy, vz = velocity
        v_mag = math.sqrt(vx*vx + vy*vy + vz*vz)
        
        if v_mag >= self.light_speed:
            raise ValueError("Velocity must be less than light speed")
        
        worldline = []
        for i in range(steps):
            t = duration * i / (steps - 1)
            x = self.origin.x + vx * t
            y = self.origin.y + vy * t  
            z = self.origin.z + vz * t
            worldline.append(Event(self.origin.t + t, x, y, z))
            
        return worldline


class CurvatureVisualizer:
    """Visualize spacetime curvature using Adaptive Pi geometry principles."""
    
    def __init__(self):
        self.curvature_field = None
        
    def create_curvature_field(self, mass_distribution: List[Tuple[Event, float]],
                              grid_size: Tuple[int, int, int, int] = (20, 20, 20, 20)) -> NDField:
        """Create a 4D curvature field from mass distribution."""
        nt, nx, ny, nz = grid_size
        
        # Create spacetime grid
        t_range = np.linspace(-5, 5, nt)
        x_range = np.linspace(-10, 10, nx)
        y_range = np.linspace(-10, 10, ny)
        z_range = np.linspace(-10, 10, nz)
        
        curvature_values = np.zeros(grid_size)
        
        for i, t in enumerate(t_range):
            for j, x in enumerate(x_range):
                for k, y in enumerate(y_range):
                    for l, z in enumerate(z_range):
                        event = Event(t, x, y, z)
                        curvature = self._calculate_curvature_at_event(event, mass_distribution)
                        curvature_values[i, j, k, l] = curvature
        
        return NDField(grid_size, curvature_values.flatten())
    
    def _calculate_curvature_at_event(self, event: Event, 
                                     masses: List[Tuple[Event, float]]) -> float:
        """Calculate spacetime curvature at an event due to mass distribution."""
        total_curvature = 0.0
        G = 1.0  # Gravitational constant in natural units
        
        for mass_event, mass in masses:
            # Calculate proper distance (simplified)
            interval = minkowski_interval(event, mass_event)
            if abs(interval) < 1e-10:  # Avoid singularity
                continue
                
            # Simplified curvature calculation (real GR would use Einstein tensor)
            r = abs(interval) ** 0.5
            if r > 0:
                curvature_contribution = G * mass / (r * r)
                total_curvature += curvature_contribution
                
        return total_curvature
    
    def visualize_geodesics(self, start_event: Event, initial_velocity: Tuple[float, float, float],
                           curvature_field: NDField, steps: int = 100) -> List[Event]:
        """Calculate and visualize geodesic paths in curved spacetime."""
        geodesic = [start_event]
        current_event = start_event
        vx, vy, vz = initial_velocity
        dt = 0.1
        
        for _ in range(steps - 1):
            # Simplified geodesic integration (real implementation would use Christoffel symbols)
            # For now, use adaptive pi principles to modify the path
            
            # Get local curvature
            grid_pos = self._event_to_grid_position(current_event, curvature_field)
            if grid_pos is not None:
                local_curvature = curvature_field.value_at(grid_pos)
                
                # Use adaptive pi to modify the path
                curvature_factor = pi_a_over_pi(1.0, local_curvature) if HAS_SPACETIME else 1.0
                
                # Apply curvature correction to velocity
                vx *= curvature_factor
                vy *= curvature_factor  
                vz *= curvature_factor
            
            # Update position
            new_event = Event(
                current_event.t + dt,
                current_event.x + vx * dt,
                current_event.y + vy * dt,
                current_event.z + vz * dt
            )
            
            geodesic.append(new_event)
            current_event = new_event
            
        return geodesic
    
    def _event_to_grid_position(self, event: Event, field: NDField) -> Optional[Tuple[int, int, int, int]]:
        """Convert spacetime event to grid indices for field lookup."""
        # Simplified mapping - would need proper coordinate transformation
        try:
            # Assuming field grid covers -5 to 5 in all dimensions
            t_idx = int((event.t + 5) / 10 * field.grid_shape[0])
            x_idx = int((event.x + 10) / 20 * field.grid_shape[1])
            y_idx = int((event.y + 10) / 20 * field.grid_shape[2])
            z_idx = int((event.z + 10) / 20 * field.grid_shape[3])
            
            # Clamp to valid indices
            t_idx = max(0, min(field.grid_shape[0] - 1, t_idx))
            x_idx = max(0, min(field.grid_shape[1] - 1, x_idx))
            y_idx = max(0, min(field.grid_shape[2] - 1, y_idx))
            z_idx = max(0, min(field.grid_shape[3] - 1, z_idx))
            
            return (t_idx, x_idx, y_idx, z_idx)
        except:
            return None


class GravitationalLensing:
    """Simulate and visualize gravitational lensing effects."""
    
    def __init__(self, lens_mass: float, lens_position: Event):
        self.lens_mass = lens_mass
        self.lens_position = lens_position
        
    def calculate_light_deflection(self, light_ray_events: List[Event]) -> List[Event]:
        """Calculate the deflection of light rays due to gravitational lensing."""
        deflected_ray = []
        
        for event in light_ray_events:
            # Calculate deflection angle (simplified)
            r_vec = np.array([
                event.x - self.lens_position.x,
                event.y - self.lens_position.y,
                event.z - self.lens_position.z
            ])
            
            r_mag = np.linalg.norm(r_vec)
            if r_mag < 1e-10:  # Avoid singularity
                deflected_ray.append(event)
                continue
                
            # Einstein deflection angle (simplified 2D case)
            deflection_angle = 4 * self.lens_mass / r_mag  # G=c=1 units
            
            # Apply deflection perpendicular to radial direction
            r_unit = r_vec / r_mag
            perp_direction = np.array([-r_unit[1], r_unit[0], 0])  # 90° rotation in xy plane
            
            deflection = deflection_angle * perp_direction
            
            deflected_event = Event(
                event.t,
                event.x + deflection[0],
                event.y + deflection[1], 
                event.z + deflection[2]
            )
            
            deflected_ray.append(deflected_event)
            
        return deflected_ray
    
    def create_einstein_ring(self, source_distance: float, lens_distance: float,
                           resolution: int = 100) -> List[Event]:
        """Generate points on an Einstein ring for perfect alignment."""
        einstein_radius = math.sqrt(4 * self.lens_mass * lens_distance * 
                                   (source_distance - lens_distance) / source_distance)
        
        ring_events = []
        for i in range(resolution):
            angle = 2 * math.pi * i / resolution
            x = self.lens_position.x + einstein_radius * math.cos(angle)
            y = self.lens_position.y + einstein_radius * math.sin(angle)
            z = self.lens_position.z
            t = self.lens_position.t
            
            ring_events.append(Event(t, x, y, z))
            
        return ring_events


# Integration with existing AdaptiveCAD GUI
class SpacetimeVisualizationCmd:
    """Command to add spacetime visualization tools to AdaptiveCAD."""
    
    def __init__(self):
        self.name = "Spacetime Visualization"
        
    def run(self, mw):
        """Add spacetime visualization to the main window."""
        if not HAS_SPACETIME:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(mw.win, "Missing Dependencies", 
                              "Spacetime module not available. Please check installation.")
            return
            
        # Show light cone parameter dialog
        try:
            from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox, QComboBox
            
            class LightConeDialog(QDialog):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("Light Cone Visualization Parameters")
                    layout = QFormLayout(self)
                    
                    self.radius = QDoubleSpinBox()
                    self.radius.setRange(0.1, 100.0)
                    self.radius.setValue(5.0)
                    self.radius.setSuffix(" units")
                    
                    self.resolution = QSpinBox()
                    self.resolution.setRange(8, 200)
                    self.resolution.setValue(32)
                    
                    self.cone_type = QComboBox()
                    self.cone_type.addItems(["Both Cones", "Future Only", "Past Only"])
                    
                    self.origin_x = QDoubleSpinBox()
                    self.origin_x.setRange(-100, 100)
                    self.origin_x.setValue(0.0)
                    
                    self.origin_y = QDoubleSpinBox()
                    self.origin_y.setRange(-100, 100)
                    self.origin_y.setValue(0.0)
                    
                    self.origin_z = QDoubleSpinBox()
                    self.origin_z.setRange(-100, 100)
                    self.origin_z.setValue(0.0)
                    
                    layout.addRow("Light Cone Radius:", self.radius)
                    layout.addRow("Resolution (points):", self.resolution)
                    layout.addRow("Cone Type:", self.cone_type)
                    layout.addRow("Origin X:", self.origin_x)
                    layout.addRow("Origin Y:", self.origin_y)
                    layout.addRow("Origin Z:", self.origin_z)
                    
                    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    buttons.accepted.connect(self.accept)
                    buttons.rejected.connect(self.reject)
                    layout.addRow(buttons)
            
            dlg = LightConeDialog(mw.win)
            if not dlg.exec():
                return
            
            # Create origin event
            origin = Event(0, dlg.origin_x.value(), dlg.origin_y.value(), dlg.origin_z.value())
            
            # Create light cone geometry
            light_cone_shape = self._create_light_cone_geometry(
                origin, 
                dlg.radius.value(), 
                dlg.resolution.value(),
                dlg.cone_type.currentText()
            )
            
            if light_cone_shape:
                # Add to document
                from adaptivecad.command_defs import Feature, DOCUMENT, rebuild_scene
                
                params = {
                    "radius": dlg.radius.value(),
                    "resolution": dlg.resolution.value(),
                    "cone_type": dlg.cone_type.currentText(),
                    "origin": (dlg.origin_x.value(), dlg.origin_y.value(), dlg.origin_z.value())
                }
                
                feature = Feature("LightCone", params, light_cone_shape)
                DOCUMENT.append(feature)
                
                # Display the light cone
                mw.view._display.EraseAll()
                mw.view._display.DisplayShape(light_cone_shape, update=True)
                mw.view._display.FitAll()
                
                mw.win.statusBar().showMessage(
                    f"Light cone created: radius={dlg.radius.value()}, type={dlg.cone_type.currentText()}", 
                    5000
                )
            else:
                mw.win.statusBar().showMessage("Failed to create light cone geometry", 3000)
                
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(mw.win, "Error", f"Light cone visualization error: {str(e)}")
    
    def _create_light_cone_geometry(self, origin: Event, radius: float, resolution: int, cone_type: str):
        """Create 3D geometry for light cone visualization."""
        try:
            from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Ax2
            from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeCone
            from OCC.Core.BRep import BRep_Builder
            from OCC.Core.TopoDS import TopoDS_Compound
            from OCC.Core.gp import gp_Trsf, gp_Vec
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
            
            builder = BRep_Builder()
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            
            # Create cone parameters
            apex = gp_Pnt(origin.x, origin.y, origin.z)
            
            # Create future light cone (opening upward in time, represented as +Z)
            if cone_type in ["Both Cones", "Future Only"]:
                future_axis = gp_Ax2(apex, gp_Dir(0, 0, 1))  # Z-axis up
                future_cone = BRepPrimAPI_MakeCone(future_axis, 0.1, radius, radius).Shape()
                builder.Add(compound, future_cone)
            
            # Create past light cone (opening downward in time, represented as -Z)
            if cone_type in ["Both Cones", "Past Only"]:
                past_apex = gp_Pnt(origin.x, origin.y, origin.z - radius)
                past_axis = gp_Ax2(past_apex, gp_Dir(0, 0, 1))  # Z-axis up
                past_cone = BRepPrimAPI_MakeCone(past_axis, radius, 0.1, radius).Shape()
                builder.Add(compound, past_cone)
            
            return compound
            
        except Exception as e:
            print(f"Error creating light cone geometry: {e}")
            return None


class LightConeDisplayBoxCmd:
    """Command to create a light cone display box with spacetime grid."""
    
    def __init__(self):
        self.name = "Light Cone Display Box"
        
    def run(self, mw):
        """Create a display box containing light cone visualization."""
        try:
            from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox, QCheckBox
            
            class DisplayBoxDialog(QDialog):
                def __init__(self, parent=None):
                    super().__init__(parent)
                    self.setWindowTitle("Light Cone Display Box Parameters")
                    layout = QFormLayout(self)
                    
                    self.box_size = QDoubleSpinBox()
                    self.box_size.setRange(10.0, 500.0)
                    self.box_size.setValue(100.0)
                    self.box_size.setSuffix(" units")
                    
                    self.cone_radius = QDoubleSpinBox()
                    self.cone_radius.setRange(1.0, 50.0)
                    self.cone_radius.setValue(20.0)
                    self.cone_radius.setSuffix(" units")
                    
                    self.grid_spacing = QDoubleSpinBox()
                    self.grid_spacing.setRange(1.0, 20.0)
                    self.grid_spacing.setValue(5.0)
                    self.grid_spacing.setSuffix(" units")
                    
                    self.show_grid = QCheckBox()
                    self.show_grid.setChecked(True)
                    
                    self.show_coordinates = QCheckBox()
                    self.show_coordinates.setChecked(True)
                    
                    layout.addRow("Display Box Size:", self.box_size)
                    layout.addRow("Light Cone Radius:", self.cone_radius)
                    layout.addRow("Grid Spacing:", self.grid_spacing)
                    layout.addRow("Show Spacetime Grid:", self.show_grid)
                    layout.addRow("Show Coordinates:", self.show_coordinates)
                    
                    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                    buttons.accepted.connect(self.accept)
                    buttons.rejected.connect(self.reject)
                    layout.addRow(buttons)
            
            dlg = DisplayBoxDialog(mw.win)
            if not dlg.exec():
                return
            
            # Create the display box with light cone
            display_shape = self._create_display_box_with_light_cone(
                dlg.box_size.value(),
                dlg.cone_radius.value(),
                dlg.grid_spacing.value(),
                dlg.show_grid.isChecked(),
                dlg.show_coordinates.isChecked()
            )
            
            if display_shape:
                # Add to document
                from adaptivecad.command_defs import Feature, DOCUMENT, rebuild_scene
                
                params = {
                    "box_size": dlg.box_size.value(),
                    "cone_radius": dlg.cone_radius.value(),
                    "grid_spacing": dlg.grid_spacing.value(),
                    "show_grid": dlg.show_grid.isChecked(),
                    "show_coordinates": dlg.show_coordinates.isChecked()
                }
                
                feature = Feature("LightConeDisplayBox", params, display_shape)
                DOCUMENT.append(feature)
                
                # Display the result
                mw.view._display.EraseAll()
                mw.view._display.DisplayShape(display_shape, update=True)
                mw.view._display.FitAll()
                
                mw.win.statusBar().showMessage(
                    f"Light Cone Display Box created: size={dlg.box_size.value()}", 
                    5000
                )
            else:
                mw.win.statusBar().showMessage("Failed to create display box", 3000)
                
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(mw.win, "Error", f"Display box error: {str(e)}")
    
    def _create_display_box_with_light_cone(self, box_size: float, cone_radius: float, 
                                           grid_spacing: float, show_grid: bool, show_coordinates: bool):
        """Create a display box containing light cone and spacetime grid."""
        try:
            from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Ax2, gp_Vec
            from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox, BRepPrimAPI_MakeCone
            from OCC.Core.BRep import BRep_Builder
            from OCC.Core.TopoDS import TopoDS_Compound
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
            
            builder = BRep_Builder()
            compound = TopoDS_Compound()
            builder.MakeCompound(compound)
            
            # Create the outer display box (wireframe)
            half_size = box_size / 2
            corner1 = gp_Pnt(-half_size, -half_size, -half_size)
            corner2 = gp_Pnt(half_size, half_size, half_size)
            
            # Create box edges for wireframe
            box_points = [
                gp_Pnt(-half_size, -half_size, -half_size),  # 0
                gp_Pnt(half_size, -half_size, -half_size),   # 1
                gp_Pnt(half_size, half_size, -half_size),    # 2
                gp_Pnt(-half_size, half_size, -half_size),   # 3
                gp_Pnt(-half_size, -half_size, half_size),   # 4
                gp_Pnt(half_size, -half_size, half_size),    # 5
                gp_Pnt(half_size, half_size, half_size),     # 6
                gp_Pnt(-half_size, half_size, half_size),    # 7
            ]
            
            # Create box edges
            box_edges = [
                (0, 1), (1, 2), (2, 3), (3, 0),  # bottom face
                (4, 5), (5, 6), (6, 7), (7, 4),  # top face
                (0, 4), (1, 5), (2, 6), (3, 7),  # vertical edges
            ]
            
            for start_idx, end_idx in box_edges:
                edge = BRepBuilderAPI_MakeEdge(box_points[start_idx], box_points[end_idx]).Edge()
                builder.Add(compound, edge)
            
            # Create light cone at center
            origin = gp_Pnt(0, 0, 0)
            
            # Future light cone
            future_axis = gp_Ax2(origin, gp_Dir(0, 0, 1))
            future_cone = BRepPrimAPI_MakeCone(future_axis, 0.5, cone_radius, cone_radius/2).Shape()
            builder.Add(compound, future_cone)
            
            # Past light cone
            past_apex = gp_Pnt(0, 0, -cone_radius/2)
            past_axis = gp_Ax2(past_apex, gp_Dir(0, 0, 1))
            past_cone = BRepPrimAPI_MakeCone(past_axis, cone_radius, 0.5, cone_radius/2).Shape()
            builder.Add(compound, past_cone)
            
            # Add spacetime grid if requested
            if show_grid:
                grid_lines = self._create_spacetime_grid(box_size, grid_spacing)
                for line in grid_lines:
                    builder.Add(compound, line)
            
            return compound
            
        except Exception as e:
            print(f"Error creating display box: {e}")
            return None
    
    def _create_spacetime_grid(self, box_size: float, spacing: float):
        """Create a spacetime coordinate grid."""
        try:
            from OCC.Core.gp import gp_Pnt
            from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge
            
            lines = []
            half_size = box_size / 2
            
            # Create grid lines in XY plane (space-space)
            for x in np.arange(-half_size, half_size + spacing, spacing):
                # Lines parallel to Y axis
                start = gp_Pnt(x, -half_size, 0)
                end = gp_Pnt(x, half_size, 0)
                line = BRepBuilderAPI_MakeEdge(start, end).Edge()
                lines.append(line)
                
            for y in np.arange(-half_size, half_size + spacing, spacing):
                # Lines parallel to X axis
                start = gp_Pnt(-half_size, y, 0)
                end = gp_Pnt(half_size, y, 0)
                line = BRepBuilderAPI_MakeEdge(start, end).Edge()
                lines.append(line)
            
            # Create time-like grid lines (Z axis represents time)
            for x in np.arange(-half_size, half_size + spacing*2, spacing*2):
                for y in np.arange(-half_size, half_size + spacing*2, spacing*2):
                    start = gp_Pnt(x, y, -half_size)
                    end = gp_Pnt(x, y, half_size)
                    line = BRepBuilderAPI_MakeEdge(start, end).Edge()
                    lines.append(line)
            
            return lines
            
        except Exception as e:
            print(f"Error creating spacetime grid: {e}")
            return []


# ...existing code...
