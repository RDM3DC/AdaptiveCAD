import numpy as np
from scipy.interpolate import RegularGridInterpolator

class NDField:
    def __init__(self, grid_shape, values, origin=None, axes=None, spacing=None):
        self.grid_shape = tuple(grid_shape)
        self.values = np.asarray(values, dtype=float).reshape(self.grid_shape)
        self.ndim = len(self.grid_shape)
        self.origin = np.zeros(self.ndim) if origin is None else np.asarray(origin)
        self.axes = np.eye(self.ndim) if axes is None else np.asarray(axes)
        self.spacing = np.ones(self.ndim) if spacing is None else np.asarray(spacing)
        self._build_interpolator()

    def _build_interpolator(self):
        """Constructs an interpolator for continuous value queries."""
        grid_points = [self.origin[dim] + self.spacing[dim] * np.arange(self.grid_shape[dim]) for dim in range(self.ndim)]
        self.interpolator = RegularGridInterpolator(grid_points, self.values)

    def get_slice(self, slice_indices):
        """
        Returns a lower-dimensional slice for visualization.
        Use 'None' for axes you want to retain.
        Example: shape (4,4,4,4), get_slice([2, None, None, 0]) → 2D slice
        """
        key = tuple(idx if idx is not None else slice(None) for idx in slice_indices)
        data = self.values[key]
        return np.asarray(data)

    def value_at(self, idx):
        """Retrieve discrete grid value at given index."""
        return self.values[tuple(idx)]

    def interpolate(self, coords):
        """Interpolate the field value at continuous coordinates."""
        coords = np.asarray(coords)
        return self.interpolator(coords)

    def transform_to_global(self, local_coords):
        """Convert local grid coordinates to global coordinates."""
        return self.origin + np.dot(self.axes, local_coords * self.spacing)

    def transform_to_local(self, global_coords):
        """Convert global coordinates to local grid coordinates."""
        return np.linalg.solve(self.axes, global_coords - self.origin) / self.spacing

    def apply_function(self, func):
        """Apply a function element-wise to the field values."""
        new_values = func(self.values)
        return NDField(self.grid_shape, new_values, self.origin, self.axes, self.spacing)

    def normalize(self):
        """Normalize field values to [0,1] range."""
        min_val = np.min(self.values)
        max_val = np.max(self.values)
        normalized_values = (self.values - min_val) / (max_val - min_val)
        return NDField(self.grid_shape, normalized_values, self.origin, self.axes, self.spacing)

    def gradient(self):
        """Compute the numerical gradient of the field."""
        grad = np.gradient(self.values, *self.spacing)
        return [NDField(self.grid_shape, g, self.origin, self.axes, self.spacing) for g in grad]

