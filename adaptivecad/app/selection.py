"""AdaptiveCAD Selection System

Provides visual selection feedback:
- Object picking via ray casting
- Selection highlighting with outlines
- Multi-selection support
- Keyboard modifiers for selection modes
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np
from PySide6.QtCore import QObject, Qt, Signal

if TYPE_CHECKING:
    from adaptivecad.aacore.scene import Prim, SDFScene

log = logging.getLogger(__name__)


@dataclass
class PickResult:
    """Result of a picking operation."""
    hit: bool = False
    prim_index: int = -1
    distance: float = float('inf')
    hit_point: Optional[np.ndarray] = None
    surface_normal: Optional[np.ndarray] = None


class RayPicker:
    """Performs ray-based object picking using SDF evaluation."""
    
    def __init__(self, scene: Optional['SDFScene'] = None):
        self.scene = scene
        self.max_steps = 64
        self.max_distance = 100.0
        self.hit_threshold = 0.001
    
    def set_scene(self, scene: 'SDFScene'):
        """Set the scene to pick from."""
        self.scene = scene
    
    def pick(self, ray_origin: np.ndarray, ray_dir: np.ndarray) -> PickResult:
        """
        Pick an object using ray marching.
        
        Args:
            ray_origin: Start point of the ray (camera position)
            ray_dir: Normalized direction of the ray
            
        Returns:
            PickResult with hit information
        """
        if not self.scene or not self.scene.prims:
            return PickResult()
        
        # Normalize ray direction
        ray_dir = ray_dir / (np.linalg.norm(ray_dir) + 1e-10)
        
        # March along ray
        t = 0.0
        for step in range(self.max_steps):
            pos = ray_origin + t * ray_dir
            
            # Find closest prim
            min_dist = float('inf')
            closest_prim = -1
            
            for i, prim in enumerate(self.scene.prims):
                # Transform point to local space
                local_pos = self._world_to_local(pos, prim)
                
                # Evaluate SDF
                dist = self._eval_sdf(prim, local_pos)
                
                if dist < min_dist:
                    min_dist = dist
                    closest_prim = i
            
            # Check for hit
            if min_dist < self.hit_threshold:
                # Compute surface normal using gradient
                normal = self._compute_normal(pos, closest_prim)
                
                return PickResult(
                    hit=True,
                    prim_index=closest_prim,
                    distance=t,
                    hit_point=pos.copy(),
                    surface_normal=normal
                )
            
            # March forward
            t += max(min_dist, 0.001)
            
            if t > self.max_distance:
                break
        
        return PickResult()
    
    def _world_to_local(self, pos: np.ndarray, prim: 'Prim') -> np.ndarray:
        """Transform world position to prim's local space."""
        if hasattr(prim, 'xform') and hasattr(prim.xform, 'M'):
            # Inverse transform
            M = prim.xform.M
            # Extract translation
            trans = M[:3, 3]
            # Extract rotation/scale (3x3)
            rot_scale = M[:3, :3]
            
            # Inverse: rotate then translate
            local = pos - trans
            
            # Inverse rotation (transpose for orthogonal)
            det = np.linalg.det(rot_scale)
            if abs(det) > 1e-10:
                inv_rot_scale = np.linalg.inv(rot_scale)
                local = inv_rot_scale @ local
            
            return local
        return pos.copy()
    
    def _eval_sdf(self, prim: 'Prim', local_pos: np.ndarray) -> float:
        """Evaluate the SDF of a primitive at a local position."""
        shape = prim.shape.lower()
        params = prim.params
        
        x, y, z = local_pos
        
        # Basic SDF implementations
        if shape == 'sphere':
            r = params.get('radius', 0.5)
            return np.sqrt(x*x + y*y + z*z) - r
        
        elif shape == 'box':
            sx = params.get('size_x', 0.5)
            sy = params.get('size_y', 0.5)
            sz = params.get('size_z', 0.5)
            q = np.array([abs(x) - sx, abs(y) - sy, abs(z) - sz])
            return np.linalg.norm(np.maximum(q, 0.0)) + min(max(q[0], max(q[1], q[2])), 0.0)
        
        elif shape == 'capsule':
            h = params.get('height', 1.0) / 2
            r = params.get('radius', 0.2)
            # Line segment from (0, -h, 0) to (0, h, 0)
            pa = np.array([x, y + h, z])
            ba = np.array([0, 2*h, 0])
            baba = np.dot(ba, ba)
            paba = np.dot(pa, ba)
            h_clamp = max(0.0, min(1.0, paba / (baba + 1e-10)))
            return np.linalg.norm(pa - h_clamp * ba) - r
        
        elif shape == 'torus':
            R = params.get('major_radius', 0.5)
            r = params.get('minor_radius', 0.2)
            q = np.array([np.sqrt(x*x + z*z) - R, y])
            return np.linalg.norm(q) - r
        
        elif shape == 'cylinder':
            r = params.get('radius', 0.5)
            h = params.get('height', 1.0) / 2
            d = np.array([abs(np.sqrt(x*x + z*z)) - r, abs(y) - h])
            return min(max(d[0], d[1]), 0.0) + np.linalg.norm(np.maximum(d, 0.0))
        
        else:
            # Fallback: treat as sphere with radius 0.5
            return np.sqrt(x*x + y*y + z*z) - 0.5
    
    def _compute_normal(self, pos: np.ndarray, prim_index: int) -> np.ndarray:
        """Compute surface normal using finite differences."""
        eps = 0.001
        
        def scene_sdf(p):
            min_dist = float('inf')
            for i, prim in enumerate(self.scene.prims):
                local_p = self._world_to_local(p, prim)
                dist = self._eval_sdf(prim, local_p)
                min_dist = min(min_dist, dist)
            return min_dist
        
        normal = np.array([
            scene_sdf(pos + np.array([eps, 0, 0])) - scene_sdf(pos - np.array([eps, 0, 0])),
            scene_sdf(pos + np.array([0, eps, 0])) - scene_sdf(pos - np.array([0, eps, 0])),
            scene_sdf(pos + np.array([0, 0, eps])) - scene_sdf(pos - np.array([0, 0, eps])),
        ])
        
        return normal / (np.linalg.norm(normal) + 1e-10)


