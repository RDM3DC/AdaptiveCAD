"""Camera Control and View Presets

Provides standard camera views and navigation helpers for the 3D viewport.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np


class CameraPresets:
    """Standard camera view presets for 3D modeling."""
    
    @staticmethod
    def front() -> Tuple[np.ndarray, np.ndarray]:
        """Front view (looking along -Z axis).
        
        Returns:
            (position, rotation_matrix)
        """
        pos = np.array([0.0, 0.0, 5.0], dtype=np.float32)
        # Identity rotation (camera looks along -Z by default)
        rot = np.eye(3, dtype=np.float32)
        return pos, rot
    
    @staticmethod
    def back() -> Tuple[np.ndarray, np.ndarray]:
        """Back view (looking along +Z axis)."""
        pos = np.array([0.0, 0.0, -5.0], dtype=np.float32)
        # Rotate 180° around Y
        rot = np.array([
            [-1, 0, 0],
            [0, 1, 0],
            [0, 0, -1]
        ], dtype=np.float32)
        return pos, rot
    
    @staticmethod
    def right() -> Tuple[np.ndarray, np.ndarray]:
        """Right view (looking along -X axis)."""
        pos = np.array([5.0, 0.0, 0.0], dtype=np.float32)
        # Rotate 90° around Y
        rot = np.array([
            [0, 0, 1],
            [0, 1, 0],
            [-1, 0, 0]
        ], dtype=np.float32)
        return pos, rot
    
    @staticmethod
    def left() -> Tuple[np.ndarray, np.ndarray]:
        """Left view (looking along +X axis)."""
        pos = np.array([-5.0, 0.0, 0.0], dtype=np.float32)
        # Rotate -90° around Y
        rot = np.array([
            [0, 0, -1],
            [0, 1, 0],
            [1, 0, 0]
        ], dtype=np.float32)
        return pos, rot
    
    @staticmethod
    def top() -> Tuple[np.ndarray, np.ndarray]:
        """Top view (looking along -Y axis)."""
        pos = np.array([0.0, 5.0, 0.0], dtype=np.float32)
        # Rotate -90° around X
        rot = np.array([
            [1, 0, 0],
            [0, 0, 1],
            [0, -1, 0]
        ], dtype=np.float32)
        return pos, rot
    
    @staticmethod
    def bottom() -> Tuple[np.ndarray, np.ndarray]:
        """Bottom view (looking along +Y axis)."""
        pos = np.array([0.0, -5.0, 0.0], dtype=np.float32)
        # Rotate 90° around X
        rot = np.array([
            [1, 0, 0],
            [0, 0, -1],
            [0, 1, 0]
        ], dtype=np.float32)
        return pos, rot
    
    @staticmethod
    def isometric() -> Tuple[np.ndarray, np.ndarray]:
        """Isometric view (classic 3/4 view)."""
        # Position camera at (1, 1, 1) direction, distance 5
        direction = np.array([1.0, 1.0, 1.0])
        direction = direction / np.linalg.norm(direction)
        pos = -direction * 5.0
        
        # Look at origin
        rot = look_at_matrix(pos, np.zeros(3), np.array([0, 1, 0]))
        return pos.astype(np.float32), rot.astype(np.float32)


def look_at_matrix(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    """Create a look-at rotation matrix.
    
    Args:
        eye: Camera position
        target: Point to look at
        up: Up vector
        
    Returns:
        3x3 rotation matrix
    """
    # Forward (from eye to target, inverted because camera looks along -Z)
    forward = target - eye
    forward = forward / (np.linalg.norm(forward) + 1e-9)
    
    # Right
    right = np.cross(forward, up)
    right = right / (np.linalg.norm(right) + 1e-9)
    
    # Up (recompute to ensure orthogonality)
    up_new = np.cross(right, forward)
    up_new = up_new / (np.linalg.norm(up_new) + 1e-9)
    
    # Build rotation matrix (transpose of view matrix's rotation part)
    # Camera space: right=X, up=Y, -forward=Z
    rot = np.column_stack([right, up_new, -forward])
    
    return rot.T  # Transpose for camera orientation


def frame_bounds(min_pt: np.ndarray, max_pt: np.ndarray, 
                 current_rot: np.ndarray, fov: float = 45.0) -> Tuple[np.ndarray, float]:
    """Calculate camera position to frame a bounding box.
    
    Args:
        min_pt: Minimum corner of bounds
        max_pt: Maximum corner of bounds
        current_rot: Current camera rotation matrix
        fov: Field of view in degrees
        
    Returns:
        (new_position, distance)
    """
    # Calculate center and size
    center = (min_pt + max_pt) / 2.0
    size = np.linalg.norm(max_pt - min_pt)
    
    # Calculate required distance based on FOV
    fov_rad = np.deg2rad(fov)
    distance = (size / 2.0) / np.tan(fov_rad / 2.0) * 1.2  # 1.2 for padding
    
    # Move camera along its current forward direction
    forward = current_rot[2, :]  # Z axis of camera (forward is -Z in view space)
    new_pos = center - forward * distance
    
    return new_pos.astype(np.float32), float(distance)


def calculate_orbit_position(center: np.ndarray, distance: float, 
                            azimuth: float, elevation: float) -> Tuple[np.ndarray, np.ndarray]:
    """Calculate camera position for orbit around a point.
    
    Args:
        center: Point to orbit around
        distance: Distance from center
        azimuth: Horizontal angle in degrees (0 = looking from +X)
        elevation: Vertical angle in degrees (0 = equator, 90 = top)
        
    Returns:
        (position, rotation_matrix)
    """
    az_rad = np.deg2rad(azimuth)
    el_rad = np.deg2rad(elevation)
    
    # Spherical to Cartesian
    x = distance * np.cos(el_rad) * np.cos(az_rad)
    y = distance * np.sin(el_rad)
    z = distance * np.cos(el_rad) * np.sin(az_rad)
    
    pos = center + np.array([x, y, z], dtype=np.float32)
    
    # Look at center
    rot = look_at_matrix(pos, center, np.array([0, 1, 0]))
    
    return pos, rot
