"""
Compress anchors in an ATC-PATH container using RDP (default) or AdaptiveCAD.
Usage:
  python -m pathtext.compress_paths input.atcp.json output.atcp.json --eps 2.0 [--method rdp|adaptive] [--minseg 4] [--maxseg 40]
       or
  python -m pathtext.compress_paths input.atcp.json output.atcp.json --target_k 20 [--method topk]
"""

import argparse
import json
import math
from pathlib import Path

from .adaptivecad import adaptive_cad
from .path_compress import compress_anchors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--method", choices=["rdp", "adaptive", "topk"], default="rdp")
    ap.add_argument("--eps", type=float, default=2.0, help="tolerance in pixels (for rdp)")
    ap.add_argument("--minseg", type=float, default=4.0, help="min segment length (adaptive)")
    ap.add_argument("--maxseg", type=float, default=40.0, help="max segment length (adaptive)")
    ap.add_argument("--target_k", type=int, default=None, help="keep top-K points (experimental)")
    args = ap.parse_args()
    obj = json.loads(Path(args.inp).read_text(encoding="utf-8"))
    for p in obj.get("paths", []):
        anchors = p.get("anchors", [])
        comp = None
        if args.method == "rdp":
            comp = compress_anchors(anchors, args.eps)
        elif args.method == "adaptive":
            simp = adaptive_cad(anchors, max_err=args.eps, min_seg=args.minseg, max_seg=args.maxseg)
            # Build comp dict similar to rdp output
            # compute max error by comparing to original
            from .path_compress import _perp_dist

            def max_err(orig, simp_points):
                me = 0.0
                for po in [(float(x), float(y)) for x, y in orig]:
                    mind = 1e18
                    for j in range(len(simp_points) - 1):
                        d = _perp_dist(po, tuple(simp_points[j]), tuple(simp_points[j + 1]))
                        if d < mind:
                            mind = d
                    me = max(me, mind)
                return me

            me = max_err(anchors, simp) if len(simp) >= 2 else 0.0
            comp = {
                "method": "adaptive",
                "eps_px": args.eps,
                "orig_points": len(anchors),
                "new_points": len(simp),
                "max_err_px": me,
                "anchors": simp,
            }
        elif args.method == "topk":
            # naive top-k: rank by curvature and keep endpoints
            pts = [(float(x), float(y)) for x, y in anchors]
            if args.target_k is None or args.target_k >= len(pts):
                simp = anchors
            else:
                # compute curvature scores for interior points
                scores = []
                for i in range(1, len(pts) - 1):
                    ax, ay = pts[i - 1]
                    bx, by = pts[i]
                    cx, cy = pts[i + 1]
                    v1x, v1y = bx - ax, by - ay
                    v2x, v2y = cx - bx, cy - by
                    n1 = (v1x * v1x + v1y * v1y) ** 0.5 + 1e-9
                    n2 = (v2x * v2x + v2y * v2y) ** 0.5 + 1e-9
                    dot = (v1x * v2x + v1y * v2y) / (n1 * n2)
                    dot = max(-1.0, min(1.0, dot))
                    angle = math.acos(dot)
                    scores.append((angle, i))
                scores.sort(reverse=True)
                keep = set([0, len(pts) - 1] + [i for _, i in scores[: max(0, args.target_k - 2)]])
                simp = [[pts[i][0], pts[i][1]] for i in sorted(keep)]
            # compute max error
            from .path_compress import _perp_dist

            def max_err(orig, simp_points):
                me = 0.0
                for po in [(float(x), float(y)) for x, y in orig]:
                    mind = 1e18
                    for j in range(len(simp_points) - 1):
                        d = _perp_dist(po, tuple(simp_points[j]), tuple(simp_points[j + 1]))
                        if d < mind:
                            mind = d
                    me = max(me, mind)
                return me

            me = max_err(anchors, simp) if len(simp) >= 2 else 0.0
            comp = {
                "method": "topk",
                "eps_px": 0.0,
                "orig_points": len(anchors),
                "new_points": len(simp),
                "max_err_px": me,
                "anchors": simp,
            }
        p["anchors_cmc"] = comp
        p["max_err"] = max(p.get("max_err", 0.0), comp["max_err_px"] if comp else 0.0)
    Path(args.out).write_text(json.dumps(obj), encoding="utf-8")
    # Print report
    for p in obj.get("paths", []):
        c = p.get("anchors_cmc", {})
        if c:
            print(
                f'Path {p.get("id")} : {c.get("orig_points")} -> {c.get("new_points")} points, max_err={c.get("max_err_px"):.2f}px ({c.get("method")})'
            )


if __name__ == "__main__":
    main()
