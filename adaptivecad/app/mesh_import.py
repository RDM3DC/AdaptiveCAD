"""Mesh Import and Conversion to SDF

Imports STL, OBJ, and other mesh formats and converts them to SDF primitives.
Uses spatial acceleration for fast distance queries.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


@dataclass
class Triangle:
    """A triangle with vertices and normal."""
    v0: np.ndarray
    v1: np.ndarray
    v2: np.ndarray
    normal: np.ndarray


class MeshSDFConverter:
    """Converts triangle meshes to signed distance fields."""
    
    def __init__(self, vertices: np.ndarray, faces: np.ndarray):
        """Initialize with mesh data.
        
        Args:
            vertices: (N, 3) array of vertex positions
            faces: (M, 3) array of triangle indices
        """
        self.vertices = vertices.astype(np.float64)
        self.faces = faces.astype(np.int32)
        self.triangles: List[Triangle] = []
        self.bounds_min: np.ndarray = np.zeros(3)
        self.bounds_max: np.ndarray = np.zeros(3)
        
        self._build_triangles()
        self._compute_bounds()
    
    def _build_triangles(self):
        """Build triangle list with normals."""
        for face in self.faces:
            v0 = self.vertices[face[0]]
            v1 = self.vertices[face[1]]
            v2 = self.vertices[face[2]]
            
            # Compute normal
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            norm = np.linalg.norm(normal)
            if norm > 1e-9:
                normal = normal / norm
            else:
                normal = np.array([0, 0, 1])
            
            self.triangles.append(Triangle(v0, v1, v2, normal))
    
    def _compute_bounds(self):
        """Compute axis-aligned bounding box."""
        self.bounds_min = np.min(self.vertices, axis=0)
        self.bounds_max = np.max(self.vertices, axis=0)
    
    def point_to_triangle_distance(self, p: np.ndarray, tri: Triangle) -> float:
        """Compute unsigned distance from point to triangle."""
        v0, v1, v2 = tri.v0, tri.v1, tri.v2
        
        # Vectors
        edge0 = v1 - v0
        edge1 = v2 - v1
        edge2 = v0 - v2
        v0p = p - v0
        v1p = p - v1
        v2p = p - v2
        
        # Check if point projects inside triangle
        normal = tri.normal
        
        # Test if point is inside by checking edge normals
        c0 = np.cross(edge0, v0p)
        c1 = np.cross(edge1, v1p)
        c2 = np.cross(edge2, v2p)
        
        inside = (np.dot(c0, normal) >= 0 and 
                 np.dot(c1, normal) >= 0 and 
                 np.dot(c2, normal) >= 0)
        
        if inside:
            # Distance to plane
            return abs(np.dot(v0p, normal))
        
        # Find closest point on edges
        def point_segment_distance(p, a, b):
            ab = b - a
            ap = p - a
            t = np.clip(np.dot(ap, ab) / (np.dot(ab, ab) + 1e-12), 0, 1)
            closest = a + t * ab
            return np.linalg.norm(p - closest)
        
        d0 = point_segment_distance(p, v0, v1)
        d1 = point_segment_distance(p, v1, v2)
        d2 = point_segment_distance(p, v2, v0)
        
        return min(d0, d1, d2)
    
    def unsigned_distance(self, p: np.ndarray) -> float:
        """Compute unsigned distance to mesh surface."""
        min_dist = float('inf')
        
        for tri in self.triangles:
            dist = self.point_to_triangle_distance(p, tri)
            min_dist = min(min_dist, dist)
        
        return min_dist
    
    def signed_distance(self, p: np.ndarray, ray_count: int = 6) -> float:
        """Compute signed distance using ray casting for inside/outside test.
        
        Args:
            p: Query point
            ray_count: Number of random rays to cast for robustness
        
        Returns:
            Signed distance (negative inside, positive outside)
        """
        # Get unsigned distance
        unsigned_dist = self.unsigned_distance(p)
        
        # Determine sign using ray casting
        # Cast multiple rays and use majority vote
        inside_votes = 0
        
        for i in range(ray_count):
            # Random ray direction
            if i == 0:
                ray_dir = np.array([1, 0, 0])
            elif i == 1:
                ray_dir = np.array([0, 1, 0])
            elif i == 2:
                ray_dir = np.array([0, 0, 1])
            else:
                # Random direction
                theta = np.random.uniform(0, 2 * np.pi)
                phi = np.random.uniform(0, np.pi)
                ray_dir = np.array([
                    np.sin(phi) * np.cos(theta),
                    np.sin(phi) * np.sin(theta),
                    np.cos(phi)
                ])
            
            # Count intersections
            intersections = 0
            for tri in self.triangles:
                if self._ray_triangle_intersect(p, ray_dir, tri):
                    intersections += 1
            
            # Odd number of intersections = inside
            if intersections % 2 == 1:
                inside_votes += 1
        
        # Majority vote
        is_inside = inside_votes > ray_count // 2
        
        return -unsigned_dist if is_inside else unsigned_dist
    
    def _ray_triangle_intersect(self, origin: np.ndarray, direction: np.ndarray, 
                               tri: Triangle) -> bool:
        """Test if ray intersects triangle (Möller-Trumbore algorithm)."""
        epsilon = 1e-9
        
        edge1 = tri.v1 - tri.v0
        edge2 = tri.v2 - tri.v0
        h = np.cross(direction, edge2)
        a = np.dot(edge1, h)
        
        if abs(a) < epsilon:
            return False
        
        f = 1.0 / a
        s = origin - tri.v0
        u = f * np.dot(s, h)
        
        if u < 0.0 or u > 1.0:
            return False
        
        q = np.cross(s, edge1)
        v = f * np.dot(direction, q)
        
        if v < 0.0 or u + v > 1.0:
            return False
        
        t = f * np.dot(edge2, q)
        
        return t > epsilon


def load_stl(filepath: Path) -> Tuple[np.ndarray, np.ndarray]:
    """Load STL file (ASCII or binary).
    
    Returns:
        (vertices, faces) tuple
    """
    try:
        
        with open(filepath, 'rb') as f:
            # Check if binary
            header = f.read(80)
            is_ascii = header.startswith(b'solid') and b'\n' in header
            
            if is_ascii:
                return _load_stl_ascii(filepath)
            else:
                return _load_stl_binary(filepath)
    
    except Exception as e:
        log.error(f"Failed to load STL: {e}")
        raise


def _load_stl_binary(filepath: Path) -> Tuple[np.ndarray, np.ndarray]:
    """Load binary STL file."""
    import struct
    
    with open(filepath, 'rb') as f:
        # Skip header
        f.read(80)
        
        # Read number of triangles
        num_triangles = struct.unpack('<I', f.read(4))[0]
        
        vertices = []
        faces = []
        vertex_map = {}
        vertex_index = 0
        
        for i in range(num_triangles):
            # Skip normal (12 bytes)
            f.read(12)
            
            # Read 3 vertices
            triangle_indices = []
            for j in range(3):
                v = struct.unpack('<fff', f.read(12))
                v_tuple = tuple(v)
                
                if v_tuple not in vertex_map:
                    vertex_map[v_tuple] = vertex_index
                    vertices.append(v)
                    triangle_indices.append(vertex_index)
                    vertex_index += 1
                else:
                    triangle_indices.append(vertex_map[v_tuple])
            
            faces.append(triangle_indices)
            
            # Skip attribute byte count
            f.read(2)
    
    return np.array(vertices), np.array(faces)


def _load_stl_ascii(filepath: Path) -> Tuple[np.ndarray, np.ndarray]:
    """Load ASCII STL file."""
    vertices = []
    faces = []
    vertex_map = {}
    vertex_index = 0
    
    with open(filepath, 'r') as f:
        triangle_vertices = []
        
        for line in f:
            line = line.strip()
            
            if line.startswith('vertex'):
                parts = line.split()
                v = (float(parts[1]), float(parts[2]), float(parts[3]))
                v_tuple = v
                
                if v_tuple not in vertex_map:
                    vertex_map[v_tuple] = vertex_index
                    vertices.append(v)
                    triangle_vertices.append(vertex_index)
                    vertex_index += 1
                else:
                    triangle_vertices.append(vertex_map[v_tuple])
            
            elif line.startswith('endfacet'):
                if len(triangle_vertices) == 3:
                    faces.append(triangle_vertices)
                triangle_vertices = []
    
    return np.array(vertices), np.array(faces)


def load_obj(filepath: Path) -> Tuple[np.ndarray, np.ndarray]:
    """Load OBJ file (basic support, no materials).
    
    Returns:
        (vertices, faces) tuple
    """
    vertices = []
    faces = []
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if not parts:
                continue
            
            if parts[0] == 'v':
                # Vertex
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            
            elif parts[0] == 'f':
                # Face (support v, v/vt, v/vt/vn formats)
                face_indices = []
                for i in range(1, len(parts)):
                    # Parse vertex index (OBJ is 1-indexed)
                    idx_str = parts[i].split('/')[0]
                    idx = int(idx_str) - 1
                    face_indices.append(idx)
                
                # Triangulate if needed (simple fan triangulation)
                for i in range(1, len(face_indices) - 1):
                    faces.append([face_indices[0], face_indices[i], face_indices[i + 1]])
    
    return np.array(vertices), np.array(faces)


def import_mesh_as_sdf(filepath: Path, scale: float = 1.0, 
                      center: bool = True) -> Optional[MeshSDFConverter]:
    """Import a mesh file and prepare for SDF conversion.
    
    Args:
        filepath: Path to STL or OBJ file
        scale: Scale factor to apply
        center: If True, center the mesh at origin
    
    Returns:
        MeshSDFConverter instance or None on failure
    """
    try:
        # Load based on extension
        ext = filepath.suffix.lower()
        
        if ext == '.stl':
            vertices, faces = load_stl(filepath)
        elif ext == '.obj':
            vertices, faces = load_obj(filepath)
        else:
            log.error(f"Unsupported format: {ext}")
            return None
        
        log.info(f"Loaded mesh: {len(vertices)} vertices, {len(faces)} faces")
        
        # Apply scale
        if scale != 1.0:
            vertices = vertices * scale
        
        # Center at origin
        if center:
            centroid = np.mean(vertices, axis=0)
            vertices = vertices - centroid
        
        # Create converter
        converter = MeshSDFConverter(vertices, faces)
        
        return converter
    
    except Exception as e:
        log.exception(f"Failed to import mesh: {e}")
        return None
