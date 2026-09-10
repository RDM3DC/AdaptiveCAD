"""Numerical geodesic initial-value tracing with optional parallel transport.

Uses analytic Cartesian Christoffel symbols and step-doubled RK4. All accepted
states remain within the normal disk. A trace is not a globally shortest path,
not an embedded 3D curve, and never machine-ready G-code. Output points are a
numerical trajectory, not the source representation of the metric.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .directional_metric import IntegrationError, NormalMetricPatch, _finite
from .metric_tools import christoffel, inner_product, point


@dataclass(frozen=True)
class GeodesicTrace:
    points: tuple[tuple[float, float], ...]
    velocities: tuple[tuple[float, float], ...]
    transported: tuple[tuple[float, float], ...]
    distances: tuple[float, ...]
    status: str
    requested_length: float
    max_speed_error: float
    max_transport_norm_error: float
    accepted_steps: int
    rejected_steps: int


def trace_geodesic(patch: NormalMetricPatch, start, direction, length: float, *,
                   transport=(1.0, 0.0), tolerance=1e-8, max_steps=4096,
                   initial_step=None) -> GeodesicTrace:
    """Trace from start and coordinate direction, normalized to metric unit speed.

    `length` is requested intrinsic arc length in patch units. `tolerance` is
    dimensionless, applied after scaling lengths by patch.length_scale. Status
    'boundary' means a shorter trace ending within numerical tolerance of the
    disk boundary. Budget exhaustion raises IntegrationError; no partial result
    is silently passed off as success. Error diagnostics are not certified bounds.
    """
    start = point(patch, start)
    if len(direction) != 2 or len(transport) != 2:
        raise ValueError("Direction and transported vector need two components")
    v = tuple(_finite(c, "direction") for c in direction)
    w = tuple(_finite(c, "transport") for c in transport)
    length, tolerance = _finite(length, "length"), _finite(tolerance, "tolerance")
    if length < 0 or not 1e-12 <= tolerance <= 1e-3:
        raise ValueError("Require length >= 0 and 1e-12 <= tolerance <= 1e-3")
    if type(max_steps) is not int or not 1 <= max_steps <= 100000:
        raise ValueError("max_steps must be an integer in [1, 100000]")
    speed = patch.speed(*start, *v)
    if speed <= 0:
        raise ValueError("Direction must be nonzero")
    v = tuple(c / speed for c in v)
    scale = patch.length_scale
    q = patch.scaled(1.0 / scale)
    state = (*[c / scale for c in start], *v, *w)
    target = length / scale
    _finite(target, "normalized length")
    hmax = min(0.05, q.radius / 16)
    if initial_step is not None:
        h = _finite(initial_step, "initial_step") / scale
        if h <= 0:
            raise ValueError("initial_step must be positive")
        h = min(h, hmax)
    else:
        h = hmax
    minimum = 1e-13 * q.radius
    if minimum == 0 or hmax == 0:
        raise IntegrationError("Normalized patch scale underflows numerical precision")
    states, distances = [state], [0.0]
    accepted = rejected = 0
    s = 0.0
    status = "complete"
    norm0 = inner_product(q, state[:2], w, w)
    max_speed = max_norm = 0.0

    def rhs(z):
        gamma = christoffel(q, z[0], z[1])
        velocity, vector = z[2:4], z[4:6]
        a = tuple(-math.fsum(gamma[k][i][j] * velocity[i] * velocity[j]
                            for i in range(2) for j in range(2)) for k in range(2))
        dw = tuple(-math.fsum(gamma[k][i][j] * velocity[i] * vector[j]
                             for i in range(2) for j in range(2)) for k in range(2))
        return (*velocity, *a, *dw)

    def rk4(z, step):
        def plus(a, b, c):
            return tuple(x + c * y for x, y in zip(a, b))
        k1 = rhs(z)
        k2 = rhs(plus(z, k1, step / 2))
        k3 = rhs(plus(z, k2, step / 2))
        k4 = rhs(plus(z, k3, step))
        result = tuple(z[i] + step * (k1[i] + 2*k2[i] + 2*k3[i] + k4[i]) / 6
                       for i in range(6))
        point(q, result[:2])
        if not all(math.isfinite(c) for c in result):
            raise IntegrationError("Nonfinite geodesic state")
        return result

    for _ in range(max_steps):
        if s >= target:
            break
        outward = state[0] * state[2] + state[1] * state[3]
        margin = q.radius - math.hypot(*state[:2])
        if margin <= max(minimum, tolerance * q.radius) and outward >= 0:
            status = "boundary"
            break
        h = min(h, target - s)
        if h < minimum:
            if target - s <= minimum:
                # We have a complete result to the stated numerical tolerance;
                # preserve the actual integrated distance, do not fabricate endpoint.
                break
            raise IntegrationError("Step underflow before requested length")
        try:
            full = rk4(state, h)
            half = rk4(rk4(state, h / 2), h / 2)
        except ValueError as exc:
            # Only domain failures trigger boundary step reduction. Invalid
            # coefficients or numerical overflow must not masquerade as a boundary.
            if "outside the declared metric disk" not in str(exc):
                raise IntegrationError(str(exc)) from exc
            rejected += 1
            h /= 2
            continue
        err = max(abs(a - b) / (15 * (1 + max(abs(a), abs(b))))
                  for a, b in zip(full, half))
        if err > tolerance:
            rejected += 1
            h *= max(0.1, 0.8 * (tolerance / err)**0.2)
            continue
        state = half
        s += h
        accepted += 1
        states.append(state)
        distances.append(s * scale)
        max_speed = max(max_speed, abs(q.speed(*state[:4]) - 1))
        norm = inner_product(q, state[:2], state[4:6], state[4:6])
        max_norm = max(max_norm, abs(norm - norm0) / max(1.0, abs(norm0)))
        h = min(hmax, h * (2.0 if err == 0 else min(2.0, 0.9 * (tolerance / err)**0.2)))
    else:
        if s < target:
            raise IntegrationError("Geodesic exceeded max_steps; shorten trace or increase budget")
    return GeodesicTrace(
        tuple((z[0] * scale, z[1] * scale) for z in states),
        tuple(z[2:4] for z in states), tuple(z[4:6] for z in states),
        tuple(distances), status, length, max_speed, max_norm, accepted, rejected,
    )
