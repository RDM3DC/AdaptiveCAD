"""
AdaptiveCAD Field Integration for Apollonian Sphere Packing
==========================================================

This module extends AdaptiveCAD's field system to support 3D Apollonian
sphere packings, providing SDF operations and field utilities for
procedural geometry generation.

Features:
- 3D sphere packing from 2D circle data
- SDF field generation for complex boolean operations  
- Integration with AdaptiveCAD's adaptive π and norm systems
- Export to various mesh formats

Usage:
    from adaptivecad_apollonian_fields import ApollonianField
    
    # Create field from gasket data
    field = ApollonianField.from_json('apollonian_points.json')
    
    # Generate mesh with adaptive parameters
    mesh = field.to_mesh(resolution=256, use_adaptive_pi=True)
"""

import numpy as np
import json
from pathlib import Path
from typing import List, Tuple, Optional, Union, Dict, Any
import sys
import os

if sys.platform.startswith("win"):
    # Ensure CUDA runtime DLLs shipped via pip are discoverable (Python 3.8+ DLL search changes)
    potential_cuda_dirs = [
        Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / "cuda_runtime" / "bin",
        Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / "cuda_nvrtc" / "bin",
        Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin",
    ]

    for cuda_dir in potential_cuda_dirs:
        if cuda_dir.exists():
            try:
                os.add_dll_directory(str(cuda_dir))
            except (FileNotFoundError, OSError):
                pass
            os.environ["PATH"] = str(cuda_dir) + os.pathsep + os.environ.get("PATH", "")
            if not os.environ.get("CUDA_PATH"):
                os.environ["CUDA_PATH"] = str(cuda_dir.parent)

# Add current directory to path for relative imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

try:
    from adaptivecad.aacore.sdf import mandelbulb_orbit
    from adaptivecad_entangled_fields import AdaptiveField
    HAVE_ADAPTIVECAD = True
except ImportError:
    print("AdaptiveCAD core not found, using fallback implementations")
    HAVE_ADAPTIVECAD = False

try:
    import cupy as cp
    import cupyx.scipy.ndimage as cp_ndimage
    HAVE_CUPY = True
    
    # Check for multiple GPUs and NVLink
    gpu_count = cp.cuda.runtime.getDeviceCount()
    if gpu_count >= 2:
        # Configure memory pool for dual GPU setup
        try:
            mempool = cp.get_default_memory_pool()
            mempool.set_limit(fraction=0.8)  # Use 80% of available GPU memory
            print(f"Detected {gpu_count} GPUs, configured memory pool for multi-GPU")
        except Exception as e:
            print(f"Could not configure GPU memory pool: {e}")
        print(f"Detected {gpu_count} GPUs, enabling multi-GPU support")
    else:
        print(f"Detected {gpu_count} GPU(s)")
    
except ImportError:
    print("CuPy not available, using CPU-only operations")
    HAVE_CUPY = False
    gpu_count = 0

try:
    import trimesh
    HAVE_TRIMESH = True
except ImportError:
    print("trimesh not available, mesh export will be limited")
    HAVE_TRIMESH = False

try:
    from skimage.measure import marching_cubes
    HAVE_SKIMAGE = True
except ImportError:
    print("scikit-image not available, mesh generation will be limited")
    HAVE_SKIMAGE = False

class ApollonianSphere:
    """Represents a single sphere in the 3D packing."""
    
    def __init__(self, center: np.ndarray, radius: float, curvature: float, depth: int):
        self.center = np.asarray(center, dtype=np.float64)
        self.radius = float(radius)
        self.curvature = float(curvature)
        self.depth = int(depth)
    
    def sdf(self, points: np.ndarray) -> np.ndarray:
        """Compute signed distance to this sphere."""
        distances = np.linalg.norm(points - self.center, axis=-1)
        return distances - self.radius
    
    def contains(self, points: np.ndarray) -> np.ndarray:
        """Check if points are inside this sphere."""
        return self.sdf(points) <= 0

