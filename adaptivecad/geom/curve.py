from __future__ import annotations

from abc import ABC, abstractmethod
from ..linalg import Vec3

class Curve(ABC):
    """Abstract parametric curve."""

    @abstractmethod
    def evaluate(self, u: float) -> Vec3:
        """Return point on curve for parameter ``u`` in [0,1]."""
        raise NotImplementedError

    def derivative(self, u: float) -> Vec3:
        """Return first derivative at ``u`` using finite difference if not overridden."""
        eps = 1e-6
        u1 = min(1.0, u + eps)
        u0 = max(0.0, u - eps)
        return (self.evaluate(u1) - self.evaluate(u0)) * (1.0 / (u1 - u0))
