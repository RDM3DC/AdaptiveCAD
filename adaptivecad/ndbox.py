import numpy as np

class NDBox:
    def __init__(self, center, size):
        self.center = np.asarray(center, dtype=float)
        self.size = np.asarray(size, dtype=float)
        assert len(self.center) == len(self.size), "Dim mismatch"
        self.ndim = len(self.center)
    
    def volume(self):
        return np.prod(self.size)
    
    def bounds(self):
        return (self.center - self.size/2, self.center + self.size/2)
    
    def contains(self, point):
        p = np.asarray(point)
        return np.all((p >= self.center - self.size/2) & (p <= self.center + self.size/2))
