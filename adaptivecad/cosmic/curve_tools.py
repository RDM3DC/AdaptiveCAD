"""Cosmic Curve Tools for AdaptiveCAD.

Advanced curve generation and manipulation tools for cosmic exploration,
including bizarre curves, cosmic splines, and nd field exploration.
"""

import numpy as np
import math
from typing import List, Tuple, Optional, Dict, Any

try:
    from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QSpinBox, QComboBox, QLabel
    from adaptivecad.command_defs import Feature, DOCUMENT, BaseCmd, rebuild_scene
    from adaptivecad.ndfield import NDField
    from adaptivecad.geom.bspline import BSplineCurve
    from adaptivecad.linalg import Vec3
    from adaptivecad.geom.hyperbolic import pi_a_over_pi
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False

# Try to import OpenCascade independently of other dependencies
# This ensures we can create shapes even if some internal modules are missing
try:
    from OCC.Core.gp import gp_Pnt
    from OCC.Core.TColgp import TColgp_Array1OfPnt
    from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCC.Core.GeomAPI import GeomAPI_PointsToBSpline  # Fixed: correct class name is GeomAPI_PointsToBSpline
    from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
    HAS_OCC = True
    print("[curve_tools] Successfully imported OpenCascade modules (HAS_OCC = True)")
except ImportError as e:
    HAS_OCC = False
    print(f"[curve_tools] Failed to import OpenCascade modules: {e} (HAS_OCC = False)")


class BizarreCurveFeature(Feature):
    """A bizarre curve with hyperbolic and transcendental distortions."""
    
    def __init__(self, base_radius: float, height: float, frequency: float, 
                 distortion: float, segments: int):
        print(f"[BizarreCurveFeature] __init__ called with base_radius={base_radius}, height={height}, frequency={frequency}, distortion={distortion}, segments={segments}")
        params = {
            "base_radius": base_radius,
            "height": height, 
            "frequency": frequency,
            "distortion": distortion,
            "segments": segments
        }
        shape = self._make_shape(params)
        print(f"[BizarreCurveFeature] Shape created: {shape}")
        super().__init__("BizarreCurve", params, shape)
        
    def _make_shape(self, params):
        """Create the bizarre curve shape using mathematical distortions."""
        print(f"[BizarreCurveFeature] _make_shape called with params: {params}")
        if not HAS_OCC:
            print("[BizarreCurveFeature] HAS_OCC is False, returning None")
            print("[BizarreCurveFeature] This means OpenCascade (pythonocc-core) was not detected")
            print("[BizarreCurveFeature] Ensure the correct conda environment with pythonocc-core is active")
            return None
        
        # If we get here, HAS_OCC is True
        print("[BizarreCurveFeature] HAS_OCC is True, creating shape...")
        base_radius = params["base_radius"]
        height = params["height"]
        frequency = params["frequency"]
        distortion = params["distortion"]
        segments = params["segments"]
        points = TColgp_Array1OfPnt(1, segments)
        for i in range(segments):
            t = i / (segments - 1)  # Parameter from 0 to 1
            angle = 2 * math.pi * frequency * t
            try:
                # Add default kappa=1.0 parameter to pi_a_over_pi call
                hyperbolic_factor = pi_a_over_pi(t * distortion, kappa=1.0)
            except Exception as e:
                print(f"[BizarreCurveFeature] pi_a_over_pi exception: {e}")
                hyperbolic_factor = 1.0
            x = base_radius * math.cos(angle) * hyperbolic_factor
            y = base_radius * math.sin(angle) * hyperbolic_factor
            z = height * t + distortion * math.sin(10 * angle) * math.exp(-2 * t)
            chaos_x = 0.1 * distortion * math.sin(23 * angle + t)
            chaos_y = 0.1 * distortion * math.cos(17 * angle - t)
            chaos_z = 0.05 * distortion * math.sin(13 * angle * t)
            pt = gp_Pnt(x + chaos_x, y + chaos_y, z + chaos_z)
            points.SetValue(i + 1, pt)
            print(f"[BizarreCurveFeature] Point {i}: {pt}")        # Create B-spline curve
        try:
            # Using GeomAPI_PointsToBSpline (correct class name)
            spline_builder = GeomAPI_PointsToBSpline(points, 3, 8, False, 1.0e-6)
            spline = spline_builder.Curve()
            edge = BRepBuilderAPI_MakeEdge(spline).Edge()
            print(f"[BizarreCurveFeature] Spline edge created: {edge}")
            return edge
        except Exception as e:
            print(f"[BizarreCurveFeature] Spline creation failed: {e}")
            wire_builder = BRepBuilderAPI_MakeWire()
            for i in range(segments - 1):
                edge = BRepBuilderAPI_MakeEdge(points.Value(i + 1), points.Value(i + 2)).Edge()
                wire_builder.Add(edge)
            wire = wire_builder.Wire()
            print(f"[BizarreCurveFeature] Polyline wire created: {wire}")
            return wire


