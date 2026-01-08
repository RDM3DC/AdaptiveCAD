"""Toy adaptive Josephson lattice simulator.

This module implements the phenomenological model described in the chat: a
2D superconducting lattice whose local barrier field ``pi_a`` adapts via an
entanglement-load proxy. The code is intentionally exploratory and not a
first-principles superconductivity solver.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, Iterable, Sequence, TypedDict, Union, cast

import matplotlib.pyplot as plt
import numpy as np


class SimulationOutput(TypedDict):
    S_map: np.ndarray
    J_map: np.ndarray
    pi_map: np.ndarray
    rho_s: float
    Tc_proxy: float
    history: Dict[str, list[float]]


@dataclass
class SimulationConfig:
    """Configuration for the adaptive lattice."""

    size: int = 48
    steps: int = 400
    dt: float = 0.05
    eta: float = 0.6
    mu: float = 0.10
    s_target: float = 0.50
    gamma: float = 0.5
    noise: float = 0.03
    pi0: float = 1.0
    seed: int | None = 0


class AdaptiveJosephsonLattice:
    """Phenomenological 2D Josephson lattice with adaptive barriers."""

    def __init__(self, cfg: SimulationConfig) -> None:
        self.cfg = cfg
        rng = np.random.default_rng(cfg.seed)
        self.pi = cfg.pi0 + 0.05 * rng.standard_normal((cfg.size, cfg.size))
        self.phi = 2 * np.pi * rng.random((cfg.size, cfg.size))
        self.history: Dict[str, list[float]] = {
            "pi_mean": [],
            "S_mean": [],
            "rho_s": [],
            "Tc": [],
        }

    def _neighbors(self, arr: np.ndarray) -> np.ndarray:
        return (
            np.roll(arr, 1, axis=0)
            + np.roll(arr, -1, axis=0)
            + np.roll(arr, 1, axis=1)
            + np.roll(arr, -1, axis=1)
        )

    def _bond_coupling(self, pi: np.ndarray) -> np.ndarray:
        return np.log1p(np.exp(pi))

    def _entanglement_proxy(
        self,
        J: np.ndarray,
        phi: np.ndarray | None = None,
        noise: float = 0.03,
    ) -> np.ndarray:
        """Bounded entanglement-load proxy rescaled to [S_floor, 1]."""

        phase = self.phi if phi is None else phi
        dphi_x = np.angle(np.exp(1j * (phase - np.roll(phase, -1, axis=1))))
        dphi_y = np.angle(np.exp(1j * (phase - np.roll(phase, -1, axis=0))))
        frustration = dphi_x**2 + dphi_y**2

        rough = (J - self._neighbors(J) / 4.0) ** 2

        S = 0.6 * frustration + 0.4 * rough
        S += noise * np.random.standard_normal(S.shape)
        S = np.clip(S, 0.0, None)

        scale = np.percentile(S, 95) + 1e-9
        S = np.clip(S / scale, 0.0, 1.0)

        S_floor = 0.05
        return np.clip(S, S_floor, 1.0)

    def _superfluid_stiffness(
        self,
        J: np.ndarray,
        phi: np.ndarray | None = None,
        gamma: float | None = None,
    ) -> float:
        """Compute rho_s with a bounded conductance response G(S)."""

        phase = self.phi if phi is None else phi
        s_gamma = self.cfg.gamma if gamma is None else gamma
        S = self._entanglement_proxy(J, phi=phase, noise=0.0)

        Gmin, Gmax = 0.2, 3.0
        G = Gmin + (Gmax - Gmin) * (1.0 / (S**s_gamma))
        G = np.clip(G, Gmin, Gmax)

        return float(np.mean(J * G) / (np.mean(J) + 1e-9))

    def _tc_proxy(self, rho_s: float) -> float:
        return 0.5 * np.pi * rho_s

    def step(self) -> Dict[str, Union[float, np.ndarray]]:
        J = self._bond_coupling(self.pi)
        right = np.roll(self.phi, -1, axis=1)
        left = np.roll(self.phi, 1, axis=1)
        down = np.roll(self.phi, -1, axis=0)
        up = np.roll(self.phi, 1, axis=0)
        current = (
            np.sin(right - self.phi)
            + np.sin(left - self.phi)
            + np.sin(down - self.phi)
            + np.sin(up - self.phi)
        )
        self.phi += self.cfg.dt * (J * current)
        S = self._entanglement_proxy(J, phi=self.phi, noise=self.cfg.noise)
        self.pi += self.cfg.dt * (
            -self.cfg.eta * (S - self.cfg.s_target)
            - self.cfg.mu * (self.pi - self.cfg.pi0)
        )
        pi_cap = 3.0
        self.pi = np.clip(self.pi, -pi_cap, pi_cap)
        rho_s = self._superfluid_stiffness(J, phi=self.phi)
        Tc = self._tc_proxy(rho_s)
        self.history["pi_mean"].append(float(np.mean(self.pi)))
        self.history["S_mean"].append(float(np.mean(S)))
        self.history["rho_s"].append(rho_s)
        self.history["Tc"].append(Tc)
        return {
            "S": S,
            "J": J,
            "rho_s": rho_s,
            "Tc": Tc,
        }


def run_simulation(cfg: SimulationConfig) -> SimulationOutput:
    lattice = AdaptiveJosephsonLattice(cfg)
    last_step: Dict[str, Union[float, np.ndarray]] = {}
    for _ in range(cfg.steps):
        last_step = lattice.step()
    S_map = cast(np.ndarray, last_step["S"])
    J_map = cast(np.ndarray, last_step["J"])
    rho_s = float(last_step["rho_s"])
    Tc_proxy = float(last_step["Tc"])
    result: SimulationOutput = {
        "S_map": S_map,
        "J_map": J_map,
        "pi_map": lattice.pi,
        "rho_s": rho_s,
        "Tc_proxy": Tc_proxy,
        "history": lattice.history,
    }
    return result


def run_sim(
    N: int = 48,
    steps: int = 400,
    eta: float = 0.6,
    mu: float = 0.10,
    S_target: float = 0.50,
    gamma: float = 0.5,
    noise: float = 0.03,
    dt: float = 0.05,
    pi0: float = 1.0,
    seed: int | None = 0,
) -> SimulationOutput:
    """Convenience wrapper that mirrors the CLI defaults."""

    cfg = SimulationConfig(
        size=N,
        steps=steps,
        dt=dt,
        eta=eta,
        mu=mu,
        s_target=S_target,
        gamma=gamma,
        noise=noise,
        pi0=pi0,
        seed=seed,
    )
    return run_simulation(cfg)


def sweep_S_target(
    N: int = 48,
    steps: int = 400,
    eta: float = 0.6,
    mu: float = 0.10,
    gamma: float = 0.5,
    noise: float = 0.03,
    S_targets: Sequence[float] | None = None,
    seeds: Iterable[int] = (0, 1, 2),
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Sweep S_target values and plot Tc_proxy trends with error bars."""

    targets = (
        np.linspace(0.1, 0.9, 9) if S_targets is None else np.array(list(S_targets), dtype=float)
    )
    Tc_means: list[float] = []
    Tc_stds: list[float] = []

    for S_t in targets:
        Tcs = []
        for seed in seeds:
            out = run_sim(
                N=N,
                steps=steps,
                eta=eta,
                mu=mu,
                S_target=float(S_t),
                gamma=gamma,
                noise=noise,
                seed=seed,
            )
            Tcs.append(float(out["Tc_proxy"]))
        Tc_means.append(float(np.mean(Tcs)))
        Tc_stds.append(float(np.std(Tcs)))

    Tc_mean_arr = np.array(Tc_means)
    Tc_std_arr = np.array(Tc_stds)
    best_idx = int(np.argmax(Tc_mean_arr))
    best_S = targets[best_idx]
    best_Tc = Tc_mean_arr[best_idx]

    print(f"Best S_target: {best_S:.3f}")
    print(f"Best Tc_proxy: {best_Tc:.3f}")

    plt.figure(figsize=(7, 4))
    plt.errorbar(targets, Tc_mean_arr, yerr=Tc_std_arr, marker="o", capsize=3)
    plt.axvline(best_S, linestyle="--", alpha=0.6)
    plt.title("Tc proxy vs Entanglement Target")
    plt.xlabel("S_target (toy entropy bound)")
    plt.ylabel("Tc_proxy (toy units)")
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()

    return targets, Tc_mean_arr, Tc_std_arr


