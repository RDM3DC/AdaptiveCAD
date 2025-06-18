"""Spacetime Visualization Toolkit for AdaptiveCAD.

Extends the existing adaptivecad.spacetime module with advanced 4D+ visualization,
light cone exploration, and curvature simulation capabilities.
"""

import numpy as np
import math
from typing import List, Tuple, Optional, Dict, Any, Callable
from dataclasses import dataclass, field

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
                    
                    # Add unselect button
                    from PySide6.QtWidgets import QPushButton, QHBoxLayout, QWidget
                    button_widget = QWidget()
                    button_layout = QHBoxLayout(button_widget)
                    
                    self.unselect_button = QPushButton("Unselect All Objects")
                    self.unselect_button.clicked.connect(self.unselect_all_objects)
                    button_layout.addWidget(self.unselect_button)
                    
                    layout.addRow("Actions:", button_widget)
                
                def unselect_all_objects(self):
                    """Unselect all objects in the display."""
                    try:
                        # Get the main window from parent hierarchy
                        parent = self.parent()
                        while parent and not hasattr(parent, 'view'):
                            parent = parent.parent()
                        
                        if parent and hasattr(parent, 'view') and hasattr(parent.view, '_display'):
                            parent.view._display.ClearSelected()
                            parent.view._display.Context.ClearSelected(True)
                            parent.view._display.Repaint()
                            
                        # Update status
                        if parent and hasattr(parent, 'statusBar'):
                            parent.statusBar().showMessage("All objects unselected", 2000)
                    except Exception as e:
                        print(f"Error unselecting objects: {e}")
            
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
                    
                    # Add unselect button
                    from PySide6.QtWidgets import QPushButton, QHBoxLayout, QWidget
                    button_widget = QWidget()
                    button_layout = QHBoxLayout(button_widget)
                    
                    self.unselect_button = QPushButton("Unselect All Objects")
                    self.unselect_button.clicked.connect(self.unselect_all_objects)
                    button_layout.addWidget(self.unselect_button)
                    
                    layout.addRow("Actions:", button_widget)
                
                def unselect_all_objects(self):
                    """Unselect all objects in the display."""
                    try:
                        # Get the main window from parent hierarchy
                        parent = self.parent()
                        while parent and not hasattr(parent, 'view'):
                            parent = parent.parent()
                        
                        if parent and hasattr(parent, 'view') and hasattr(parent.view, '_display'):
                            parent.view._display.ClearSelected()
                            parent.view._display.Context.ClearSelected(True)
                            parent.view._display.Repaint()
                            
                        # Update status
                        if parent and hasattr(parent, 'statusBar'):
                            parent.statusBar().showMessage("All objects unselected", 2000)
                    except Exception as e:
                        print(f"Error unselecting objects: {e}")
            
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


