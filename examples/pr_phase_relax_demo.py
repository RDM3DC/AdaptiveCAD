"""Phase-Resolved (PR) headless demo.

Runs a grid-based phase relaxation loop and prints summary metrics.
"""

from __future__ import annotations

import argparse

from adaptivecad.pr import PRFieldConfig, relax_phase_field


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--size", type=int, default=64)
    p.add_argument("--steps", type=int, default=200)
    p.add_argument("--dt", type=float, default=0.15)
    p.add_argument("--diffusion", type=float, default=0.35)
    p.add_argument("--coupling", type=float, default=0.25)
    p.add_argument("--coupling-mode", choices=("none", "geom_target"), default="geom_target")
    p.add_argument("--phase-dim", dest="phase_dim", type=int, default=2)
    p.add_argument("--phase-space", dest="phase_space", choices=("unwrapped", "wrapped"), default="unwrapped")
    p.add_argument("--seed", type=int, default=0)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    cfg = PRFieldConfig(
        size=args.size,
        steps=args.steps,
        dt=args.dt,
        diffusion=args.diffusion,
        coupling=args.coupling,
        coupling_mode=args.coupling_mode,
        phase_dim=args.phase_dim,
        phase_space=args.phase_space,
        seed=args.seed,
    )

    metrics, _state = relax_phase_field(cfg)

    print("PR relax complete")
    print(f"coherence: {metrics['coherence']:.6f}")
    print(f"phase_energy: {metrics['phase_energy']:.6f}")
    print(f"coupling_energy: {metrics['coupling_energy']:.6f}")
    print(f"total_energy: {metrics['total_energy']:.6f}")
    print(f"phi_std: {metrics['phi_std']:.6f}")


if __name__ == "__main__":
    main()
