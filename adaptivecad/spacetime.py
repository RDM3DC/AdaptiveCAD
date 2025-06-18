"""Basic spacetime utilities for AdaptiveCAD.

This module introduces very small helper classes for 4-D
Minkowski spacetime. It is intentionally lightweight so that
other modules can experiment with relativistic concepts such as
light-cone visualization and Lorentz transformations.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Tuple


@dataclass
class Event:
    """A point in Minkowski spacetime with coordinates (t, x, y, z)."""

    t: float
    x: float
    y: float
    z: float

    def as_tuple(self) -> Tuple[float, float, float, float]:
        return (self.t, self.x, self.y, self.z)


def minkowski_interval(e1: Event, e2: Event | None = None) -> float:
    """Return the squared Minkowski interval between two events."""
    if e2 is None:
        e2 = Event(0.0, 0.0, 0.0, 0.0)
    dt = e1.t - e2.t
    dx = e1.x - e2.x
    dy = e1.y - e2.y
    dz = e1.z - e2.z
    return dt * dt - (dx * dx + dy * dy + dz * dz)


def lorentz_boost_x(beta: float) -> Iterable[Iterable[float]]:
    """Return a 4x4 Lorentz boost matrix along the x axis.

    Parameters
    ----------
    beta:
        Velocity as a fraction of the speed of light ``v / c``.
    """
    if abs(beta) >= 1.0:
        raise ValueError("beta magnitude must be < 1")
    gamma = 1.0 / math.sqrt(1.0 - beta * beta)
    return [
        [gamma, -gamma * beta, 0.0, 0.0],
        [-gamma * beta, gamma, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def apply_boost(event: Event, beta: float) -> Event:
    """Apply an x-axis Lorentz boost to an event."""
    M = lorentz_boost_x(beta)
    t = M[0][0] * event.t + M[0][1] * event.x
    x = M[1][0] * event.t + M[1][1] * event.x
    return Event(t, x, event.y, event.z)


def light_cone(event: Event, radius: float, steps: int = 100) -> Tuple[list[Event], list[Event]]:
    """Return sample events on the future and past light-cones."""
    future: list[Event] = []
    past: list[Event] = []
    for i in range(steps):
        phi = 2.0 * math.pi * i / steps
        x = radius * math.cos(phi)
        y = radius * math.sin(phi)
        future.append(Event(event.t + radius, event.x + x, event.y + y, event.z))
        past.append(Event(event.t - radius, event.x + x, event.y + y, event.z))
    return future, past