class SelectionHighlighter:
    """Manages visual highlighting of selected objects."""
    
    def __init__(self):
        self.selection_color = np.array([1.0, 0.6, 0.0], dtype=np.float32)  # Orange
        self.hover_color = np.array([0.4, 0.8, 1.0], dtype=np.float32)  # Light blue
        self.outline_width = 2.0
        self.pulse_speed = 2.0  # Hz
        self._time = 0.0
    
    def update(self, dt: float):
        """Update animation time."""
        self._time += dt
    
    def get_selection_uniform_data(self, prim_index: int, selected_indices: List[int], 
                                    hover_index: int) -> dict:
        """Get shader uniform data for selection highlighting."""
        is_selected = prim_index in selected_indices
        is_hovered = prim_index == hover_index
        
        # Pulsing effect for selection
        pulse = 0.5 + 0.5 * np.sin(self._time * self.pulse_speed * 2 * np.pi)
        
        if is_selected:
            color = self.selection_color
            intensity = 0.8 + 0.2 * pulse
        elif is_hovered:
            color = self.hover_color
            intensity = 0.6
        else:
            color = np.zeros(3)
            intensity = 0.0
        
        return {
            'highlight_color': color * intensity,
            'is_selected': is_selected,
            'is_hovered': is_hovered,
            'outline_width': self.outline_width if (is_selected or is_hovered) else 0.0,
        }


