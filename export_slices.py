#!/usr/bin/env python3
"""Command-line tool to export cross-section slices from an AMA file."""
from __future__ import annotations

import argparse

from adaptivecad.slice_export import export_slices_from_ama


def main() -> None:
    parser = argparse.ArgumentParser(description="Export cross-section slices from an AMA file")
    parser.add_argument("input", help="Input AMA file path")
    parser.add_argument("heights", nargs="+", type=float, help="Z heights to slice at")
    parser.add_argument("--out-dir", default="slices", help="Directory to store output slice files")
    parser.add_argument("--format", choices=["brep", "stl"], default="brep", help="Output file format")
    args = parser.parse_args()

    export_slices_from_ama(args.input, args.heights, args.out_dir, args.format)


if __name__ == "__main__":
    main()