class CosmicSplineFeature(Feature):
    """A cosmic spline that follows spacetime curvature patterns."""
    
    def __init__(self, control_points: List[Tuple[float, float, float]], 
                 degree: int, cosmic_curvature: float):
        params = {
            "control_points": control_points,
            "degree": degree,
            "cosmic_curvature": cosmic_curvature
        }
        shape = self._make_shape(params)
        super().__init__("CosmicSpline", params, shape)
    
    def _make_shape(self, params):
        """Create cosmic spline with spacetime curvature effects."""
        if not HAS_OCC:
            return None
            
        control_points = params["control_points"]
        degree = params["degree"]
        cosmic_curvature = params["cosmic_curvature"]
        
        # Transform control points with cosmic curvature
        transformed_points = []
        for i, (x, y, z) in enumerate(control_points):
            # Apply spacetime metric distortion
            r = math.sqrt(x*x + y*y + z*z)
            if r > 1e-10:
                try:
                    curvature_factor = pi_a_over_pi(r * cosmic_curvature)
                except:
                    curvature_factor = 1.0
                
                # Schwarzschild-like metric transformation
                scale = 1.0 + cosmic_curvature * math.exp(-r / 10.0)
                
                transformed_points.append((
                    x * curvature_factor * scale,
                    y * curvature_factor * scale, 
                    z * curvature_factor
                ))
            else:
                transformed_points.append((x, y, z))
        
        # Create OCC points array
        points = TColgp_Array1OfPnt(1, len(transformed_points))
        for i, (x, y, z) in enumerate(transformed_points):
            points.SetValue(i + 1, gp_Pnt(x, y, z))
        
        # Create cosmic spline
        try:
            spline_builder = GeomAPI_PointsToBSpline(points, min(degree, len(transformed_points) - 1), 8, False, 1.0e-6)
            spline = spline_builder.Curve()
            edge = BRepBuilderAPI_MakeEdge(spline).Edge()
            return edge
        except:
            return None


