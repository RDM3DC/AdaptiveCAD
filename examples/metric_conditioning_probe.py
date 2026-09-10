"""Read-only local conditioning experiment using AdaptiveCAD's native surfaces.

This is not a Navier-Stokes solver, a singularity certificate, or an automatic
model rejection rule. It measures one parameterization at one specified point.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass

from adaptivecad.geom.meshfree_tools import Curve, Surface


@dataclass(frozen=True)
class LocalConditioning:
    status: str
    maximum_stretch: float
    minimum_stretch: float
    jacobian_condition: float | None
    metric_condition: float | None


def local_conditioning(surface: Surface, u: float, v: float) -> LocalConditioning:
    """Singular-value ratio of [Su Sv] for the current normalized parameters.

    The ratio is unchanged by rigid spatial rotation and uniform unit conversion,
    but NOT by arbitrary reparameterization. Rank loss and unresolved underflow
    are reported together; floating-point arithmetic is not a proof of either.
    """
    if not isinstance(surface, Surface):
        raise TypeError("Expected a native mesh-free Surface")
    _, a, b, *_ = surface.jet(u, v)
    if not all(math.isfinite(x) for vector in (a, b) for x in vector):
        raise ValueError("Nonfinite surface derivative")
    scale = max(abs(x) for vector in (a, b) for x in vector)
    if scale == 0:
        return LocalConditioning("degenerate_or_unresolved", 0.0, 0.0, None, None)
    an, bn = tuple(x / scale for x in a), tuple(x / scale for x in b)
    E, G = math.fsum(x*x for x in an), math.fsum(x*x for x in bn)
    F = math.fsum(x*y for x, y in zip(an, bn))
    largest = math.sqrt((E + G + math.hypot(E - G, 2*F)) / 2)
    cross = (an[1]*bn[2] - an[2]*bn[1], an[2]*bn[0] - an[0]*bn[2],
             an[0]*bn[1] - an[1]*bn[0])
    # Product of singular values equals area stretch; avoids subtracting
    # almost equal eigenvalues when the angular metric is poorly conditioned.
    smallest = math.hypot(*cross) / largest
    smax, smin = scale*largest, scale*smallest
    if not math.isfinite(smax):
        raise ValueError("Stretch exceeds the supported floating-point range")
    if smallest == 0 or smin == 0:
        return LocalConditioning("degenerate_or_unresolved", smax, 0.0, None, None)
    condition = largest / smallest
    metric_condition = condition*condition
    if not math.isfinite(metric_condition):
        return LocalConditioning("condition_out_of_range", smax, smin, None, None)
    return LocalConditioning("resolved_local_sample", smax, smin, condition, metric_condition)


def experiment():
    """Native flat sheets with equal area and zero curvature but unequal stretch."""
    rows = []
    for epsilon in (1.0, 0.1, 0.01, 0.0001):
        surface = Surface("extrude", Curve.line((0, 0, 0), (epsilon, 0, 0)),
                          vector=(0, 1/epsilon, 0))
        differential = surface.differential(0.5, 0.5)
        row = {"epsilon": epsilon, "parameter_domain_area": surface.area().value,
               "gaussian_curvature": differential["gaussian_curvature"],
               **asdict(local_conditioning(surface, 0.5, 0.5))}
        rows.append(row)
    return {"scope": "numerical experiment, not a fluid model or global certificate",
            "rows": rows}


if __name__ == "__main__":
    print(json.dumps(experiment(), indent=2, allow_nan=False))
