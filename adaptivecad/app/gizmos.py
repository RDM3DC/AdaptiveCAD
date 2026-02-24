"""AdaptiveCAD Transform Gizmos

Provides visual 3D transform handles for interactive object manipulation:
- Move gizmo with axis arrows
- Rotate gizmo with rotation rings
- Scale gizmo with axis cubes
- Selection highlighting
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

import numpy as np
from PySide6.QtCore import QObject, Signal

log = logging.getLogger(__name__)


class GizmoMode(Enum):
    """Active gizmo mode."""
    NONE = "none"
    MOVE = "move"
    ROTATE = "rotate"
    SCALE = "scale"


class GizmoAxis(Enum):
    """Gizmo axis being manipulated."""
    NONE = "none"
    X = "x"
    Y = "y"
    Z = "z"
    XY = "xy"
    XZ = "xz"
    YZ = "yz"
    ALL = "all"  # For uniform scale
    VIEW = "view"  # Screen-space


@dataclass
class GizmoColors:
    """Colors for gizmo rendering."""
    x_axis: Tuple[float, float, float] = (0.9, 0.2, 0.2)  # Red
    y_axis: Tuple[float, float, float] = (0.2, 0.9, 0.2)  # Green
    z_axis: Tuple[float, float, float] = (0.2, 0.2, 0.9)  # Blue
    xy_plane: Tuple[float, float, float] = (0.9, 0.9, 0.2)  # Yellow
    xz_plane: Tuple[float, float, float] = (0.9, 0.2, 0.9)  # Magenta
    yz_plane: Tuple[float, float, float] = (0.2, 0.9, 0.9)  # Cyan
    all_axis: Tuple[float, float, float] = (0.9, 0.9, 0.9)  # White
    highlight: Tuple[float, float, float] = (1.0, 1.0, 0.3)  # Bright yellow
    selection: Tuple[float, float, float] = (1.0, 0.6, 0.0)  # Orange


class GizmoState:
    """Tracks the current state of gizmo interaction."""
    
    def __init__(self):
        self.mode = GizmoMode.NONE
        self.active_axis = GizmoAxis.NONE
        self.hovered_axis = GizmoAxis.NONE
        self.is_dragging = False
        self.drag_start_pos: Optional[np.ndarray] = None
        self.drag_start_value: Optional[np.ndarray] = None
        self.position = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        self.rotation = np.array([0.0, 0.0, 0.0], dtype=np.float32)  # Euler degrees
        self.scale = np.array([1.0, 1.0, 1.0], dtype=np.float32)
        self.size = 0.5  # Gizmo size in world units


class SelectionManager(QObject):
    """Manages object selection in the scene."""
    
    selectionChanged = Signal(list)  # List of selected indices
    
    def __init__(self, scene=None):
        super().__init__()
        self.scene = scene
        self._selected_indices: list = []
        self._hover_index: int = -1
    
    def set_scene(self, scene):
        """Set the scene to manage."""
        self.scene = scene
    
    @property
    def selected_indices(self) -> list:
        return self._selected_indices.copy()
    
    @property
    def has_selection(self) -> bool:
        return len(self._selected_indices) > 0
    
    @property
    def primary_selection(self) -> int:
        """Return the primary (first) selected index, or -1 if none."""
        return self._selected_indices[0] if self._selected_indices else -1
    
    def select(self, index: int, add_to_selection: bool = False):
        """Select an object by index."""
        if not self.scene:
            return
        
        if index < 0 or index >= len(self.scene.prims):
            if not add_to_selection:
                self.clear_selection()
            return
        
        if add_to_selection:
            if index not in self._selected_indices:
                self._selected_indices.append(index)
        else:
            self._selected_indices = [index]
        
        self.selectionChanged.emit(self._selected_indices)
    
    def deselect(self, index: int):
        """Deselect an object by index."""
        if index in self._selected_indices:
            self._selected_indices.remove(index)
            self.selectionChanged.emit(self._selected_indices)
    
    def toggle_selection(self, index: int):
        """Toggle selection of an object."""
        if index in self._selected_indices:
            self.deselect(index)
        else:
            self.select(index, add_to_selection=True)
    
    def clear_selection(self):
        """Clear all selections."""
        if self._selected_indices:
            self._selected_indices = []
            self.selectionChanged.emit(self._selected_indices)
    
    def select_all(self):
        """Select all objects."""
        if self.scene:
            self._selected_indices = list(range(len(self.scene.prims)))
            self.selectionChanged.emit(self._selected_indices)
    
    def set_hover(self, index: int):
        """Set the hovered object index."""
        self._hover_index = index
    
    @property
    def hover_index(self) -> int:
        return self._hover_index
    
    def get_selection_center(self) -> np.ndarray:
        """Get the center point of the current selection."""
        if not self.scene or not self._selected_indices:
            return np.array([0.0, 0.0, 0.0], dtype=np.float32)
        
        centers = []
        for idx in self._selected_indices:
            if 0 <= idx < len(self.scene.prims):
                prim = self.scene.prims[idx]
                center = prim.xform.M[:3, 3]
                centers.append(center)
        
        if centers:
            return np.mean(centers, axis=0).astype(np.float32)
        return np.array([0.0, 0.0, 0.0], dtype=np.float32)


class GizmoRenderer:
    """Renders transform gizmos using OpenGL."""
    
    def __init__(self):
        self.state = GizmoState()
        self.colors = GizmoColors()
        self._arrow_verts = None
        self._ring_verts = None
        self._cube_verts = None
        self._initialized = False
    
    def initialize(self):
        """Initialize gizmo geometry."""
        if self._initialized:
            return
        
        # Generate arrow geometry for move gizmo
        self._arrow_verts = self._generate_arrow()
        
        # Generate ring geometry for rotate gizmo
        self._ring_verts = self._generate_ring()
        
        # Generate cube geometry for scale gizmo
        self._cube_verts = self._generate_cube()
        
        self._initialized = True
    
    def _generate_arrow(self, length: float = 1.0, radius: float = 0.02) -> np.ndarray:
        """Generate arrow geometry (shaft + cone)."""
        segments = 12
        verts = []
        
        # Shaft (cylinder along Z)
        shaft_length = length * 0.75
        for i in range(segments):
            angle1 = 2 * math.pi * i / segments
            angle2 = 2 * math.pi * (i + 1) / segments
            
            x1, y1 = radius * math.cos(angle1), radius * math.sin(angle1)
            x2, y2 = radius * math.cos(angle2), radius * math.sin(angle2)
            
            # Quad as two triangles
            verts.extend([
                [x1, y1, 0], [x2, y2, 0], [x1, y1, shaft_length],
                [x2, y2, 0], [x2, y2, shaft_length], [x1, y1, shaft_length],
            ])
        
        # Cone head
        cone_base_radius = radius * 3
        cone_start = shaft_length
        cone_end = length
        
        for i in range(segments):
            angle1 = 2 * math.pi * i / segments
            angle2 = 2 * math.pi * (i + 1) / segments
            
            x1 = cone_base_radius * math.cos(angle1)
            y1 = cone_base_radius * math.sin(angle1)
            x2 = cone_base_radius * math.cos(angle2)
            y2 = cone_base_radius * math.sin(angle2)
            
            # Triangle to tip
            verts.extend([
                [x1, y1, cone_start],
                [x2, y2, cone_start],
                [0, 0, cone_end],
            ])
            
            # Base cap
            verts.extend([
                [0, 0, cone_start],
                [x2, y2, cone_start],
                [x1, y1, cone_start],
            ])
        
        return np.array(verts, dtype=np.float32)
    
    def _generate_ring(self, radius: float = 1.0, tube_radius: float = 0.02) -> np.ndarray:
        """Generate torus ring geometry."""
        ring_segments = 48
        tube_segments = 8
        verts = []
        
        for i in range(ring_segments):
            theta1 = 2 * math.pi * i / ring_segments
            theta2 = 2 * math.pi * (i + 1) / ring_segments
            
            for j in range(tube_segments):
                phi1 = 2 * math.pi * j / tube_segments
                phi2 = 2 * math.pi * (j + 1) / tube_segments
                
                # Four corners of quad
                def torus_point(theta, phi):
                    r = radius + tube_radius * math.cos(phi)
                    x = r * math.cos(theta)
                    y = r * math.sin(theta)
                    z = tube_radius * math.sin(phi)
                    return [x, y, z]
                
                p1 = torus_point(theta1, phi1)
                p2 = torus_point(theta2, phi1)
                p3 = torus_point(theta2, phi2)
                p4 = torus_point(theta1, phi2)
                
                # Two triangles
                verts.extend([p1, p2, p3, p1, p3, p4])
        
        return np.array(verts, dtype=np.float32)
    
    def _generate_cube(self, size: float = 0.1) -> np.ndarray:
        """Generate cube geometry for scale handles."""
        s = size / 2
        verts = []
        
        # Six faces
        faces = [
            # Front
            [[-s, -s, s], [s, -s, s], [s, s, s], [-s, -s, s], [s, s, s], [-s, s, s]],
            # Back
            [[s, -s, -s], [-s, -s, -s], [-s, s, -s], [s, -s, -s], [-s, s, -s], [s, s, -s]],
            # Top
            [[-s, s, -s], [-s, s, s], [s, s, s], [-s, s, -s], [s, s, s], [s, s, -s]],
            # Bottom
            [[-s, -s, s], [-s, -s, -s], [s, -s, -s], [-s, -s, s], [s, -s, -s], [s, -s, s]],
            # Right
            [[s, -s, s], [s, -s, -s], [s, s, -s], [s, -s, s], [s, s, -s], [s, s, s]],
            # Left
            [[-s, -s, -s], [-s, -s, s], [-s, s, s], [-s, -s, -s], [-s, s, s], [-s, s, -s]],
        ]
        
        for face in faces:
            verts.extend(face)
        
        return np.array(verts, dtype=np.float32)
    
    def get_shader_data(self) -> dict:
        """Get gizmo data for shader rendering."""
        return {
            'mode': self.state.mode.value,
            'position': self.state.position,
            'rotation': self.state.rotation,
            'scale': self.state.scale,
            'size': self.state.size,
            'active_axis': self.state.active_axis.value,
            'hovered_axis': self.state.hovered_axis.value,
            'colors': {
                'x': self.colors.x_axis,
                'y': self.colors.y_axis,
                'z': self.colors.z_axis,
                'highlight': self.colors.highlight,
            }
        }


class GizmoController(QObject):
    """Controls gizmo interaction and updates scene objects."""
    
    transformStarted = Signal()
    transformUpdated = Signal(dict)  # transform dict
    transformEnded = Signal()
    
    def __init__(self, selection_manager: SelectionManager, scene=None):
        super().__init__()
        self.selection = selection_manager
        self.scene = scene
        self.renderer = GizmoRenderer()
        self.state = self.renderer.state
        
        self._snap_translate = 0.0  # 0 = no snapping
        self._snap_rotate = 0.0  # degrees, 0 = no snapping
        self._snap_scale = 0.0  # 0 = no snapping
    
    def set_scene(self, scene):
        """Set the scene."""
        self.scene = scene
        self.selection.set_scene(scene)
    
    def set_mode(self, mode: GizmoMode):
        """Set the active gizmo mode."""
        self.state.mode = mode
        self._update_gizmo_position()
    
    def set_snap(self, translate: float = 0.0, rotate: float = 0.0, scale: float = 0.0):
        """Set snapping values."""
        self._snap_translate = translate
        self._snap_rotate = rotate
        self._snap_scale = scale
    
    def _update_gizmo_position(self):
        """Update gizmo position to match selection."""
        if self.selection.has_selection:
            self.state.position = self.selection.get_selection_center()
            
            # Get rotation/scale from primary selection
            idx = self.selection.primary_selection
            if self.scene and 0 <= idx < len(self.scene.prims):
                prim = self.scene.prims[idx]
                if hasattr(prim, 'euler'):
                    self.state.rotation = prim.euler.copy()
                if hasattr(prim, 'scale'):
                    self.state.scale = prim.scale.copy()
    
    def hit_test(self, ray_origin: np.ndarray, ray_dir: np.ndarray) -> GizmoAxis:
        """Test if a ray hits any gizmo axis."""
        if self.state.mode == GizmoMode.NONE or not self.selection.has_selection:
            return GizmoAxis.NONE
        
        pos = self.state.position
        size = self.state.size
        
        # Simplified hit testing - check distance to each axis line
        hit_threshold = 0.08 * size
        
        # Test X axis (red)
        x_hit = self._ray_line_distance(ray_origin, ray_dir, pos, pos + np.array([size, 0, 0]))
        
        # Test Y axis (green)  
        y_hit = self._ray_line_distance(ray_origin, ray_dir, pos, pos + np.array([0, size, 0]))
        
        # Test Z axis (blue)
        z_hit = self._ray_line_distance(ray_origin, ray_dir, pos, pos + np.array([0, 0, size]))
        
        # Find closest hit
        hits = [
            (x_hit, GizmoAxis.X),
            (y_hit, GizmoAxis.Y),
            (z_hit, GizmoAxis.Z),
        ]
        
        hits.sort(key=lambda x: x[0])
        
        if hits[0][0] < hit_threshold:
            return hits[0][1]
        
        return GizmoAxis.NONE
    
    def _ray_line_distance(
        self, 
        ray_origin: np.ndarray, 
        ray_dir: np.ndarray,
        line_start: np.ndarray,
        line_end: np.ndarray
    ) -> float:
        """Calculate minimum distance between a ray and a line segment."""
        # Vector from ray origin to line start
        w0 = ray_origin - line_start
        
        # Line direction
        u = ray_dir
        v = line_end - line_start
        
        a = np.dot(u, u)
        b = np.dot(u, v)
        c = np.dot(v, v)
        d = np.dot(u, w0)
        e = np.dot(v, w0)
        
        denom = a * c - b * b
        
        if abs(denom) < 1e-10:
            # Parallel
            return np.linalg.norm(w0 - (np.dot(w0, v) / (c + 1e-10)) * v)
        
        s = (b * e - c * d) / denom
        t = (a * e - b * d) / denom
        
        # Clamp t to [0, 1] for line segment
        t = max(0, min(1, t))
        
        # Closest points
        p_ray = ray_origin + s * ray_dir
        p_line = line_start + t * v
        
        return np.linalg.norm(p_ray - p_line)
    
    def begin_drag(self, axis: GizmoAxis, mouse_pos: Tuple[int, int], viewport_size: Tuple[int, int]):
        """Begin a drag operation."""
        if axis == GizmoAxis.NONE:
            return
        
        self.state.active_axis = axis
        self.state.is_dragging = True
        self.state.drag_start_pos = np.array(mouse_pos, dtype=np.float32)
        
        # Store starting values
        if self.state.mode == GizmoMode.MOVE:
            self.state.drag_start_value = self.state.position.copy()
        elif self.state.mode == GizmoMode.ROTATE:
            self.state.drag_start_value = self.state.rotation.copy()
        elif self.state.mode == GizmoMode.SCALE:
            self.state.drag_start_value = self.state.scale.copy()
        
        self.transformStarted.emit()
    
    def update_drag(self, mouse_pos: Tuple[int, int], viewport_size: Tuple[int, int]):
        """Update the drag operation."""
        if not self.state.is_dragging:
            return
        
        current_pos = np.array(mouse_pos, dtype=np.float32)
        delta = current_pos - self.state.drag_start_pos
        
        # Scale delta by viewport size for consistent behavior
        delta_normalized = delta / np.array(viewport_size, dtype=np.float32)
        
        transform = {}
        
        if self.state.mode == GizmoMode.MOVE:
            transform = self._compute_move_delta(delta_normalized)
        elif self.state.mode == GizmoMode.ROTATE:
            transform = self._compute_rotate_delta(delta_normalized)
        elif self.state.mode == GizmoMode.SCALE:
            transform = self._compute_scale_delta(delta_normalized)
        
        # Apply to selected objects
        self._apply_transform(transform)
        
        self.transformUpdated.emit(transform)
    
    def end_drag(self):
        """End the drag operation."""
        if self.state.is_dragging:
            self.state.is_dragging = False
            self.state.active_axis = GizmoAxis.NONE
            self.state.drag_start_pos = None
            self.state.drag_start_value = None
            self.transformEnded.emit()
    
    def _compute_move_delta(self, delta: np.ndarray) -> dict:
        """Compute translation from mouse delta."""
        sensitivity = 5.0
        axis = self.state.active_axis
        
        move = np.array([0.0, 0.0, 0.0], dtype=np.float32)
        
        if axis == GizmoAxis.X:
            move[0] = delta[0] * sensitivity
        elif axis == GizmoAxis.Y:
            move[1] = -delta[1] * sensitivity  # Invert Y
        elif axis == GizmoAxis.Z:
            move[2] = delta[0] * sensitivity
        elif axis == GizmoAxis.XY:
            move[0] = delta[0] * sensitivity
            move[1] = -delta[1] * sensitivity
        elif axis == GizmoAxis.XZ:
            move[0] = delta[0] * sensitivity
            move[2] = -delta[1] * sensitivity
        elif axis == GizmoAxis.YZ:
            move[1] = delta[0] * sensitivity
            move[2] = -delta[1] * sensitivity
        
        # Apply snapping
        if self._snap_translate > 0:
            move = np.round(move / self._snap_translate) * self._snap_translate
        
        new_pos = self.state.drag_start_value + move
        
        return {'position': new_pos.tolist()}
    
    def _compute_rotate_delta(self, delta: np.ndarray) -> dict:
        """Compute rotation from mouse delta."""
        sensitivity = 180.0  # degrees
        axis = self.state.active_axis
        
        rot = self.state.drag_start_value.copy()
        
        if axis == GizmoAxis.X:
            rot[0] += delta[1] * sensitivity
        elif axis == GizmoAxis.Y:
            rot[1] += delta[0] * sensitivity
        elif axis == GizmoAxis.Z:
            rot[2] += delta[0] * sensitivity
        
        # Apply snapping
        if self._snap_rotate > 0:
            rot = np.round(rot / self._snap_rotate) * self._snap_rotate
        
        return {'rotation': rot.tolist()}
    
    def _compute_scale_delta(self, delta: np.ndarray) -> dict:
        """Compute scale from mouse delta."""
        sensitivity = 2.0
        axis = self.state.active_axis
        
        scale = self.state.drag_start_value.copy()
        scale_delta = (delta[0] - delta[1]) * sensitivity
        
        if axis == GizmoAxis.X:
            scale[0] = max(0.01, scale[0] + scale_delta)
        elif axis == GizmoAxis.Y:
            scale[1] = max(0.01, scale[1] + scale_delta)
        elif axis == GizmoAxis.Z:
            scale[2] = max(0.01, scale[2] + scale_delta)
        elif axis == GizmoAxis.ALL:
            factor = max(0.01, 1.0 + scale_delta)
            scale = self.state.drag_start_value * factor
        
        # Apply snapping
        if self._snap_scale > 0:
            scale = np.round(scale / self._snap_scale) * self._snap_scale
            scale = np.maximum(scale, 0.01)
        
        return {'scale': scale.tolist()}
    
    def _apply_transform(self, transform: dict):
        """Apply transform to selected objects."""
        if not self.scene:
            return
        
        for idx in self.selection.selected_indices:
            if 0 <= idx < len(self.scene.prims):
                prim = self.scene.prims[idx]
                
                if 'position' in transform:
                    pos = np.array(transform['position'], dtype=np.float32)
                    prim.xform.M[:3, 3] = pos
                    self.state.position = pos
                
                if 'rotation' in transform and hasattr(prim, 'set_transform'):
                    rot = np.array(transform['rotation'], dtype=np.float32)
                    self.state.rotation = rot
                    prim.set_transform(
                        pos=prim.xform.M[:3, 3],
                        euler=rot,
                        scale=prim.scale if hasattr(prim, 'scale') else np.ones(3)
                    )
                
                if 'scale' in transform and hasattr(prim, 'set_transform'):
                    scale = np.array(transform['scale'], dtype=np.float32)
                    self.state.scale = scale
                    prim.set_transform(
                        pos=prim.xform.M[:3, 3],
                        euler=prim.euler if hasattr(prim, 'euler') else np.zeros(3),
                        scale=scale
                    )
        
        # Notify scene of changes
        if hasattr(self.scene, '_notify'):
            self.scene._notify()
    
    def set_hover(self, axis: GizmoAxis):
        """Set the hovered axis for highlighting."""
        self.state.hovered_axis = axis


# Selection outline shader code (GLSL)
SELECTION_OUTLINE_VERT = """
#version 330 core
layout(location = 0) in vec3 position;
uniform mat4 mvp;
uniform float outline_scale;

void main() {
    vec3 scaled_pos = position * outline_scale;
    gl_Position = mvp * vec4(scaled_pos, 1.0);
}
"""

SELECTION_OUTLINE_FRAG = """
#version 330 core
out vec4 fragColor;
uniform vec3 outline_color;

void main() {
    fragColor = vec4(outline_color, 1.0);
}
"""

# Gizmo shader code (GLSL)
GIZMO_VERT = """
#version 330 core
layout(location = 0) in vec3 position;
uniform mat4 mvp;
uniform mat4 model;

void main() {
    gl_Position = mvp * model * vec4(position, 1.0);
}
"""

GIZMO_FRAG = """
#version 330 core
out vec4 fragColor;
uniform vec3 axis_color;
uniform bool is_highlighted;

void main() {
    vec3 color = axis_color;
    if (is_highlighted) {
        color = mix(color, vec3(1.0, 1.0, 0.3), 0.5);
    }
    fragColor = vec4(color, 1.0);
}
"""
