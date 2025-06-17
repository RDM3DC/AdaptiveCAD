import math

class VecN:
    def __init__(self, coords):
        self.coords = list(coords)

    def __add__(self, other):
        return VecN([a + b for a, b in zip(self.coords, other.coords)])

    def __sub__(self, other):
        return VecN([a - b for a, b in zip(self.coords, other.coords)])

    def __mul__(self, scalar):
        return VecN([scalar * x for x in self.coords])

    def dot(self, other):
        return sum(a * b for a, b in zip(self.coords, other.coords))

    def norm(self):
        return math.sqrt(self.dot(self))

    def __len__(self):
        return len(self.coords)

    def __getitem__(self, idx):
        return self.coords[idx]

    def __repr__(self):
        return f"VecN({self.coords})"

class BSplineCurveN:
    def __init__(self, control_points, degree, knots):
        self.control_points = control_points  # list of VecN
        self.degree = degree                  # integer p
        self.knots = knots                    # list/array of floats
        self.n = len(control_points) - 1      # number of control points - 1

        # Sanity check for valid knot vector
        expected_knots = self.n + self.degree + 2
        if len(self.knots) != expected_knots:
            raise ValueError(
                f"Knot vector length {len(self.knots)} does not match expected {expected_knots}"
            )

    def find_span(self, u):
        """Find the knot span index for parameter u."""
        if u == self.knots[self.n + 1]:
            return self.n
        low = self.degree
        high = self.n + 1
        mid = (low + high) // 2
        while u < self.knots[mid] or u >= self.knots[mid + 1]:
            if u < self.knots[mid]:
                high = mid
            else:
                low = mid
            mid = (low + high) // 2
        return mid

    def de_boor(self, u):
        """Evaluate the B-spline at parameter u using de Boor's algorithm."""
        k = self.find_span(u)
        p = self.degree
        d = [self.control_points[j + k - p] for j in range(0, p + 1)]
        for r in range(1, p + 1):
            for j in range(p, r - 1, -1):
                i = j + k - p
                alpha = (u - self.knots[i]) / (self.knots[i + p - r + 1] - self.knots[i])
                d[j] = d[j - 1] * (1.0 - alpha) + d[j] * alpha
        return d[p]

    def evaluate(self, u):
        """Evaluate at normalized parameter u in [0, 1]."""
        # Map u in [0,1] to actual knot domain
        u_min = self.knots[self.degree]
        u_max = self.knots[self.n + 1]
        uu = u_min + (u_max - u_min) * u
        return self.de_boor(uu)