def phase_diagram_Tc(
    N: int = 48,
    steps: int = 400,
    etas: Sequence[float] | None = None,
    S_targets: Sequence[float] | None = None,
    mu: float = 0.10,
    gamma: float = 0.5,
    noise: float = 0.03,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Generate a Tc heatmap across eta and S_target knobs."""

    eta_vals = np.array(np.linspace(0.1, 2.0, 8) if etas is None else list(etas), dtype=float)
    target_vals = np.array(
        np.linspace(0.1, 0.9, 9) if S_targets is None else list(S_targets), dtype=float
    )
    Tc_map = np.zeros((len(eta_vals), len(target_vals)))
    pi_map = np.zeros_like(Tc_map)
    S_map = np.zeros_like(Tc_map)

    for i, eta in enumerate(eta_vals):
        for j, S_t in enumerate(target_vals):
            out = run_sim(
                N=N,
                steps=steps,
                eta=float(eta),
                mu=mu,
                S_target=float(S_t),
                gamma=gamma,
                noise=noise,
                seed=seed,
            )
            Tc_map[i, j] = float(out["Tc_proxy"])
            pi_map[i, j] = float(np.mean(cast(np.ndarray, out["pi_map"])))
            S_map[i, j] = float(np.mean(cast(np.ndarray, out["S_map"])))

    plt.figure(figsize=(8, 5))
    plt.imshow(Tc_map, origin="lower", aspect="auto")
    plt.colorbar(label="Tc_proxy (toy)")
    plt.xticks(range(len(target_vals)), [f"{x:.2f}" for x in target_vals])
    plt.yticks(range(len(eta_vals)), [f"{x:.2f}" for x in eta_vals])
    plt.xlabel("S_target")
    plt.ylabel("eta")
    plt.title("Phase diagram: Tc_proxy")
    plt.tight_layout()
    plt.show()

    return eta_vals, target_vals, Tc_map, pi_map, S_map


def parse_args() -> SimulationConfig:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=48, help="lattice size N (NxN)")
    parser.add_argument("--steps", type=int, default=400, help="simulation steps")
    parser.add_argument("--eta", type=float, default=0.6, help="geometry adaptation rate")
    parser.add_argument("--mu", type=float, default=0.10, help="elastic leak term")
    parser.add_argument("--s-target", type=float, default=0.50, help="entanglement target")
    parser.add_argument("--gamma", type=float, default=1.0, help="G ~ 1 / S^gamma scaling")
    parser.add_argument("--noise", type=float, default=0.03, help="noise strength in S proxy")
    parser.add_argument("--dt", type=float, default=0.05, help="integration time step")
    parser.add_argument("--pi0", type=float, default=1.0, help="equilibrium barrier value")
    parser.add_argument("--seed", type=int, default=0, help="rng seed")
    args = parser.parse_args()
    return SimulationConfig(
        size=args.size,
        steps=args.steps,
        dt=args.dt,
        eta=args.eta,
        mu=args.mu,
        s_target=args.s_target,
        gamma=args.gamma,
        noise=args.noise,
        pi0=args.pi0,
        seed=args.seed,
    )


def main() -> None:
    cfg = parse_args()
    result = run_simulation(cfg)
    print(f"Final rho_s (toy units): {result['rho_s']:.4f}")
    print(f"Final Tc_proxy (toy units): {result['Tc_proxy']:.4f}")


if __name__ == "__main__":
    main()