class ApollonianField:
    """
    3D Apollonian sphere packing field with multi-GPU SDF operations.
    
    Supports various extrusion modes:
    - Cylinder: Extrude 2D circles to cylinders
    - Sphere: Convert circles to spheres at same positions
    - Torus: Revolve circles around a central axis
    - Custom: User-defined extrusion function
    
    Multi-GPU features:
    - Automatic workload distribution across available GPUs
    - Unified memory management for NVLink systems
    - Chunked processing for large datasets
    """
    
    def __init__(self, spheres: List[ApollonianSphere], 
                 bounds: Optional[Tuple[float, float, float, float, float, float]] = None,
                 use_gpu: bool = True,
                 max_spheres_per_chunk: int = 5000):
        """
        Initialize field from list of spheres.
        
        Args:
            spheres: List of ApollonianSphere objects
            bounds: Optional (xmin, xmax, ymin, ymax, zmin, zmax) bounds
            use_gpu: Whether to use GPU acceleration when available
            max_spheres_per_chunk: Maximum spheres to process per GPU chunk
        """
        self.spheres = spheres
        self.use_gpu = use_gpu and HAVE_CUPY
        self.max_spheres_per_chunk = max_spheres_per_chunk
        self.gpu_count = gpu_count if self.use_gpu else 0
        
        if bounds is None:
            # Auto-compute bounds from sphere extents
            if spheres:
                centers = np.array([s.center for s in spheres])
                radii = np.array([s.radius for s in spheres])
                
                mins = np.min(centers - radii[:, np.newaxis], axis=0)
                maxs = np.max(centers + radii[:, np.newaxis], axis=0)

                # Add 10% margin and store bounds in (xmin, xmax, ymin, ymax, zmin, zmax)
                margin = (maxs - mins) * 0.1
                min_extents = mins - margin
                max_extents = maxs + margin
                self.bounds = (
                    float(min_extents[0]), float(max_extents[0]),
                    float(min_extents[1]), float(max_extents[1]),
                    float(min_extents[2]), float(max_extents[2])
                )
            else:
                self.bounds = (-1, 1, -1, 1, -1, 1)
        else:
            self.bounds = bounds
        
        # Pre-compute sphere data for GPU operations
        if self.use_gpu and spheres:
            self._prepare_gpu_data()
        
        print(f"ApollonianField: {len(spheres)} spheres, GPU: {self.use_gpu}, Multi-GPU: {self.gpu_count > 1}")
    
    def _prepare_gpu_data(self):
        """Pre-compute sphere data arrays for efficient GPU operations."""
        if not self.spheres:
            return
            
        # Pack sphere data into arrays for vectorized operations
        self.sphere_centers = np.array([s.center for s in self.spheres], dtype=np.float32)
        self.sphere_radii = np.array([s.radius for s in self.spheres], dtype=np.float32)
        self.sphere_curvatures = np.array([s.curvature for s in self.spheres], dtype=np.float32)
        self.sphere_depths = np.array([s.depth for s in self.spheres], dtype=np.int32)
        
        self._device_sphere_cache: Dict[int, Tuple['cp.ndarray', 'cp.ndarray', 'cp.ndarray', 'cp.ndarray']] = {}

        # Prime device 0 cache when available
        if self.use_gpu:
            with cp.cuda.Device(0):
                centers = cp.asarray(self.sphere_centers)
                radii = cp.asarray(self.sphere_radii)
                curvatures = cp.asarray(self.sphere_curvatures)
                depths = cp.asarray(self.sphere_depths)
            self._device_sphere_cache[0] = (centers, radii, curvatures, depths)

    def _get_device_spheres(self, gpu_id: int):
        """Retrieve (centers, radii, curvatures, depths) arrays resident on the target GPU."""
        if not self.use_gpu:
            raise RuntimeError("GPU data requested but GPU acceleration is disabled")

        if not hasattr(self, '_device_sphere_cache'):
            self._device_sphere_cache = {}

        if gpu_id in self._device_sphere_cache:
            return self._device_sphere_cache[gpu_id]

        with cp.cuda.Device(gpu_id):
            centers = cp.asarray(self.sphere_centers)
            radii = cp.asarray(self.sphere_radii)
            curvatures = cp.asarray(self.sphere_curvatures)
            depths = cp.asarray(self.sphere_depths)

        self._device_sphere_cache[gpu_id] = (centers, radii, curvatures, depths)
        return self._device_sphere_cache[gpu_id]
    
    @classmethod
    def from_circles_2d(cls, circles_data: List[Tuple[float, float, float, int]], 
                       extrusion_mode: str = "cylinder",
                       extrusion_height: float = 2.0,
                       max_spheres: int = 20000,  # Increased for dual GPU setup
                       min_radius: float = 0.005,  # Filter tiny circles more aggressively
                       use_gpu: bool = True,
                       **extrusion_kwargs) -> 'ApollonianField':
        """
        Create 3D field from 2D circle data with optimized sphere generation.
        
        Args:
            circles_data: List of (x, y, radius, depth) tuples
            extrusion_mode: How to convert 2D circles to 3D ("cylinder", "sphere", "torus")
            extrusion_height: Height parameter for extrusion
            max_spheres: Maximum spheres to generate (increased for dual GPU)
            min_radius: Minimum circle radius to include
            use_gpu: Whether to use GPU acceleration
            **extrusion_kwargs: Additional parameters for specific extrusion modes
            
        Returns:
            ApollonianField with 3D spheres
        """
        spheres = []
        circles_processed = 0
        
        # Filter and sort circles by size (largest first for better performance)
        filtered_circles = [(x, y, r, d) for x, y, r, d in circles_data if r >= min_radius]
        filtered_circles.sort(key=lambda c: c[2], reverse=True)  # Sort by radius descending
        
        print(f"Processing {len(filtered_circles)} circles (filtered from {len(circles_data)})")
        
        for x, y, radius, depth in filtered_circles:
            if len(spheres) >= max_spheres:
                print(f"Reached sphere limit ({max_spheres}), stopping generation")
                break
                
            circles_processed += 1
            if circles_processed % 1000 == 0:
                print(f"Processed {circles_processed}/{len(filtered_circles)} circles, generated {len(spheres)} spheres")
            
            if extrusion_mode == "cylinder":
                # Create fewer, larger spheres for small radii to reduce memory usage
                base_spheres = max(1, int(extrusion_height / (radius * 2.0)))
                num_spheres = min(base_spheres, 3)  # Cap at 3 spheres per cylinder
                
                if num_spheres == 1:
                    z_positions = [0.0]
                else:
                    z_positions = np.linspace(-extrusion_height/2, extrusion_height/2, num_spheres)
                
                for z in z_positions:
                    center = np.array([x, y, z])
                    curvature = 1.0 / radius if radius > 0 else 0
                    sphere = ApollonianSphere(center, radius, curvature, depth)
                    spheres.append(sphere)
                    
            elif extrusion_mode == "sphere":
                # Single sphere at circle center
                center = np.array([x, y, 0])
                curvature = 1.0 / radius if radius > 0 else 0
                sphere = ApollonianSphere(center, radius, curvature, depth)
                spheres.append(sphere)
                
            elif extrusion_mode == "torus":
                # Revolve circle around z-axis with fewer samples for performance
                revolution_radius = extrusion_kwargs.get("revolution_radius", 2.0)
                num_spheres = min(extrusion_kwargs.get("num_spheres", 8), 8)  # Reduced from 16
                
                angles = np.linspace(0, 2*np.pi, num_spheres, endpoint=False)
                
                for angle in angles:
                    # Revolve the circle center around z-axis
                    original_r = np.sqrt(x*x + y*y)
                    new_r = revolution_radius + original_r * np.cos(angle)
                    new_z = original_r * np.sin(angle)
                    
                    center = np.array([new_r * np.cos(0), new_r * np.sin(0), new_z])
                    curvature = 1.0 / radius if radius > 0 else 0
                    sphere = ApollonianSphere(center, radius * 0.8, curvature, depth)  # Slightly smaller for overlap
                    spheres.append(sphere)
            
            else:
                raise ValueError(f"Unknown extrusion mode: {extrusion_mode}")
        
        print(f"Generated {len(spheres)} spheres from {circles_processed} circles")
        return cls(spheres, use_gpu=use_gpu)
        """
        Create 3D field from 2D circle data.
        
        Args:
            circles_data: List of (x, y, radius, depth) tuples
            extrusion_mode: How to convert 2D circles to 3D ("cylinder", "sphere", "torus")
            extrusion_height: Height parameter for extrusion
            **extrusion_kwargs: Additional parameters for specific extrusion modes
            
        Returns:
            ApollonianField with 3D spheres
        """
        spheres = []
        
        for x, y, radius, depth in circles_data:
            if extrusion_mode == "cylinder":
                # Create spheres along z-axis to approximate cylinder
                num_spheres = max(2, int(extrusion_height / (radius * 0.5)))
                z_positions = np.linspace(-extrusion_height/2, extrusion_height/2, num_spheres)
                
                for z in z_positions:
                    center = np.array([x, y, z])
                    curvature = 1.0 / radius if radius > 0 else 0
                    sphere = ApollonianSphere(center, radius, curvature, depth)
                    spheres.append(sphere)
                    
            elif extrusion_mode == "sphere":
                # Single sphere at circle center
                center = np.array([x, y, 0])
                curvature = 1.0 / radius if radius > 0 else 0
                sphere = ApollonianSphere(center, radius, curvature, depth)
                spheres.append(sphere)
                
            elif extrusion_mode == "torus":
                # Revolve circle around z-axis
                revolution_radius = extrusion_kwargs.get("revolution_radius", 2.0)
                num_spheres = extrusion_kwargs.get("num_spheres", 16)
                
                angles = np.linspace(0, 2*np.pi, num_spheres, endpoint=False)
                
                for angle in angles:
                    # Revolve the circle center around z-axis
                    original_r = np.sqrt(x*x + y*y)
                    new_r = revolution_radius + original_r * np.cos(angle)
                    new_z = original_r * np.sin(angle)
                    
                    center = np.array([new_r * np.cos(0), new_r * np.sin(0), new_z])
                    curvature = 1.0 / radius if radius > 0 else 0
                    sphere = ApollonianSphere(center, radius * 0.8, curvature, depth)  # Slightly smaller for overlap
                    spheres.append(sphere)
            
            else:
                raise ValueError(f"Unknown extrusion mode: {extrusion_mode}")
        
        return cls(spheres)
    
    @classmethod
    def from_json(cls, json_path: str, **extrusion_kwargs) -> 'ApollonianField':
        """
        Load field from JSON file created by apollonian_gasket.py.
        
        Args:
            json_path: Path to JSON file
            **extrusion_kwargs: Passed to from_circles_2d
            
        Returns:
            ApollonianField instance
        """
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        # Extract circle data
        points = data["points"]
        attributes = data["attributes"]
        
        circles_data = []
        for i, point in enumerate(points):
            x, y = point[0], point[1]
            radius = attributes["radius"][i]
            depth = attributes["depth"][i]
            
            # Skip outer circles (negative curvature)
            if not attributes["outer_circle"][i]:
                circles_data.append((x, y, radius, depth))
        
        print(f"Loaded {len(circles_data)} circles from {json_path}")
        return cls.from_circles_2d(circles_data, **extrusion_kwargs)
    
    def _determine_point_chunk(self, total_points: int) -> int:
        """Heuristic for point chunk sizing to balance memory and throughput."""
        if total_points <= 250_000:
            return total_points
        return 250_000

    def _evaluate_chunk_gpu(self, points_chunk: np.ndarray, gpu_id: int = 0,
                             need_attributes: bool = False) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """Evaluate distances (and optionally attributes) for a chunk on the given GPU."""
        if not self.use_gpu or not hasattr(self, 'gpu_centers'):
            return self._evaluate_chunk_cpu(points_chunk, need_attributes)

        with cp.cuda.Device(gpu_id):
            gpu_points = cp.asarray(points_chunk, dtype=cp.float32)
            best_dist = cp.full((gpu_points.shape[0],), cp.float32(np.inf), dtype=cp.float32)

            if need_attributes:
                best_index = cp.full((gpu_points.shape[0],), -1, dtype=cp.int32)
                best_curv = cp.zeros((gpu_points.shape[0],), dtype=cp.float32)
                best_depth = cp.zeros((gpu_points.shape[0],), dtype=cp.int32)
            else:
                best_index = best_curv = best_depth = None

            device_centers, device_radii, device_curvatures, device_depths = self._get_device_spheres(gpu_id)

            for sphere_start in range(0, len(self.spheres), self.max_spheres_per_chunk):
                sphere_end = min(sphere_start + self.max_spheres_per_chunk, len(self.spheres))

                centers_chunk = device_centers[sphere_start:sphere_end]
                radii_chunk = device_radii[sphere_start:sphere_end]

                diff = gpu_points[:, None, :] - centers_chunk[None, :, :]
                distances = cp.linalg.norm(diff, axis=2) - radii_chunk[None, :]

                chunk_min = cp.min(distances, axis=1)
                better = chunk_min < best_dist

                if cp.any(better):
                    best_dist = cp.where(better, chunk_min, best_dist)
                    if need_attributes:
                        chunk_arg = cp.argmin(distances, axis=1)
                        global_indices = chunk_arg + sphere_start
                        best_index = cp.where(better, global_indices.astype(cp.int32), best_index)
                        curv_slice = device_curvatures[sphere_start:sphere_end]
                        depth_slice = device_depths[sphere_start:sphere_end]
                        chosen_curv = curv_slice[chunk_arg]
                        chosen_depth = depth_slice[chunk_arg]
                        best_curv = cp.where(better, chosen_curv.astype(cp.float32), best_curv)
                        best_depth = cp.where(better, chosen_depth.astype(cp.int32), best_depth)

            distances_np = cp.asnumpy(best_dist)
            if need_attributes:
                return (
                    distances_np,
                    cp.asnumpy(best_curv),
                    cp.asnumpy(best_depth),
                    cp.asnumpy(best_index),
                )
            return distances_np, None, None, None

    def _evaluate_chunk_cpu(self, points_chunk: np.ndarray, need_attributes: bool = False) -> Tuple[np.ndarray, Optional[np.ndarray], Optional[np.ndarray], Optional[np.ndarray]]:
        """CPU fallback evaluation with minimal allocations."""
        n_points = len(points_chunk)
        best_dist = np.full(n_points, np.inf, dtype=np.float32)

        if need_attributes:
            best_curv = np.zeros(n_points, dtype=np.float32)
            best_depth = np.zeros(n_points, dtype=np.int32)
            best_index = np.full(n_points, -1, dtype=np.int32)
        else:
            best_curv = best_depth = best_index = None

        for idx, sphere in enumerate(self.spheres):
            sphere_dist = sphere.sdf(points_chunk).astype(np.float32)
            better = sphere_dist < best_dist

            if not np.any(better):
                continue

            best_dist[better] = sphere_dist[better]

            if need_attributes:
                best_curv[better] = sphere.curvature
                best_depth[better] = sphere.depth
                best_index[better] = idx

        if need_attributes:
            return best_dist, best_curv, best_depth, best_index
        return best_dist, None, None, None

    def _evaluate_field(self, points: np.ndarray, include_attributes: bool = False) -> Union[np.ndarray, Tuple[np.ndarray, Dict[str, np.ndarray]]]:
        """Shared evaluation path for SDF-only and SDF+attribute queries."""
        if points.ndim < 2 or points.shape[-1] != 3:
            raise ValueError("Points array must have shape (..., 3)")

        target_shape = points.shape[:-1]
        total_points = int(np.prod(target_shape))

        if total_points == 0:
            empty = np.empty(target_shape, dtype=np.float32)
            if include_attributes:
                attributes = {
                    'curvature': empty.copy(),
                    'depth': empty.copy().astype(np.int32),
                    'closest_sphere': empty.copy().astype(np.int32),
                }
                return empty, attributes
            return empty

        flat_points = points.reshape(-1, 3).astype(np.float32)

        if not self.spheres:
            distances = np.full(target_shape, np.inf, dtype=np.float32)
            if include_attributes:
                zero_f = np.zeros(target_shape, dtype=np.float32)
                zero_i = np.zeros(target_shape, dtype=np.int32)
                attributes = {
                    'curvature': zero_f,
                    'depth': zero_i,
                    'closest_sphere': np.full(target_shape, -1, dtype=np.int32),
                }
                return distances, attributes
            return distances

        chunk_size = self._determine_point_chunk(total_points)
        chunk_size = max(1, chunk_size)

        dist_buffer = np.empty(total_points, dtype=np.float32)
        if include_attributes:
            curv_buffer = np.empty(total_points, dtype=np.float32)
            depth_buffer = np.empty(total_points, dtype=np.int32)
            index_buffer = np.empty(total_points, dtype=np.int32)
        else:
            curv_buffer = depth_buffer = index_buffer = None

        chunk_id = 0
        for start in range(0, total_points, chunk_size):
            end = min(start + chunk_size, total_points)
            point_chunk = flat_points[start:end]
            gpu_id = 0
            if self.use_gpu and self.gpu_count > 0:
                if self.gpu_count > 1:
                    gpu_id = chunk_id % self.gpu_count
                chunk_result = self._evaluate_chunk_gpu(point_chunk, gpu_id, include_attributes)
            else:
                chunk_result = self._evaluate_chunk_cpu(point_chunk, include_attributes)

            dist_buffer[start:end] = chunk_result[0]

            if include_attributes:
                curv_buffer[start:end] = chunk_result[1]
                depth_buffer[start:end] = chunk_result[2]
                index_buffer[start:end] = chunk_result[3]

            chunk_id += 1

        distances = dist_buffer.reshape(target_shape)

        if not include_attributes:
            return distances

        attributes = {
            'curvature': curv_buffer.reshape(target_shape),
            'depth': depth_buffer.reshape(target_shape),
            'closest_sphere': index_buffer.reshape(target_shape),
        }

        return distances, attributes

    def sdf_gpu_multi(self, points: np.ndarray) -> np.ndarray:
        """Retained for backward compatibility; delegates to unified evaluator."""
        return self._evaluate_field(points, include_attributes=False)

    def sdf(self, points: np.ndarray) -> np.ndarray:
        """Compute signed distance field, automatically choosing GPU or CPU."""
        return self._evaluate_field(points, include_attributes=False)

    def sdf_with_attributes(self, points: np.ndarray) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Compute SDF alongside curvature/depth metadata without massive stacks."""
        result = self._evaluate_field(points, include_attributes=True)
        assert isinstance(result, tuple)
        return result
    
    def to_mesh(self, resolution: int = 128, 
                use_adaptive_pi: bool = False,
                adaptive_params: Optional[Dict[str, Any]] = None) -> Optional[object]:
        """
        Generate mesh using marching cubes.
        
        Args:
            resolution: Grid resolution per axis
            use_adaptive_pi: Whether to use AdaptiveCAD's adaptive π
            adaptive_params: Parameters for adaptive operations
            
        Returns:
            Mesh object (trimesh.Trimesh if available, else dict)
        """
        if not HAVE_SKIMAGE:
            print("scikit-image required for mesh generation")
            return None
        
        # Create sampling grid
        xmin, xmax, ymin, ymax, zmin, zmax = self.bounds
        
        x = np.linspace(xmin, xmax, resolution)
        y = np.linspace(ymin, ymax, resolution)
        z = np.linspace(zmin, zmax, resolution)
        
        X, Y, Z = np.meshgrid(x, y, z, indexing='ij')
        points = np.stack([X, Y, Z], axis=-1)
        
        print(f"Sampling SDF on {resolution}³ grid...")
        
        # Compute SDF with attributes
        sdf_values, attributes = self.sdf_with_attributes(points)
        
        # Apply adaptive operations if requested
        if use_adaptive_pi and HAVE_ADAPTIVECAD and adaptive_params:
            print("Applying adaptive π modifications...")
            # This would integrate with AdaptiveCAD's adaptive systems
            # Implementation depends on specific adaptive_params
            pass
        
        print("Running marching cubes...")
        
        try:
            # Run marching cubes
            verts, faces, normals, _ = marching_cubes(
                sdf_values, level=0.0, 
                spacing=(
                    (xmax-xmin)/(resolution-1),
                    (ymax-ymin)/(resolution-1), 
                    (zmax-zmin)/(resolution-1)
                )
            )
            
            # Transform to world coordinates
            verts[:, 0] += xmin
            verts[:, 1] += ymin
            verts[:, 2] += zmin
            
            print(f"Generated mesh: {len(verts)} vertices, {len(faces)} faces")
            
            # Compute vertex colors from attributes
            vertex_curvatures = []
            vertex_depths = []
            
            for i, vertex in enumerate(verts):
                # Find closest grid point for attribute lookup
                xi = int((vertex[0] - xmin) / (xmax - xmin) * (resolution - 1))
                yi = int((vertex[1] - ymin) / (ymax - ymin) * (resolution - 1))
                zi = int((vertex[2] - zmin) / (zmax - zmin) * (resolution - 1))
                
                # Clamp to valid range
                xi = max(0, min(resolution-1, xi))
                yi = max(0, min(resolution-1, yi))
                zi = max(0, min(resolution-1, zi))
                
                vertex_curvatures.append(attributes['curvature'][xi, yi, zi])
                vertex_depths.append(attributes['depth'][xi, yi, zi])
            
            vertex_colors = self._compute_vertex_colors(vertex_curvatures, vertex_depths)
            
            # Create mesh object
            if HAVE_TRIMESH:
                mesh = trimesh.Trimesh(
                    vertices=verts, 
                    faces=faces,
                    vertex_normals=normals,
                    vertex_colors=vertex_colors,
                    process=False
                )
                return mesh
            else:
                return {
                    'vertices': verts,
                    'faces': faces,
                    'normals': normals,
                    'vertex_colors': vertex_colors,
                    'curvatures': vertex_curvatures,
                    'depths': vertex_depths
                }
        
        except Exception as e:
            print(f"Marching cubes failed: {e}")
            return None
    
    def _compute_vertex_colors(self, curvatures: List[float], depths: List[int]) -> np.ndarray:
        """Compute RGB colors from curvature and depth values."""
        colors = np.zeros((len(curvatures), 3), dtype=np.uint8)
        
        if not curvatures:
            return colors
        
        # Normalize curvature to 0-1 range
        curv_array = np.array(curvatures)
        if np.max(curv_array) > np.min(curv_array):
            curv_norm = (curv_array - np.min(curv_array)) / (np.max(curv_array) - np.min(curv_array))
        else:
            curv_norm = np.zeros_like(curv_array)
        
        # Normalize depth to 0-1 range
        depth_array = np.array(depths)
        if np.max(depth_array) > np.min(depth_array):
            depth_norm = (depth_array - np.min(depth_array)) / (np.max(depth_array) - np.min(depth_array))
        else:
            depth_norm = np.zeros_like(depth_array)
        
        # Generate colors: curvature -> red, depth -> blue, mixed -> green
        colors[:, 0] = (curv_norm * 255).astype(np.uint8)          # Red channel
        colors[:, 1] = ((curv_norm * depth_norm) * 255).astype(np.uint8)  # Green channel
        colors[:, 2] = (depth_norm * 255).astype(np.uint8)        # Blue channel
        
        return colors
    
    def export_mesh(self, filename: str, resolution: int = 128, **kwargs):
        """
        Export mesh to file.
        
        Args:
            filename: Output filename (extension determines format)
            resolution: Grid resolution
            **kwargs: Additional arguments passed to to_mesh
        """
        mesh = self.to_mesh(resolution=resolution, **kwargs)
        
        if mesh is None:
            print("Failed to generate mesh")
            return
        
        if HAVE_TRIMESH and hasattr(mesh, 'export'):
            mesh.export(filename)
            print(f"Exported mesh to {filename}")
        else:
            # Fallback export for basic formats
            if filename.endswith('.obj'):
                self._export_obj(mesh, filename)
            else:
                print(f"Export format not supported: {filename}")
    
    def _export_obj(self, mesh_dict: Dict[str, Any], filename: str):
        """Export mesh dictionary to OBJ format."""
        verts = mesh_dict['vertices']
        faces = mesh_dict['faces']
        colors = mesh_dict.get('vertex_colors')
        
        with open(filename, 'w') as f:
            f.write("# Apollonian sphere packing mesh\n")
            
            # Write vertices
            for i, v in enumerate(verts):
                if colors is not None:
                    r, g, b = colors[i] / 255.0
                    f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f} {r:.3f} {g:.3f} {b:.3f}\n")
                else:
                    f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
            
            # Write faces (OBJ uses 1-based indexing)
            for face in faces:
                f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")
        
        print(f"Exported OBJ mesh to {filename}")

def create_example_field(max_depth: int = 3) -> ApollonianField:
    """Create an example Apollonian field for testing."""
    # Generate simple test data
    circles_data = [
        (0.0, 0.0, 0.5, 0),      # Center circle
        (0.7, 0.0, 0.2, 1),      # Right circle
        (-0.35, 0.606, 0.2, 1),  # Top-left circle
        (-0.35, -0.606, 0.2, 1), # Bottom-left circle
    ]
    
    return ApollonianField.from_circles_2d(
        circles_data, 
        extrusion_mode="cylinder",
        extrusion_height=2.0
    )

def main():
    """Example usage of the ApollonianField class."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate Apollonian sphere packing mesh')
    parser.add_argument('--input', type=str, help='Input JSON file from apollonian_gasket.py')
    parser.add_argument('--output', type=str, default='apollonian_spheres.obj', help='Output mesh file')
    parser.add_argument('--resolution', type=int, default=128, help='Grid resolution')
    parser.add_argument('--extrusion', choices=['cylinder', 'sphere', 'torus'], 
                       default='cylinder', help='Extrusion mode')
    parser.add_argument('--height', type=float, default=2.0, help='Extrusion height')
    
    args = parser.parse_args()
    
    if args.input:
        # Load from JSON file
        field = ApollonianField.from_json(
            args.input,
            extrusion_mode=args.extrusion,
            extrusion_height=args.height
        )
    else:
        # Create example field
        print("No input file specified, creating example field")
        field = create_example_field()
    
    print(f"Field contains {len(field.spheres)} spheres")
    print(f"Field bounds: {field.bounds}")
    
    # Export mesh
    field.export_mesh(args.output, resolution=args.resolution)

if __name__ == '__main__':
    main()