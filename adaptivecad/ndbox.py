import numpy as np

class NDBox:
    def __init__(self, center, size):
        self.center = np.asarray(center, dtype=float)
        self.size = np.asarray(size, dtype=float)
        assert len(self.center) == len(self.size), "Dimension mismatch"
        self.ndim = len(self.center)

    def volume(self):
        """Calculate the hyper-volume of the ND box."""
        return np.prod(self.size)

    def bounds(self):
        """Get the lower and upper bounds of the box."""
        half_size = self.size / 2
        return (self.center - half_size, self.center + half_size)

    def contains(self, point):
        """Check if the point lies within the box."""
        point = np.asarray(point)
        lower_bound, upper_bound = self.bounds()
        return np.all((point >= lower_bound) & (point <= upper_bound))

    def intersect(self, other):
        """Determine if this box intersects with another NDBox."""
        assert self.ndim == other.ndim, "Dimension mismatch"
        bounds_a = self.bounds()
        bounds_b = other.bounds()
        return np.all(bounds_a[0] <= bounds_b[1]) and np.all(bounds_a[1] >= bounds_b[0])

    def intersection_volume(self, other):
        """Calculate the hyper-volume of intersection with another NDBox."""
        if not self.intersect(other):
            return 0.0

        lower_a, upper_a = self.bounds()
        lower_b, upper_b = other.bounds()

        intersection_lower = np.maximum(lower_a, lower_b)
        intersection_upper = np.minimum(upper_a, upper_b)

        intersection_size = intersection_upper - intersection_lower
        return np.prod(intersection_size)

    def translate(self, vector):
        """Translate the NDBox by the given vector."""
        vector = np.asarray(vector)
        assert vector.shape == self.center.shape, "Dimension mismatch"
        self.center += vector

    def scale(self, factor):
        """Scale the size of the NDBox uniformly or per dimension."""
        factor = np.asarray(factor)
        if factor.size == 1:
            self.size *= factor
        else:
            assert factor.shape == self.size.shape, "Dimension mismatch"
            self.size *= factor
