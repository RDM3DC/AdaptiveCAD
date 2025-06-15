import numpy as np

class NDField:
    def get_slice(self, slice_indices):
        """
        Returns a lower-dimensional slice for visualization.
        `slice_indices` should be a list/tuple with length equal to ndim.
        Use 'None' for axes you want to keep (not slice).
        Example: For shape (4,4,4,4), get_slice([2, None, None, 0]) → 2D slice
        """
        key = tuple(idx if idx is not None else slice(None) for idx in slice_indices)
        data = self.values[key]
        import numpy as np
        return np.asarray(data)
    def __init__(self, grid_shape, values, origin=None, axes=None, spacing=None):
        self.grid_shape = tuple(grid_shape)
        self.values = np.asarray(values, dtype=float).reshape(self.grid_shape)
        self.ndim = len(self.grid_shape)
        self.origin = np.zeros(self.ndim) if origin is None else np.asarray(origin)
        self.axes = np.eye(self.ndim) if axes is None else np.asarray(axes)
        self.spacing = np.ones(self.ndim) if spacing is None else np.asarray(spacing)
    
    def value_at(self, idx):
        return self.values[tuple(idx)]
