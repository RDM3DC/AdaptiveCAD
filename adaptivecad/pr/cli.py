from __future__ import annotations

import argparse
import json
from pathlib import Path

from .tools import augment_ama_with_derived_fields


def _cmd_augment(args: argparse.Namespace) -> int:
    res = augment_ama_with_derived_fields(
        args.ama,
        out_path=args.out,
        include=tuple(args.include),
        smooth_iters=int(args.smooth_iters),
        scale_xy=float(args.scale_xy),
        scale_z=float(args.scale_z),
        units=str(args.units),
    )
    print(json.dumps(res, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m adaptivecad.pr.cli")
    sub = p.add_subparsers(dest="cmd", required=True)

    aug = sub.add_parser("augment", help="Add derived PR layers to an existing AMA (writes a new file by default)")
    aug.add_argument("ama", type=str, help="Path to input .ama")
    aug.add_argument("--out", type=str, default=None, help="Output .ama path (default: *_aug.ama next to input)")
    aug.add_argument(
        "--include",
        type=str,
        nargs="+",
        default=["gradmag", "laplacian", "curvature", "smooth"],
        help="Derived layers to add",
    )
    aug.add_argument("--smooth-iters", type=int, default=4)
    aug.add_argument("--scale-xy", type=float, default=1.0)
    aug.add_argument("--scale-z", type=float, default=1.0)
    aug.add_argument("--units", type=str, default="mm")
    aug.set_defaults(func=_cmd_augment)

    ns = p.parse_args(argv)
    return int(ns.func(ns))


if __name__ == "__main__":
    raise SystemExit(main())