class NDFieldExplorerFeature(Feature):
    """N-dimensional field visualization and exploration."""
    
    def __init__(self, dimensions: int, grid_size: int, field_type: str):
        params = {
            "dimensions": dimensions,
            "grid_size": grid_size,
            "field_type": field_type
        }
        shape = self._make_shape(params)
        super().__init__("NDFieldExplorer", params, shape)
    
    def _make_shape(self, params):
        """Create 3D visualization of N-dimensional field."""
        if not HAS_OCC:
            return None
            
        dimensions = params["dimensions"]
        grid_size = params["grid_size"]
        field_type = params["field_type"]
        
        # Create sample grid for visualization (project to 3D)
        grid_shape = [grid_size] * dimensions
        
        # Generate field values based on type
        if field_type == "scalar_wave":
            values = self._generate_scalar_wave(grid_shape)
        elif field_type == "quantum_field":
            values = self._generate_quantum_field(grid_shape)
        elif field_type == "cosmic_web":
            values = self._generate_cosmic_web(grid_shape)
        else:
            values = np.random.random(grid_shape)
        
        # Create NDField
        self.ndfield = NDField(grid_shape, values)
        
        # Visualize as point cloud or surface (simplified)
        return self._create_visualization_shape(grid_size)
    
    def _generate_scalar_wave(self, grid_shape):
        """Generate scalar wave field values."""
        total_size = np.prod(grid_shape)
        indices = np.unravel_index(np.arange(total_size), grid_shape)
        
        # Multi-dimensional wave
        values = np.zeros(total_size)
        for i in range(len(grid_shape)):
            coord = indices[i] / grid_shape[i] * 2 * np.pi
            values += np.sin(coord * (i + 1))
        
        return values.reshape(grid_shape)
    
    def _generate_quantum_field(self, grid_shape):
        """Generate quantum field fluctuations."""
        total_size = np.prod(grid_shape)
        # Quantum vacuum fluctuations
        real_part = np.random.normal(0, 1, total_size)
        imag_part = np.random.normal(0, 1, total_size)
        values = np.sqrt(real_part**2 + imag_part**2)
        return values.reshape(grid_shape)
    
    def _generate_cosmic_web(self, grid_shape):
        """Generate cosmic web structure."""
        total_size = np.prod(grid_shape)
        indices = np.unravel_index(np.arange(total_size), grid_shape)
        
        # Filamentary structure
        values = np.ones(total_size)
        for i in range(len(grid_shape)):
            coord = indices[i] / grid_shape[i]
            # Create filaments along different dimensions
            values *= 1 + 0.5 * np.sin(coord * np.pi * (i + 2))
        
        return values.reshape(grid_shape)
    
    def _create_visualization_shape(self, grid_size):
        """Create a simple box to represent the field."""
        try:
            # Simple box representation for now
            return BRepPrimAPI_MakeBox(grid_size, grid_size, grid_size).Shape()
        except:
            return None


# Command Classes for GUI Integration

class BizarreCurveCmd(BaseCmd):
    """Command to create bizarre curves with hyperbolic distortions."""
    
    title = "Bizarre Curve"
    
    def run(self, mw):
        if not HAS_DEPENDENCIES:
            mw.win.statusBar().showMessage("Dependencies not available for Bizarre Curve", 3000)
            return
            
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Bizarre Curve Parameters")
                layout = QFormLayout(self)
                
                self.base_radius = QDoubleSpinBox()
                self.base_radius.setRange(0.1, 1000)
                self.base_radius.setValue(20.0)
                
                self.height = QDoubleSpinBox()
                self.height.setRange(0.1, 1000)
                self.height.setValue(50.0)
                
                self.frequency = QDoubleSpinBox()
                self.frequency.setRange(0.1, 10.0)
                self.frequency.setValue(2.0)
                
                self.distortion = QDoubleSpinBox()
                self.distortion.setRange(0.0, 5.0)
                self.distortion.setValue(1.0)
                
                self.segments = QSpinBox()
                self.segments.setRange(20, 500)
                self.segments.setValue(100)
                
                layout.addRow("Base Radius:", self.base_radius)
                layout.addRow("Height:", self.height)
                layout.addRow("Frequency:", self.frequency)
                layout.addRow("Distortion:", self.distortion)
                layout.addRow("Segments:", self.segments)
                
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addRow(buttons)
        
        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
            
        feat = BizarreCurveFeature(
            dlg.base_radius.value(),
            dlg.height.value(),
            dlg.frequency.value(),
            dlg.distortion.value(),
            dlg.segments.value()
        )
        print(f"[BizarreCurveCmd] Feature created: {feat}")
        print(f"[BizarreCurveCmd] Feature shape: {feat.shape}")
        try:
            DOCUMENT.append(feat)
            print("[BizarreCurveCmd] Added feature to DOCUMENT")
            mw.view._display.EraseAll()
            print("[BizarreCurveCmd] Erased all shapes from display")
            mw.view._display.DisplayShape(feat.shape, update=True)
            print("[BizarreCurveCmd] Displayed shape")
            mw.view._display.FitAll()
            print("[BizarreCurveCmd] FitAll called")
            mw.win.statusBar().showMessage("Bizarre Curve created!", 3000)
        except Exception as e:
            print(f"[BizarreCurveCmd] Exception during display: {e}")
            mw.win.statusBar().showMessage(f"Error creating bizarre curve: {e}", 5000)


