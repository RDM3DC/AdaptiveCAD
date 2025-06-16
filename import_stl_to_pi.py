#!/usr/bin/env python3
"""Convert an STL mesh to AdaptiveCAD's \u03c0\u2090 geometry and save as AMA.

This script demonstrates how to take a standard STL mesh, conform it using
AdaptiveCAD's non‑Euclidean \u03c0\u2090 scaling and export the result as an
AMA archive ready for downstream toolpaths.
"""

import argparse

from adaptivecad.commands.import_conformal import (
    import_mesh_shape,
    extract_bspline_faces,
    conform_bspline_surface,
)
from adaptivecad.command_defs import Feature
from adaptivecad.io import write_ama

from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeFace


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import an STL file and convert it to Adaptive \u03c0 geometry"
    )
    parser.add_argument("stl", help="Path to the STL file to import")
    parser.add_argument(
        "-o", "--output", default="converted.ama", help="Destination AMA file"
    )
    parser.add_argument(
        "-k", "--kappa", type=float, default=1.0, help="\u03ba parameter for \u03c0\u2090 scaling"
    )
    args = parser.parse_args()

    # Load the mesh as an OpenCascade shape
    shape = import_mesh_shape(args.stl)

    # Convert each face to a B-spline surface and apply \u03c0\u2090 scaling
    features = []
    for bs in extract_bspline_faces(shape):
        conform_bspline_surface(bs, args.kappa)
        face = BRepBuilderAPI_MakeFace(bs, 1e-6).Face()
        features.append(Feature("Imported", {"file": args.stl, "kappa": args.kappa}, face))

    write_ama(features, args.output)
    print(f"Saved AMA archive to {args.output}")


if __name__ == "__main__":
    main()