class ObjectPicker(QObject):
    """
    High-level object picking interface.
    
    Handles mouse input and converts to picking operations.
    """
    
    objectPicked = Signal(int, bool, bool)  # index, add_to_selection, toggle
    objectHovered = Signal(int)
    
    def __init__(self, picker: RayPicker):
        super().__init__()
        self.ray_picker = picker
        self._last_hover = -1
    
    def pick_at_screen_pos(
        self, 
        screen_pos: Tuple[int, int],
        camera_pos: np.ndarray,
        view_matrix: np.ndarray,
        proj_matrix: np.ndarray,
        viewport_size: Tuple[int, int],
        modifiers: Qt.KeyboardModifiers = Qt.KeyboardModifier.NoModifier
    ) -> PickResult:
        """
        Pick object at screen position.
        
        Args:
            screen_pos: (x, y) screen coordinates
            camera_pos: Camera world position
            view_matrix: 4x4 view matrix
            proj_matrix: 4x4 projection matrix
            viewport_size: (width, height) of viewport
            modifiers: Keyboard modifiers (Ctrl, Shift)
            
        Returns:
            PickResult
        """
        # Convert screen to normalized device coordinates
        x = (2.0 * screen_pos[0] / viewport_size[0]) - 1.0
        y = 1.0 - (2.0 * screen_pos[1] / viewport_size[1])  # Flip Y
        
        # Create ray in clip space
        clip_near = np.array([x, y, -1.0, 1.0])
        clip_far = np.array([x, y, 1.0, 1.0])
        
        # Inverse projection
        try:
            inv_proj = np.linalg.inv(proj_matrix)
            inv_view = np.linalg.inv(view_matrix)
        except np.linalg.LinAlgError:
            return PickResult()
        
        # Transform to view space
        view_near = inv_proj @ clip_near
        view_far = inv_proj @ clip_far
        
        # Perspective divide
        view_near = view_near[:3] / view_near[3]
        view_far = view_far[:3] / view_far[3]
        
        # Transform to world space
        world_near = (inv_view @ np.append(view_near, 1.0))[:3]
        world_far = (inv_view @ np.append(view_far, 1.0))[:3]
        
        # Ray direction
        ray_dir = world_far - world_near
        ray_dir = ray_dir / (np.linalg.norm(ray_dir) + 1e-10)
        
        # Perform pick
        result = self.ray_picker.pick(world_near, ray_dir)
        
        if result.hit:
            # Check for Ctrl or Shift modifiers
            try:
                ctrl_mod = Qt.KeyboardModifier.ControlModifier
                shift_mod = Qt.KeyboardModifier.ShiftModifier
            except AttributeError:
                ctrl_mod = Qt.ControlModifier
                shift_mod = Qt.ShiftModifier
            
            add_to_selection = bool(modifiers & shift_mod)
            toggle = bool(modifiers & ctrl_mod)
            
            self.objectPicked.emit(result.prim_index, add_to_selection, toggle)
        
        return result
    
    def hover_at_screen_pos(
        self,
        screen_pos: Tuple[int, int],
        camera_pos: np.ndarray,
        view_matrix: np.ndarray,
        proj_matrix: np.ndarray,
        viewport_size: Tuple[int, int]
    ) -> int:
        """Update hover state at screen position."""
        result = self.pick_at_screen_pos(
            screen_pos, camera_pos, view_matrix, proj_matrix, 
            viewport_size, Qt.KeyboardModifier.NoModifier
        )
        
        hover_index = result.prim_index if result.hit else -1
        
        if hover_index != self._last_hover:
            self._last_hover = hover_index
            self.objectHovered.emit(hover_index)
        
        return hover_index


def compute_bounding_box(prim: 'Prim') -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute the axis-aligned bounding box of a primitive.
    
    Returns:
        Tuple of (min_point, max_point)
    """
    shape = prim.shape.lower()
    params = prim.params
    
    # Get local bounds
    if shape == 'sphere':
        r = params.get('radius', 0.5)
        local_min = np.array([-r, -r, -r])
        local_max = np.array([r, r, r])
    
    elif shape == 'box':
        sx = params.get('size_x', 0.5)
        sy = params.get('size_y', 0.5)
        sz = params.get('size_z', 0.5)
        local_min = np.array([-sx, -sy, -sz])
        local_max = np.array([sx, sy, sz])
    
    elif shape == 'capsule':
        h = params.get('height', 1.0) / 2
        r = params.get('radius', 0.2)
        local_min = np.array([-r, -h - r, -r])
        local_max = np.array([r, h + r, r])
    
    elif shape == 'torus':
        R = params.get('major_radius', 0.5)
        r = params.get('minor_radius', 0.2)
        extent = R + r
        local_min = np.array([-extent, -r, -extent])
        local_max = np.array([extent, r, extent])
    
    elif shape == 'cylinder':
        r = params.get('radius', 0.5)
        h = params.get('height', 1.0) / 2
        local_min = np.array([-r, -h, -r])
        local_max = np.array([r, h, r])
    
    else:
        # Default bounds
        local_min = np.array([-1, -1, -1])
        local_max = np.array([1, 1, 1])
    
    # Transform to world space
    if hasattr(prim, 'xform') and hasattr(prim.xform, 'M'):
        M = prim.xform.M
        
        # Transform all 8 corners
        corners = []
        for i in range(8):
            corner = np.array([
                local_min[0] if i & 1 else local_max[0],
                local_min[1] if i & 2 else local_max[1],
                local_min[2] if i & 4 else local_max[2],
            ])
            world_corner = (M[:3, :3] @ corner) + M[:3, 3]
            corners.append(world_corner)
        
        corners = np.array(corners)
        world_min = np.min(corners, axis=0)
        world_max = np.max(corners, axis=0)
        
        return world_min, world_max
    
    return local_min, local_max


def compute_selection_center(scene: 'SDFScene', indices: List[int]) -> np.ndarray:
    """Compute the center of a selection."""
    if not scene or not indices:
        return np.zeros(3, dtype=np.float32)
    
    centers = []
    for idx in indices:
        if 0 <= idx < len(scene.prims):
            prim = scene.prims[idx]
            center = prim.xform.M[:3, 3] if hasattr(prim.xform, 'M') else np.zeros(3)
            centers.append(center)
    
    if centers:
        return np.mean(centers, axis=0).astype(np.float32)
    
    return np.zeros(3, dtype=np.float32)