class CosmicSplineCmd(BaseCmd):
    """Command to create cosmic splines with spacetime curvature."""
    
    title = "Cosmic Spline"
    
    def run(self, mw):
        if not HAS_DEPENDENCIES:
            mw.win.statusBar().showMessage("Dependencies not available for Cosmic Spline", 3000)
            return
            
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("Cosmic Spline Parameters")
                layout = QFormLayout(self)
                
                self.num_points = QSpinBox()
                self.num_points.setRange(3, 20)
                self.num_points.setValue(6)
                
                self.degree = QSpinBox()
                self.degree.setRange(1, 5)
                self.degree.setValue(3)
                
                self.cosmic_curvature = QDoubleSpinBox()
                self.cosmic_curvature.setRange(0.0, 2.0)
                self.cosmic_curvature.setValue(0.5)
                
                self.spread = QDoubleSpinBox()
                self.spread.setRange(1.0, 100.0)
                self.spread.setValue(30.0)
                
                layout.addRow("Control Points:", self.num_points)
                layout.addRow("Curve Degree:", self.degree)
                layout.addRow("Cosmic Curvature:", self.cosmic_curvature)
                layout.addRow("Point Spread:", self.spread)
                
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addRow(buttons)
        
        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
        
        # Generate control points
        num_points = dlg.num_points.value()
        spread = dlg.spread.value()
        control_points = []
        
        for i in range(num_points):
            t = i / (num_points - 1)
            x = spread * (t - 0.5) * math.cos(t * 2 * math.pi)
            y = spread * (t - 0.5) * math.sin(t * 2 * math.pi)
            z = spread * t * math.sin(t * 4 * math.pi)
            control_points.append((x, y, z))
        
        feat = CosmicSplineFeature(
            control_points,
            dlg.degree.value(),
            dlg.cosmic_curvature.value()
        )
        
        try:
            DOCUMENT.append(feat)
            mw.view._display.EraseAll()
            mw.view._display.DisplayShape(feat.shape, update=True)
            mw.view._display.FitAll()
            mw.win.statusBar().showMessage("Cosmic Spline created!", 3000)
        except Exception as e:
            mw.win.statusBar().showMessage(f"Error creating cosmic spline: {e}", 5000)


class NDFieldExplorerCmd(BaseCmd):
    """Command to explore N-dimensional fields."""
    
    title = "ND Field Explorer"
    
    def run(self, mw):
        if not HAS_DEPENDENCIES:
            mw.win.statusBar().showMessage("Dependencies not available for ND Field Explorer", 3000)
            return
            
        class ParamDialog(QDialog):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setWindowTitle("ND Field Explorer Parameters")
                layout = QFormLayout(self)
                
                self.dimensions = QSpinBox()
                self.dimensions.setRange(2, 8)
                self.dimensions.setValue(4)
                
                self.grid_size = QSpinBox()
                self.grid_size.setRange(2, 20)
                self.grid_size.setValue(8)
                
                self.field_type = QComboBox()
                self.field_type.addItems(["scalar_wave", "quantum_field", "cosmic_web", "random"])
                self.field_type.setCurrentText("scalar_wave")
                
                layout.addRow("Dimensions:", self.dimensions)
                layout.addRow("Grid Size:", self.grid_size)
                layout.addRow("Field Type:", self.field_type)
                
                buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
                buttons.accepted.connect(self.accept)
                buttons.rejected.connect(self.reject)
                layout.addRow(buttons)
        
        dlg = ParamDialog(mw.win)
        if not dlg.exec():
            return
            
        feat = NDFieldExplorerFeature(
            dlg.dimensions.value(),
            dlg.grid_size.value(),
            dlg.field_type.currentText()
        )
        
        try:
            DOCUMENT.append(feat)
            mw.view._display.EraseAll()
            mw.view._display.DisplayShape(feat.shape, update=True)
            mw.view._display.FitAll()
            mw.win.statusBar().showMessage(f"ND Field Explorer created: {dlg.dimensions.value()}D field", 3000)
        except Exception as e:
            mw.win.statusBar().showMessage(f"Error creating ND field: {e}", 5000)