def unselect_all_objects_utility(display_object):
    """Utility function to unselect all objects from any display object.
    
    Args:
        display_object: The display object (usually mw.view._display)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if hasattr(display_object, 'ClearSelected'):
            display_object.ClearSelected()
            
        if hasattr(display_object, 'Context'):
            display_object.Context.ClearSelected(True)
            
        if hasattr(display_object, 'Repaint'):
            display_object.Repaint()
            
        return True
        
    except Exception as e:
        print(f"Error in unselect_all_objects_utility: {e}")
        return False


class UnselectAllObjectsCmd:
    """Command to unselect all objects in the display."""
    
    def __init__(self):
        self.name = "Unselect All Objects"
        
    def run(self, mw):
        """Unselect all objects in the main window display."""
        try:
            if hasattr(mw, 'view') and hasattr(mw.view, '_display'):
                # Clear selection in the display
                mw.view._display.ClearSelected()
                
                # Also clear from context if available
                if hasattr(mw.view._display, 'Context'):
                    mw.view._display.Context.ClearSelected(True)
                
                # Repaint the display to show changes
                mw.view._display.Repaint()
                
                # Update status bar
                if hasattr(mw, 'win') and hasattr(mw.win, 'statusBar'):
                    mw.win.statusBar().showMessage("All objects unselected", 2000)
                else:
                    print("All objects unselected")
                    
            else:
                error_msg = "No display available for unselecting objects"
                if hasattr(mw, 'win'):
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.information(mw.win, "Information", error_msg)
                else:
                    print(error_msg)
                    
        except Exception as e:
            error_msg = f"Error unselecting objects: {str(e)}"
            if hasattr(mw, 'win'):
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.critical(mw.win, "Error", error_msg)
            else:
                print(error_msg)


class ToolbarUnselectCmd:
    """Toolbar command to unselect all objects and clear selection errors."""
    
    def __init__(self):
        self.name = "Unselect All"
        self.tooltip = "Unselect all objects and clear selection errors"
        self.icon = None  # Can be set to an icon path if available
        self.shortcut = "Ctrl+D"  # Keyboard shortcut
        
    def run(self, mw):
        """Execute the unselect command from toolbar."""
        try:
            success = False
            
            # Method 1: Try clearing through the display
            if hasattr(mw, 'view') and hasattr(mw.view, '_display'):
                display = mw.view._display
                
                # Clear selected objects
                if hasattr(display, 'ClearSelected'):
                    display.ClearSelected()
                    success = True
                
                # Clear from interactive context
                if hasattr(display, 'Context'):
                    try:
                        display.Context.ClearSelected(True)
                        # Also try to clear any highlighted objects
                        if hasattr(display.Context, 'ClearDetected'):
                            display.Context.ClearDetected()
                    except:
                        pass
                
                # Clear any error highlighting
                if hasattr(display, 'EraseSelected'):
                    try:
                        display.EraseSelected()
                    except:
                        pass
                
                # Force repaint to clear visual artifacts
                if hasattr(display, 'Repaint'):
                    display.Repaint()
                elif hasattr(display, 'Update'):
                    display.Update()
                
                # Try to fit all objects in view to refresh display
                if hasattr(display, 'FitAll'):
                    try:
                        display.FitAll()
                    except:
                        pass
            
            # Method 2: Try clearing through document if available
            try:
                from adaptivecad.command_defs import DOCUMENT
                if DOCUMENT:
                    # Clear any selection state in document features
                    for feature in DOCUMENT:
                        if hasattr(feature, 'selected'):
                            feature.selected = False
            except ImportError:
                pass
            
            # Method 3: Try to clear Qt selection models if available
            if hasattr(mw, 'win'):
                try:
                    # Clear any QTreeView or QListView selections
                    for child in mw.win.findChildren('QAbstractItemView'):
                        if hasattr(child, 'clearSelection'):
                            child.clearSelection()
                except:
                    pass
            
            # Update status with feedback
            if hasattr(mw, 'win') and hasattr(mw.win, 'statusBar'):
                if success:
                    mw.win.statusBar().showMessage("All objects unselected - selection errors cleared", 3000)
                else:
                    mw.win.statusBar().showMessage("Attempted to clear selections", 2000)
            else:
                print("Unselect all: Selection cleared and errors removed")
                
        except Exception as e:
            error_msg = f"Error clearing selections: {str(e)}"
            if hasattr(mw, 'win'):
                try:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(mw.win, "Unselect Warning", error_msg)
                except:
                    print(error_msg)
            else:
                print(error_msg)


class QuickUnselectCmd:
    """Quick unselect command with minimal overhead for frequent use."""
    
    def __init__(self):
        self.name = "Quick Unselect"
        self.tooltip = "Quick unselect (no confirmation)"
        
    def run(self, mw):
        """Quick unselect without status messages."""
        try:
            if hasattr(mw, 'view') and hasattr(mw.view, '_display'):
                display = mw.view._display
                display.ClearSelected()
                if hasattr(display, 'Context'):
                    display.Context.ClearSelected(True)
                display.Repaint()
        except:
            pass  # Fail silently for quick operation


def clear_all_selection_errors(display_object, verbose=False):
    """Comprehensive function to clear all types of selection errors and visual artifacts.
    
    Args:
        display_object: The OpenCASCADE display object
        verbose (bool): If True, print detailed status messages
        
    Returns:
        list: List of actions taken to clear errors
    """
    actions_taken = []
    
    try:
        if not display_object:
            return ["Error: No display object provided"]
        
        # 1. Clear basic selections
        if hasattr(display_object, 'ClearSelected'):
            display_object.ClearSelected()
            actions_taken.append("Cleared basic selections")
        
        # 2. Clear context selections
        if hasattr(display_object, 'Context'):
            context = display_object.Context
            
            # Clear selected objects
            if hasattr(context, 'ClearSelected'):
                context.ClearSelected(True)
                actions_taken.append("Cleared context selections")
            
            # Clear detected/highlighted objects
            if hasattr(context, 'ClearDetected'):
                context.ClearDetected()
                actions_taken.append("Cleared detected objects")
            
            # Clear any pre-selection highlighting
            if hasattr(context, 'ClearPrs'):
                try:
                    context.ClearPrs()
                    actions_taken.append("Cleared presentation objects")
                except:
                    pass
        
        # 3. Clear displayed shapes with errors
        if hasattr(display_object, 'EraseSelected'):
            try:
                display_object.EraseSelected()
                actions_taken.append("Erased selected shapes")
            except:
                pass
        
        # 4. Try to clear all and redisplay (nuclear option)
        if hasattr(display_object, 'EraseAll'):
            try:
                # Store current shapes before erasing
                displayed_shapes = []
                if hasattr(display_object, 'DisplayedShapes'):
                    displayed_shapes = display_object.DisplayedShapes()
                
                # Clear everything
                display_object.EraseAll()
                actions_taken.append("Cleared all displayed objects")
                
                # Redisplay without selection
                for shape in displayed_shapes:
                    if hasattr(display_object, 'DisplayShape'):
                        display_object.DisplayShape(shape, update=False)
                
                if displayed_shapes:
                    actions_taken.append(f"Redisplayed {len(displayed_shapes)} objects")
                    
            except Exception as e:
                actions_taken.append(f"Error during full refresh: {e}")
        
        # 5. Force display update
        update_methods = ['Repaint', 'Update', 'UpdateCurrentViewer', 'Redraw']
        for method in update_methods:
            if hasattr(display_object, method):
                try:
                    getattr(display_object, method)()
                    actions_taken.append(f"Called {method}")
                    break
                except:
                    continue
        
        # 6. Reset view if needed
        if hasattr(display_object, 'FitAll'):
            try:
                display_object.FitAll()
                actions_taken.append("Reset view to fit all objects")
            except:
                pass
        
        if verbose:
            for action in actions_taken:
                print(f"Selection Error Clear: {action}")
                
    except Exception as e:
        error_msg = f"Error in clear_all_selection_errors: {e}"
        actions_taken.append(error_msg)
        if verbose:
            print(error_msg)
    
    return actions_taken


class ErrorClearingUnselectCmd:
    """Advanced unselect command specifically designed to clear selection errors."""
    
    def __init__(self):
        self.name = "Clear Selection Errors"
        self.tooltip = "Clear all selection errors and visual artifacts"
        
    def run(self, mw):
        """Run comprehensive error clearing."""
        try:
            if not (hasattr(mw, 'view') and hasattr(mw.view, '_display')):
                raise Exception("No display available")
            
            # Run comprehensive error clearing
            actions = clear_all_selection_errors(mw.view._display, verbose=True)
            
            # Report results
            if hasattr(mw, 'win') and hasattr(mw.win, 'statusBar'):
                success_count = len([a for a in actions if not a.startswith("Error")])
                mw.win.statusBar().showMessage(
                    f"Selection errors cleared: {success_count} actions completed", 
                    4000
                )
            
            # Show detailed results in console
            print("=== Selection Error Clearing Results ===")
            for action in actions:
                print(f"  • {action}")
            print("========================================")
            
        except Exception as e:
            error_msg = f"Failed to clear selection errors: {str(e)}"
            if hasattr(mw, 'win'):
                try:
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.critical(mw.win, "Error Clearing Failed", error_msg)
                except:
                    print(error_msg)
            else:
                print(error_msg)


# Enhanced Multiverse Exploration Toolkit
@dataclass
class Config:
    """Configuration constants for multiverse exploration."""
    TEMP_MIN_COMPLEXITY: float = 1e-4
    TEMP_MAX_COMPLEXITY: float = 1e12
    DEFAULT_GRID_SIZE: int = 10
    ANTHROPIC_THRESHOLD: float = 0.3
    UNIVERSE_AGE: float = 13.8e9
    FINE_STRUCTURE_CONSTANT: float = 1.0/137
    STELLAR_LIFETIME_MIN: float = 1e8
    STELLAR_LIFETIME_MAX: float = 1e11
    NUCLEAR_FUSION_MIN: float = 1e-4
    NUCLEAR_FUSION_MAX: float = 1e-2


def gaussian_weight(value: float, optimal: float, scale: float) -> float:
    """Calculate a Gaussian weight for a parameter relative to its optimal value."""
    return math.exp(-scale * (value - optimal) ** 2)


@dataclass
class UniverseParameters:
    """Enhanced universe parameters with validation and extensibility."""
    
    # Core physical constants
    constants: Dict[str, float] = field(default_factory=lambda: {
        "c": 1.0,
        "hbar": 1.0, 
        "G": 1.0,
        "alpha": Config.FINE_STRUCTURE_CONSTANT,
        "m_electron": 1.0,
        "m_proton": 1836.0,  # Proton-electron mass ratio
        "Lambda": 0.0,
        "g_weak": 1.0,
        "g_strong": 1.0
    })
    
    # Spacetime structure
    spacetime_dimensions: int = 4
    signature: Tuple[int, int] = (1, 3)  # (timelike, spacelike)
    
    # Initial conditions
    initial_entropy: float = 1.0
    initial_temperature: float = 1.0
    
    # Computed metrics (not set during initialization)
    stability_score: float = field(default=0.0, init=False)
    complexity_measure: float = field(default=0.0, init=False) 
    habitability_index: float = field(default=0.0, init=False)
    
    def __post_init__(self):
        """Validate physical constraints."""
        if self.constants["c"] <= 0:
            raise ValueError("Speed of light must be positive")
        if self.spacetime_dimensions < 1:
            raise ValueError("Spacetime dimensions must be at least 1")
        if self.constants["G"] <= 0:
            raise ValueError("Gravitational constant must be positive")
        if self.constants["alpha"] <= 0:
            raise ValueError("Fine structure constant must be positive")
    
    @property
    def alpha(self) -> float:
        return self.constants["alpha"]
    
    @property 
    def G(self) -> float:
        return self.constants["G"]
    
    @property
    def Lambda(self) -> float:
        return self.constants["Lambda"]
    
    @property
    def m_proton(self) -> float:
        return self.constants["m_proton"]
    
    @property
    def m_electron(self) -> float:
        return self.constants["m_electron"]
    
    def to_tuple(self) -> tuple:
        """Convert to tuple for caching purposes."""
        return tuple(sorted(self.constants.items())) + (
            self.spacetime_dimensions,
            self.signature,
            self.initial_entropy,
            self.initial_temperature
        )


class UniverseSimulator:
    """Enhanced universe simulator with improved physics and performance."""
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._cache = {}
    
    def simulate_universe_evolution(self, params: UniverseParameters, time_steps: int = 100) -> Dict[str, List[float]]:
        """Simulate universe evolution with improved cosmological model."""
        evolution = {
            "time": [],
            "scale_factor": [], 
            "temperature": [],
            "entropy": [],
            "complexity": []
        }
        
        a_0 = 1.0
        T_0 = params.initial_temperature
        S_0 = params.initial_entropy
        
        for step in range(time_steps):
            t = step / time_steps * self.config.UNIVERSE_AGE
            
            # Enhanced Friedmann equation evolution
            if params.Lambda > 0:
                # De Sitter expansion
                H = math.sqrt(params.Lambda / 3)
                a_t = a_0 * math.exp(H * t / 1e9)
            elif params.Lambda < 0:
                # Big Crunch scenario
                H = math.sqrt(-params.Lambda / 3)
                t_collapse = math.pi / (2 * H * 1e9)
                if t < t_collapse:
                    a_t = a_0 * math.sin(H * t / 1e9)
                else:
                    a_t = 0  # Universe has collapsed
            else:
                # Matter-dominated expansion
                a_t = a_0 * (t / 1e9) ** (2/3) if t > 0 else a_0
            
            # Temperature evolution (adiabatic cooling)
            T_t = T_0 / a_t if a_t > 0 else 0
            
            # Entropy evolution (comoving volume)
            S_t = S_0 * a_t**3 if a_t > 0 else S_0
            
            # Enhanced complexity calculation
            complexity_t = self._calculate_complexity(params, t, a_t, T_t)
            
            evolution["time"].append(t)
            evolution["scale_factor"].append(a_t)
            evolution["temperature"].append(T_t)
            evolution["entropy"].append(S_t)
            evolution["complexity"].append(complexity_t)
        
        return evolution
    
    def _calculate_complexity(self, params: UniverseParameters, time: float, 
                            scale_factor: float, temperature: float) -> float:
        """Enhanced complexity calculation based on physical processes."""
        complexity = 0.0
        
        if scale_factor <= 0:
            return 0.0
        
        # Nuclear fusion feasibility
        nuclear_rate = (params.constants["g_strong"] * params.alpha**2 * 
                       math.exp(-params.m_proton / max(temperature, 1e-10)))
        
        if self.config.NUCLEAR_FUSION_MIN < nuclear_rate < self.config.NUCLEAR_FUSION_MAX:
            complexity += 0.4
        
        # Gravitational structure formation
        jeans_mass = (temperature / (params.G * params.m_proton))**(3/2)
        if 1e-6 < jeans_mass < 1e6:  # Suitable for star formation
            complexity += 0.3
        
        # Chemical complexity (molecular formation)
        binding_energy = params.alpha**2 * params.m_electron
        if temperature < binding_energy and temperature > binding_energy / 100:
            complexity += 0.2
        
        # Electromagnetic interactions
        em_factor = gaussian_weight(params.alpha, self.config.FINE_STRUCTURE_CONSTANT, 100)
        complexity += 0.1 * em_factor
        
        return min(1.0, complexity)
    
    def calculate_stability_score(self, params: UniverseParameters) -> float:
        """Enhanced stability calculation with physical grounding."""
        stability = 0.0
        
        # Electromagnetic stability
        alpha_factor = gaussian_weight(params.alpha, self.config.FINE_STRUCTURE_CONSTANT, 100)
        stability += 0.25 * alpha_factor
        
        # Gravitational stability (prevent immediate collapse or runaway expansion)
        if abs(params.Lambda) < 1.0:  # Reasonable cosmological constant
            lambda_factor = gaussian_weight(params.Lambda, 0.0, 1.0)
            stability += 0.25 * lambda_factor
        
        # Nuclear stability
        if 0.1 < params.constants["g_strong"] < 10.0:
            stability += 0.25
        
        # Mass ratio stability
        mass_ratio = params.m_proton / params.m_electron
        if 1000 < mass_ratio < 10000:  # Allows for atomic structure
            stability += 0.25
        
        return min(1.0, stability)
    
    def calculate_habitability_index(self, params: UniverseParameters) -> float:
        """Enhanced habitability calculation with anthropic constraints."""
        habitability = 0.0
        
        # Stellar lifetime constraint
        stellar_lifetime = 1.0 / (params.G * params.alpha**2 * params.m_proton)
        if self.config.STELLAR_LIFETIME_MIN < stellar_lifetime < self.config.STELLAR_LIFETIME_MAX:
            habitability += 0.3
        
        # Spacetime dimensionality (3+1 optimal for stable orbits and waves)
        if params.spacetime_dimensions == 4 and params.signature == (1, 3):
            habitability += 0.2
        
        # Chemical complexity potential
        if 0.5 < params.alpha / self.config.FINE_STRUCTURE_CONSTANT < 2.0:
            habitability += 0.2
        
        # Gravitational binding vs expansion
        if -0.1 < params.Lambda < 0.1:
            habitability += 0.15
        
        # Nuclear processes (allows for element formation)
        if 0.5 < params.constants["g_strong"] < 2.0:
            habitability += 0.15
        
        return min(1.0, habitability)


class ParameterSpaceExplorer:
    """Enhanced parameter space exploration with performance optimizations."""
    
    def __init__(self, simulator: UniverseSimulator):
        self.simulator = simulator
        self._cache = {}
    
    def generate_parameter_grid(self, parameter_ranges: Dict[str, Tuple[float, float]], 
                              n_samples: int = 100, method: str = "latin_hypercube") -> List[UniverseParameters]:
        """Generate parameter grid using efficient sampling methods."""
        try:
            if method == "latin_hypercube":
                from scipy.stats import qmc
                sampler = qmc.LatinHypercube(d=len(parameter_ranges))
                samples = sampler.random(n=n_samples)
            else:
                # Fallback to uniform random sampling
                samples = np.random.random((n_samples, len(parameter_ranges)))
        except ImportError:
            # Fallback if scipy not available
            samples = np.random.random((n_samples, len(parameter_ranges)))
        
        universes = []
        param_names = list(parameter_ranges.keys())
        
        for sample in samples:
            params = UniverseParameters()
            
            # Set parameter values
            for i, param_name in enumerate(param_names):
                min_val, max_val = parameter_ranges[param_name]
                value = min_val + sample[i] * (max_val - min_val)
                
                if param_name in params.constants:
                    params.constants[param_name] = value
                else:
                    setattr(params, param_name, value)
            
            # Calculate metrics
            try:
                params.stability_score = self.simulator.calculate_stability_score(params)
                params.complexity_measure = self._estimate_max_complexity_cached(params)
                params.habitability_index = self.simulator.calculate_habitability_index(params)
                universes.append(params)
            except Exception as e:
                print(f"Error evaluating universe parameters: {e}")
                continue
        
        return universes
    
    def _estimate_max_complexity_cached(self, params: UniverseParameters) -> float:
        """Cached complexity estimation to improve performance."""
        params_key = params.to_tuple()
        
        if params_key in self._cache:
            return self._cache[params_key]
        
        try:
            evolution = self.simulator.simulate_universe_evolution(params, 50)
            max_complexity = max(evolution["complexity"]) if evolution["complexity"] else 0.0
            self._cache[params_key] = max_complexity
            return max_complexity
        except Exception as e:
            print(f"Error in complexity estimation: {e}")
            return 0.0
    
    def analyze_parameter_sensitivity(self, base_params: UniverseParameters, 
                                    parameter_name: str, variation_range: Tuple[float, float],
                                    steps: int = 20) -> Dict[str, List[float]]:
        """Analyze sensitivity of universe properties to parameter changes."""
        min_val, max_val = variation_range
        parameter_values = np.linspace(min_val, max_val, steps)
        
        results = {
            "parameter_values": [],
            "stability_scores": [],
            "habitability_indices": [],
            "complexity_measures": []
        }
        
        for value in parameter_values:
            # Create modified parameters
            test_params = UniverseParameters()
            test_params.constants.update(base_params.constants)
            test_params.spacetime_dimensions = base_params.spacetime_dimensions
            test_params.signature = base_params.signature
            
            if parameter_name in test_params.constants:
                test_params.constants[parameter_name] = value
            else:
                setattr(test_params, parameter_name, value)
            
            try:
                # Calculate metrics
                stability = self.simulator.calculate_stability_score(test_params)
                habitability = self.simulator.calculate_habitability_index(test_params)
                complexity = self._estimate_max_complexity_cached(test_params)
                
                results["parameter_values"].append(value)
                results["stability_scores"].append(stability)
                results["habitability_indices"].append(habitability)
                results["complexity_measures"].append(complexity)
                
            except Exception as e:
                print(f"Error in sensitivity analysis at {parameter_name}={value}: {e}")
                continue
        
        return results
    
    def find_optimal_universes(self, universes: List[UniverseParameters], 
                             criteria: Optional[callable] = None) -> List[UniverseParameters]:
        """Find optimal universes using custom or default criteria."""
        if criteria is None:
            # Default: weighted combination of all metrics
            criteria = lambda u: (0.4 * u.habitability_index + 
                                0.3 * u.stability_score + 
                                0.3 * u.complexity_measure)
        
        try:
            sorted_universes = sorted(universes, key=criteria, reverse=True)
            top_count = max(1, len(sorted_universes) // 10)
            return sorted_universes[:top_count]
        except Exception as e:
            print(f"Error in optimization: {e}")
            return universes[:min(10, len(universes))]


class MultiverseLandscape:
    """Enhanced multiverse landscape with robust visualization."""
    
    def __init__(self):
        self.universes: List[UniverseParameters] = []
    
    def add_universe_sample(self, universe: UniverseParameters):
        """Add a universe sample to the landscape."""
        self.universes.append(universe)
    
    def create_landscape_field(self, parameter1: str, parameter2: str, 
                             metric: str = "habitability") -> Optional['NDField']:
        """Create a landscape field with robust interpolation."""
        if not self.universes:
            raise ValueError("No universes in landscape")
        
        try:
            # Extract parameter and metric values
            param1_vals = np.array([getattr(u, parameter1) if hasattr(u, parameter1) 
                                  else u.constants.get(parameter1, 0) for u in self.universes])
            param2_vals = np.array([getattr(u, parameter2) if hasattr(u, parameter2)
                                  else u.constants.get(parameter2, 0) for u in self.universes])
            
            metric_attr = f"{metric}_index" if metric == "habitability" else f"{metric}_score"
            if metric == "complexity":
                metric_attr = "complexity_measure"
            
            metric_vals = np.array([getattr(u, metric_attr, 0) for u in self.universes])
            
            # Create regular grid with interpolation
            try:
                from scipy.interpolate import griddata
                grid_size = 50
                grid_x, grid_y = np.meshgrid(
                    np.linspace(np.min(param1_vals), np.max(param1_vals), grid_size),
                    np.linspace(np.min(param2_vals), np.max(param2_vals), grid_size)
                )
                grid_z = griddata((param1_vals, param2_vals), metric_vals, 
                                (grid_x, grid_y), method="cubic", fill_value=0)
                
                if HAS_SPACETIME:
                    from adaptivecad.ndfield import NDField
                    return NDField((grid_size, grid_size), grid_z.flatten())
                else:
                    # Fallback implementation
                    return type('NDField', (), {
                        'grid_shape': (grid_size, grid_size),
                        'data': grid_z.flatten()
                    })()
                    
            except ImportError:
                # Fallback without scipy interpolation
                grid_size = int(math.sqrt(len(self.universes)))
                if grid_size * grid_size != len(self.universes):
                    grid_size = max(1, int(math.sqrt(len(self.universes))))
                
                if HAS_SPACETIME:
                    from adaptivecad.ndfield import NDField
                    return NDField((grid_size, grid_size), metric_vals[:grid_size*grid_size])
                else:
                    return type('NDField', (), {
                        'grid_shape': (grid_size, grid_size),
                        'data': metric_vals[:grid_size*grid_size]
                    })()
                    
        except Exception as e:
            print(f"Error creating landscape field: {e}")
            return None
    
    def find_anthropic_islands(self, threshold: float = 0.3) -> List[List[UniverseParameters]]:
        """Find clusters of universes with high habitability."""
        if not self.universes:
            return []
        
        # Filter universes above threshold
        viable_universes = [u for u in self.universes if u.habitability_index >= threshold]
        
        if not viable_universes:
            return []
        
        # Simple clustering based on parameter distance
        islands = []
        processed = set()
        
        for universe in viable_universes:
            if id(universe) in processed:
                continue
            
            # Start new island
            island = [universe]
            processed.add(id(universe))
            
            # Find nearby universes
            for other in viable_universes:
                if id(other) in processed:
                    continue
                
                if self._parameter_distance(universe, other) < 0.3:
                    island.append(other)
                    processed.add(id(other))            
            islands.append(island)
