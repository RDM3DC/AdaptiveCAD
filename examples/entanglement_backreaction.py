"""Minimal entanglement-backreaction prototype.

This module reproduces the exploratory numpy simulation that drives a 1D chain of
qubits, updates local curvature variables (``pi_a``) from von Neumann
entropies, and reports the final state after a fixed number of steps.
"""

from __future__ import annotations

import argparse
import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np


@dataclass
class SimulationParams:
    """Container for the simulation constants."""

    n_qubits: int = 6
    steps: int = 200
    dt: float = 0.1
    lam: float = 0.8
    eta: float = 0.3
    theta_gain: float = 0.2
    entropy_target: float = 0.4


@dataclass
class HamiltonianParams:
    """Parameters for the Hamiltonian-based evolution mode."""

    n_qubits: int = 5
    steps: int = 150
    dt: float = 0.1
    eta: float = 0.5
    entropy_target: float = 0.4
    initial_pi: float = 0.2


@dataclass
class SweepParams:
    """Parameter grid for the phase-sweep study."""

    n_qubits: int = 6
    steps: int = 150
    dt: float = 0.1
    mu: float = 0.1
    etas: Tuple[float, ...] = (0.1, 0.5, 1.0, 2.0)
    targets: Tuple[float, ...] = (0.1, 0.3, 0.5, 0.7)
    pi_rest: float = 1.0
    min_pi: float = 0.0
    capture_examples: int = 4


@dataclass
class SweepResult:
    """Container for phase-sweep outputs."""

    etas: Tuple[float, ...]
    targets: Tuple[float, ...]
    mean_pi: np.ndarray
    mean_std: np.ndarray
    examples: List[Dict[str, Any]]
    mu: float


@dataclass
class StageTwoParams:
    """Configuration for the mutual-information vs geometry analysis."""

    n_qubits: int = 6
    steps: int = 300
    dt: float = 0.1
    eta: float = 0.5
    mu: float = 0.05
    entropy_target: float = 0.65
    pi_rest: float = 1.0
    min_pi: float = 0.0
    distance_metric: str = "mi-log"
    distance_eps: float = 1e-3
    info_eps: float = 1e-4


@dataclass
class GoldilocksParams:
    """Parameter grid for the connectivity/stability sweep."""

    etas: Tuple[float, ...] = (0.05, 0.2, 0.5, 1.0, 2.5)
    targets: Tuple[float, ...] = (0.05, 0.2, 0.45, 0.6, 0.8)
    steps: int = 200
    burn_in: int = 50
    mu: float = 0.01
    n_qubits: int = 6
    dt: float = 0.1
    pi_rest: float = 1.0


def rxx(phi: float) -> np.ndarray:
    """Return the 4x4 RXX(φ) gate matrix."""

    c = np.cos(phi / 2.0)
    s = -1j * np.sin(phi / 2.0)
    x = np.array([[0, 1], [1, 0]], dtype=complex)
    return c * np.eye(4) + s * np.kron(x, x)


def apply_two_qubit(
    u: np.ndarray,
    psi: np.ndarray,
    n: int,
    q1: int,
    q2: int,
) -> np.ndarray:
    """Apply ``u`` to qubits ``q1`` and ``q2`` of ``psi``.

    The axes permutation is made explicit so it works for arbitrary ordering of
    ``q1`` and ``q2``.
    """

    dims = [2] * n
    psi_t = psi.reshape(dims)
    axes: List[int] = [q1, q2] + [i for i in range(n) if i not in (q1, q2)]
    inv_axes = np.zeros_like(axes)
    for idx, axis in enumerate(axes):
        inv_axes[axis] = idx

    psi_front = np.transpose(psi_t, axes).reshape(4, -1)
    psi_front = (u @ psi_front).reshape([2, 2] + [2] * (n - 2))
    psi_t = np.transpose(psi_front, inv_axes).reshape(2**n)
    return psi_t


def reduced_density_matrix(psi: np.ndarray, n: int, keep: Iterable[int]) -> np.ndarray:
    """Return the reduced density matrix for the qubits in ``keep``."""

    keep = list(keep)
    trace_out = [i for i in range(n) if i not in keep]
    dims = [2] * n
    psi_t = psi.reshape(dims)
    axes = keep + trace_out
    psi_re = np.transpose(psi_t, axes).reshape(2 ** len(keep), 2 ** len(trace_out))
    return psi_re @ psi_re.conj().T


def von_neumann_entropy(rho: np.ndarray, eps: float = 1e-12) -> float:
    """Compute the von Neumann entropy of density matrix ``rho``."""

    vals = np.linalg.eigvalsh(rho)
    vals = np.clip(vals, eps, 1.0)
    return float(-np.sum(vals * np.log(vals)))


def partial_trace_to_pair(psi: np.ndarray, n: int, keep_indices: Tuple[int, int]) -> np.ndarray:
    """Return the reduced density matrix for a chosen pair of qubits."""

    psi_tensor = psi.reshape([2] * n)
    trace_indices = [i for i in range(n) if i not in keep_indices]
    permuted_indices = list(keep_indices) + trace_indices
    psi_permuted = np.transpose(psi_tensor, permuted_indices)
    dim_keep = 2 ** len(keep_indices)
    dim_trace = 2 ** len(trace_indices)
    psi_mat = psi_permuted.reshape(dim_keep, dim_trace)
    return psi_mat @ psi_mat.conj().T


def two_qubit_x_operator(n: int, q1: int, q2: int) -> np.ndarray:
    """Construct the full XX operator acting on qubits ``q1`` and ``q2``."""

    x = np.array([[0, 1], [1, 0]], dtype=complex)
    i2 = np.eye(2, dtype=complex)
    ops: List[np.ndarray] = []
    for idx in range(n):
        if idx in (q1, q2):
            ops.append(x)
        else:
            ops.append(i2)

    term = ops[0]
    for mat in ops[1:]:
        term = np.kron(term, mat)
    return term


class QuantumGravityUniverse:
    """Hamiltonian evolution wrapper that tracks aggregate observables."""

    def __init__(self, n_qubits: int = 6, dt: float = 0.1, pi_0: float = 1.0, min_pi: float = 0.0) -> None:
        self.n = n_qubits
        self.dt = dt
        self.dim = 2**n_qubits
        self.edges = [(i, i + 1) for i in range(n_qubits - 1)]
        self.psi = np.zeros(self.dim, dtype=complex)
        self.psi[0] = 1.0
        self.pi_a = {edge: pi_0 for edge in self.edges}
        self.pi_0 = pi_0
        self.min_pi = min_pi
        self.xx_ops = {edge: two_qubit_x_operator(n_qubits, *edge) for edge in self.edges}
        self.history = {"t": [], "pi_avg": [], "S_avg": [], "pi_std": []}

    def step(self, eta: float, mu: float, entropy_target: float) -> None:
        """Advance the state by one dt using the specified feedback gains."""

        h_total = np.zeros((self.dim, self.dim), dtype=complex)
        for edge in self.edges:
            h_total += self.pi_a[edge] * self.xx_ops[edge]

        # eigh keeps the propagation unitary and numerically stable for Hermitian H
        evals, evecs = np.linalg.eigh(h_total)
        u_total = evecs @ np.diag(np.exp(-1j * evals * self.dt)) @ evecs.conj().T
        self.psi = u_total @ self.psi

        s_vals: List[float] = []
        pi_vals: List[float] = []
        for edge in self.edges:
            rho_pair = partial_trace_to_pair(self.psi, self.n, edge)
            s_val = von_neumann_entropy(rho_pair)
            s_vals.append(s_val)
            entanglement_force = -eta * (s_val - entropy_target)
            elastic_force = -mu * (self.pi_a[edge] - self.pi_0)
            updated_pi = self.pi_a[edge] + (entanglement_force + elastic_force) * self.dt
            non_negative = max(0.0, updated_pi)
            self.pi_a[edge] = max(self.min_pi, non_negative)
            pi_vals.append(self.pi_a[edge])

        self.history["t"].append(len(self.history["pi_avg"]) * self.dt)
        self.history["pi_avg"].append(float(np.mean(pi_vals)))
        self.history["S_avg"].append(float(np.mean(s_vals)))
        self.history["pi_std"].append(float(np.std(pi_vals)))


def run_simulation(
    params: SimulationParams,
) -> Tuple[Dict[Tuple[int, int], float], Dict[Tuple[int, int], float]]:
    """Run the backreaction loop and return final entropies and curvatures."""

    n = params.n_qubits
    edges = [(i, i + 1) for i in range(n - 1)]

    psi = np.zeros(2**n, dtype=complex)
    psi[0] = 1.0

    pi_a = {e: np.pi for e in edges}
    theta = {e: 0.0 for e in edges}

    for _ in range(params.steps):
        for e in edges:
            i, j = e
            phi = theta[e] + params.lam * (pi_a[e] - np.pi)
            u = rxx(phi)
            psi = apply_two_qubit(u, psi, n, i, j)

        entropies = {}
        for e in edges:
            i, _ = e
            left = list(range(i + 1))
            rho_left = reduced_density_matrix(psi, n, left)
            entropies[e] = von_neumann_entropy(rho_left)

        for e in edges:
            delta = entropies[e] - params.entropy_target
            pi_a[e] += params.dt * params.eta * delta
            theta[e] += params.dt * params.theta_gain * (-delta)

    return entropies, pi_a


def run_hamiltonian_simulation(
    params: HamiltonianParams,
    plot_history: bool = False,
) -> Tuple[Dict[Tuple[int, int], List[float]], Dict[Tuple[int, int], List[float]]]:
    """Evolve the chain with a global Hamiltonian and record histories."""

    n = params.n_qubits
    dim = 2**n
    edges = [(i, i + 1) for i in range(n - 1)]
    psi = np.zeros(dim, dtype=complex)
    psi[0] = 1.0

    pi_a = {e: params.initial_pi for e in edges}
    xx_ops = {e: two_qubit_x_operator(n, e[0], e[1]) for e in edges}
    history_s = {e: [] for e in edges}
    history_pi = {e: [] for e in edges}

    for _ in range(params.steps):
        h_total = np.zeros((dim, dim), dtype=complex)
        for edge in edges:
            h_total += pi_a[edge] * xx_ops[edge]

        evals, evecs = np.linalg.eigh(h_total)
        u_total = evecs @ np.diag(np.exp(-1j * evals * params.dt)) @ evecs.conj().T
        psi = u_total @ psi

        for edge in edges:
            rho_uv = partial_trace_to_pair(psi, n, edge)
            s_val = von_neumann_entropy(rho_uv)
            delta = s_val - params.entropy_target
            pi_a[edge] = max(0.0, pi_a[edge] - params.eta * delta * params.dt)
            history_s[edge].append(s_val)
            history_pi[edge].append(pi_a[edge])

    if plot_history:
        import matplotlib.pyplot as plt

        fig, (ax_s, ax_pi) = plt.subplots(2, 1, figsize=(10, 8), sharex=True)
        for edge in edges:
            ax_s.plot(history_s[edge], label=f"Bond {edge}")
        ax_s.axhline(params.entropy_target, color="k", linestyle="--", label="Target S")
        ax_s.set_ylabel("Entanglement entropy")
        ax_s.legend(loc="upper right", fontsize="small")
        ax_s.grid(True, alpha=0.3)

        for edge in edges:
            ax_pi.plot(history_pi[edge], label=f"Bond {edge}")
        ax_pi.set_ylabel("pi_a")
        ax_pi.set_xlabel("Time step")
        ax_pi.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.show()

    return history_s, history_pi


def run_parameter_sweep(
    params: SweepParams,
) -> SweepResult:
    """Sweep eta/entropy targets to map phase behaviour."""

    etas = params.etas
    targets = params.targets
    results_pi = np.zeros((len(etas), len(targets)))
    results_osc = np.zeros_like(results_pi)
    examples: List[Dict[str, Any]] = []

    for i, eta in enumerate(etas):
        for j, target in enumerate(targets):
            universe = QuantumGravityUniverse(
                n_qubits=params.n_qubits,
                dt=params.dt,
                pi_0=params.pi_rest,
                min_pi=params.min_pi,
            )
            for _ in range(params.steps):
                universe.step(eta=eta, mu=params.mu, entropy_target=target)

            tail_slice = slice(max(0, len(universe.history["pi_avg"]) - 20), None)
            final_pi = float(np.mean(universe.history["pi_avg"][tail_slice]))
            final_std = float(np.mean(universe.history["pi_std"][tail_slice]))
            results_pi[i, j] = final_pi
            results_osc[i, j] = final_std

            if len(examples) < params.capture_examples:
                examples.append(
                    {
                        "eta": eta,
                        "target": target,
                        "pi_avg": list(universe.history["pi_avg"]),
                        "S_avg": list(universe.history["S_avg"]),
                    }
                )

    return SweepResult(etas=etas, targets=targets, mean_pi=results_pi, mean_std=results_osc, examples=examples, mu=params.mu)


def plot_representative_trajectories(result: SweepResult) -> None:
    """Plot a small set of trajectories gathered during the sweep."""

    if not result.examples:
        return

    import matplotlib.pyplot as plt

    n_examples = len(result.examples)
    rows = 2
    cols = (n_examples + 1) // 2
    fig, axes = plt.subplots(rows, cols, figsize=(6 * cols, 6), sharex=True)
    axes = np.atleast_1d(axes).ravel()

    for ax, example in zip(axes, result.examples):
        ax.plot(example["pi_avg"], label=r"$\pi_{avg}$", color="tab:blue")
        ax.plot(example["S_avg"], label=r"$S_{avg}$", color="tab:red")
        ax.axhline(example["target"], linestyle="--", color="black", alpha=0.6, label="Target S")
        ax.set_title(f"eta={example['eta']}, target={example['target']}")
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize="small")

    for ax in axes[n_examples:]:
        ax.axis("off")

    fig.suptitle(f"Representative trajectories (mu={result.mu})")
    plt.tight_layout()
    plt.show()


def plot_phase_diagram(result: SweepResult) -> None:
    """Render heatmaps for the mean coupling and oscillation metrics."""

    import matplotlib.pyplot as plt

    etas = result.etas
    targets = result.targets

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    im1 = ax1.imshow(result.mean_pi, origin="lower", cmap="viridis", aspect="auto")
    ax1.set_xticks(range(len(targets)))
    ax1.set_yticks(range(len(etas)))
    ax1.set_xticklabels(targets)
    ax1.set_yticklabels(etas)
    ax1.set_xlabel(r"Entanglement target ($S_{target}$)")
    ax1.set_ylabel(r"Learning rate ($\eta$)")
    ax1.set_title(r"Final coupling strength $\pi_{avg}$")
    plt.colorbar(im1, ax=ax1, label=r"$\pi$")

    im2 = ax2.imshow(result.mean_std, origin="lower", cmap="magma", aspect="auto")
    ax2.set_xticks(range(len(targets)))
    ax2.set_yticks(range(len(etas)))
    ax2.set_xticklabels(targets)
    ax2.set_yticklabels(etas)
    ax2.set_xlabel(r"Entanglement target ($S_{target}$)")
    ax2.set_ylabel(r"Learning rate ($\eta$)")
    ax2.set_title("Spatial variance / instability")
    plt.colorbar(im2, ax=ax2, label=r"Std of $\pi$")

    plt.tight_layout()
    plt.show()


def run_goldilocks_sweep(params: GoldilocksParams) -> Tuple[np.ndarray, np.ndarray]:
    """Evaluate connectivity/stability over a Goldilocks parameter grid."""

    etas = params.etas
    targets = params.targets
    connectivity = np.zeros((len(etas), len(targets)))
    stability = np.zeros_like(connectivity)

    for i, eta in enumerate(etas):
        for j, target in enumerate(targets):
            universe = QuantumGravityUniverse(
                n_qubits=params.n_qubits,
                dt=params.dt,
                pi_0=params.pi_rest,
                min_pi=0.0,
            )
            pi_history: List[float] = []
            for _ in range(params.steps):
                universe.step(eta=eta, mu=params.mu, entropy_target=target)
                avg_pi = float(np.mean(list(universe.pi_a.values())))
                pi_history.append(avg_pi)

            tail = pi_history[-params.burn_in :] if params.burn_in < len(pi_history) else pi_history
            connectivity[i, j] = float(np.mean(tail))
            stability[i, j] = float(np.std(tail))

    return connectivity, stability


def plot_goldilocks_maps(
    connectivity: np.ndarray,
    stability: np.ndarray,
    etas: Tuple[float, ...],
    targets: Tuple[float, ...],
) -> None:
    """Plot heatmaps for the Goldilocks connectivity/stability metrics."""

    try:
        import matplotlib.pyplot as plt
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Goldilocks plotting requires matplotlib") from exc

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    im1 = ax1.imshow(connectivity, origin="lower", cmap="viridis", aspect="auto")
    ax1.set_title(r"Connectivity ($\pi_{avg}$)")
    ax1.set_xlabel(r"$S_{target}$")
    ax1.set_ylabel(r"$\eta$")
    ax1.set_xticks(range(len(targets)))
    ax1.set_xticklabels(targets)
    ax1.set_yticks(range(len(etas)))
    ax1.set_yticklabels(etas)
    plt.colorbar(im1, ax=ax1)

    im2 = ax2.imshow(stability, origin="lower", cmap="magma", aspect="auto")
    ax2.set_title(r"Instability / Foam ($\sigma_{\pi}$)")
    ax2.set_xlabel(r"$S_{target}$")
    ax2.set_xticks(range(len(targets)))
    ax2.set_xticklabels(targets)
    ax2.set_yticks([])
    plt.colorbar(im2, ax=ax2)

    plt.tight_layout()
    plt.show()


def compute_mutual_information_matrix(universe: QuantumGravityUniverse) -> np.ndarray:
    """Compute pairwise mutual information using the universe's state."""

    n = universe.n
    single_entropies = []
    for idx in range(n):
        rho_i = reduced_density_matrix(universe.psi, n, [idx])
        single_entropies.append(von_neumann_entropy(rho_i))

    mi = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i == j:
                mi[i, j] = 2.0 * single_entropies[i]
                continue
            rho_ij = reduced_density_matrix(universe.psi, n, [i, j])
            s_pair = von_neumann_entropy(rho_ij)
            val = single_entropies[i] + single_entropies[j] - s_pair
            mi[i, j] = max(0.0, val)
    return mi


def compute_geometric_distance_matrix(
    universe: QuantumGravityUniverse,
    mi_matrix: np.ndarray | None = None,
    metric: str = "pi",
    eps: float = 1e-3,
) -> np.ndarray:
    """Estimate distances either from 1/pi or epsilon-floored MI."""

    n = universe.n
    if metric == "mi-log":
        if mi_matrix is None:
            raise ValueError("mi_matrix required for mi-log metric")
        dist = -np.log(mi_matrix + eps)
        np.fill_diagonal(dist, 0.0)
        return dist

    if metric != "pi":
        raise ValueError(f"Unsupported distance metric: {metric}")

    dist = np.zeros((n, n))
    weights: Dict[Tuple[int, int], float] = {}
    for edge, coupling in universe.pi_a.items():
        weight = float("inf") if coupling <= 0.0 else 1.0 / coupling
        weights[edge] = weight
        weights[(edge[1], edge[0])] = weight

    for i in range(n):
        for j in range(i + 1, n):
            total = 0.0
            for k in range(i, j):
                total += weights.get((k, k + 1), float("inf"))
            dist[i, j] = dist[j, i] = total
    return dist


def compute_info_geodesic(mi_matrix: np.ndarray, eps: float = 1e-4) -> np.ndarray:
    """Compute path-length distances using 1/(MI + eps) along the chain."""

    n = mi_matrix.shape[0]
    dist = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            total = 0.0
            for k in range(i, j):
                total += 1.0 / (mi_matrix[k, k + 1] + eps)
            dist[i, j] = dist[j, i] = total
    return dist


def plot_stage_two_heatmaps(
    mi: np.ndarray,
    distances: np.ndarray,
    info_distance: np.ndarray | None = None,
) -> None:
    """Plot mutual information and geometric distance matrices side-by-side."""

    try:
        plt = importlib.import_module("matplotlib.pyplot")
        sns = importlib.import_module("seaborn")
    except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Stage-two plotting requires matplotlib and seaborn") from exc

    n_cols = 3 if info_distance is not None else 2
    fig, axes = plt.subplots(1, n_cols, figsize=(6 * n_cols, 5))
    ax_geo = axes[0]
    sns.heatmap(distances, ax=ax_geo, cmap="viridis_r", annot=True, fmt=".2f")
    ax_geo.set_title(r"Emergent geometry")
    ax_geo.set_xlabel("Qubit index")
    ax_geo.set_ylabel("Qubit index")

    if info_distance is not None:
        ax_info = axes[1]
        sns.heatmap(info_distance, ax=ax_info, cmap="coolwarm", annot=True, fmt=".2f")
        ax_info.set_title(r"Entanglement geodesic")
        ax_info.set_xlabel("Qubit index")
        ax_info.set_ylabel("Qubit index")
        ax_mi = axes[2]
    else:
        ax_mi = axes[1]

    sns.heatmap(mi, ax=ax_mi, cmap="magma", annot=True, fmt=".2f")
    ax_mi.set_title(r"Mutual information $I(A:B)$")
    ax_mi.set_xlabel("Qubit index")
    ax_mi.set_ylabel("Qubit index")

    plt.tight_layout()
    plt.show()


def run_stage_two_analysis(
    params: StageTwoParams,
    plot: bool = False,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run the stage-two burn-in and return MI/geometry matrices."""

    universe = QuantumGravityUniverse(
        n_qubits=params.n_qubits,
        dt=params.dt,
        pi_0=params.pi_rest,
        min_pi=params.min_pi,
    )
    for _ in range(params.steps):
        universe.step(eta=params.eta, mu=params.mu, entropy_target=params.entropy_target)

    mi_matrix = compute_mutual_information_matrix(universe)
    geo_matrix = compute_geometric_distance_matrix(
        universe,
        mi_matrix=mi_matrix,
        metric=params.distance_metric,
        eps=params.distance_eps,
    )
    info_distance = compute_info_geodesic(mi_matrix, eps=params.info_eps)

    if plot:
        plot_stage_two_heatmaps(mi_matrix, geo_matrix, info_distance)

    return mi_matrix, geo_matrix, info_distance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("gate", "hamiltonian"), default="gate", help="pick the evolution style")
    parser.add_argument("--phase-sweep", action="store_true", help="run the Hamiltonian phase-diagram sweep and exit")
    parser.add_argument("--goldilocks-sweep", action="store_true", help="run the connectivity/stability sweep and exit")
    parser.add_argument("--stage-two", action="store_true", help="run the stage-two mutual-information analysis and exit")
    parser.add_argument("--steps", type=int, default=200, help="number of simulation steps (gate/hamiltonian modes)")
    parser.add_argument("--n-qubits", type=int, default=6, help="size of qubit chain")
    parser.add_argument("--entropy-target", type=float, default=0.4, help="target von Neumann entropy")
    parser.add_argument("--eta", type=float, default=0.3, help="curvature adaptation rate")
    parser.add_argument("--lambda", dest="lam", type=float, default=0.8, help="gate-angle coupling strength (gate mode)")
    parser.add_argument("--theta-gain", type=float, default=0.2, help="feedback gain for theta updates (gate mode)")
    parser.add_argument("--dt", type=float, default=0.1, help="time increment for updates")
    parser.add_argument("--initial-pi", type=float, default=0.2, help="initial coupling used in Hamiltonian experiments")
    parser.add_argument("--plot-history", action="store_true", help="plot entropy and pi_a histories (Hamiltonian mode)")
    parser.add_argument("--plot-stage-two", action="store_true", help="plot mutual-information vs geometry heatmaps")
    parser.add_argument("--plot-goldilocks", action="store_true", help="plot the Goldilocks connectivity/stability maps")

    sweep_group = parser.add_argument_group("phase sweep")
    sweep_group.add_argument("--sweep-etas", type=float, nargs="+", default=(0.1, 0.5, 1.0, 2.0), help="eta values sampled during phase sweep")
    sweep_group.add_argument("--sweep-targets", type=float, nargs="+", default=(0.1, 0.3, 0.5, 0.7), help="entropy targets sampled during sweep")
    sweep_group.add_argument("--sweep-steps", type=int, default=150, help="simulation steps per sweep cell")
    sweep_group.add_argument("--sweep-mu", type=float, default=0.1, help="relaxation/leak term used in sweep")
    sweep_group.add_argument("--plot-sweep-trajectories", action="store_true", help="plot representative pi/S trajectories from the sweep")
    sweep_group.add_argument("--plot-phase-diagram", action="store_true", help="plot heatmaps summarizing the sweep")

    stage2_group = parser.add_argument_group("stage two analysis")
    stage2_group.add_argument("--stage2-eta", type=float, default=0.5, help="eta used during stage-two burn-in")
    stage2_group.add_argument("--stage2-target", type=float, default=0.65, help="entropy target for stage-two run")
    stage2_group.add_argument("--stage2-mu", type=float, default=0.05, help="relaxation term mu for stage-two run")
    stage2_group.add_argument("--stage2-steps", type=int, default=300, help="number of burn-in steps for stage-two run")
    stage2_group.add_argument("--stage2-pi0", type=float, default=1.0, help="rest coupling pi_0 for stage-two run")
    stage2_group.add_argument("--stage2-min-pi", type=float, default=0.0, help="minimum coupling enforced during stage-two run")
    stage2_group.add_argument(
        "--stage2-distance-metric",
        choices=("pi", "mi-log"),
        default="mi-log",
        help="distance estimator used for stage-two geometry",
    )
    stage2_group.add_argument("--stage2-distance-eps", type=float, default=1e-3, help="epsilon used in MI-based distance")
    stage2_group.add_argument("--stage2-info-eps", type=float, default=1e-4, help="epsilon used in entanglement geodesic distances")
    stage2_group.add_argument("--stage2-export-prefix", type=str, default="", help="optional prefix for exporting stage-two CSV matrices")

    gold_group = parser.add_argument_group("goldilocks sweep")
    gold_group.add_argument("--gold-etas", type=float, nargs="+", default=(0.05, 0.2, 0.5, 1.0, 2.5), help="eta axis for Goldilocks sweep")
    gold_group.add_argument("--gold-targets", type=float, nargs="+", default=(0.05, 0.2, 0.45, 0.6, 0.8), help="entropy targets for Goldilocks sweep")
    gold_group.add_argument("--gold-steps", type=int, default=200, help="steps per Goldilocks cell")
    gold_group.add_argument("--gold-burn", type=int, default=50, help="number of terminal steps used for averaging")
    gold_group.add_argument("--gold-mu", type=float, default=0.01, help="relaxation term for Goldilocks sweep")
    args = parser.parse_args()

    if args.phase_sweep:
        sweep_params = SweepParams(
            n_qubits=args.n_qubits,
            steps=args.sweep_steps,
            dt=args.dt,
            mu=args.sweep_mu,
            etas=tuple(args.sweep_etas),
            targets=tuple(args.sweep_targets),
            pi_rest=args.initial_pi,
            min_pi=args.stage2_min_pi,
        )
        sweep_result = run_parameter_sweep(sweep_params)
        print("Phase sweep complete. Mean pi matrix:")
        print(sweep_result.mean_pi)
        print("Mean std-dev matrix:")
        print(sweep_result.mean_std)
        if args.plot_sweep_trajectories:
            plot_representative_trajectories(sweep_result)
        if args.plot_phase_diagram:
            plot_phase_diagram(sweep_result)
        return

    if args.goldilocks_sweep:
        gold_params = GoldilocksParams(
            etas=tuple(args.gold_etas),
            targets=tuple(args.gold_targets),
            steps=args.gold_steps,
            burn_in=args.gold_burn,
            mu=args.gold_mu,
            n_qubits=args.n_qubits,
            dt=args.dt,
            pi_rest=args.initial_pi,
        )
        connectivity, stability = run_goldilocks_sweep(gold_params)
        print("Goldilocks connectivity map (pi_avg):")
        print(connectivity)
        print("Goldilocks stability map (sigma_pi):")
        print(stability)
        if args.plot_goldilocks:
            plot_goldilocks_maps(connectivity, stability, gold_params.etas, gold_params.targets)
        return

    if args.stage_two:
        stage_params = StageTwoParams(
            n_qubits=args.n_qubits,
            steps=args.stage2_steps,
            dt=args.dt,
            eta=args.stage2_eta,
            mu=args.stage2_mu,
            entropy_target=args.stage2_target,
            pi_rest=args.stage2_pi0,
            min_pi=args.stage2_min_pi,
            distance_metric=args.stage2_distance_metric,
            distance_eps=args.stage2_distance_eps,
            info_eps=args.stage2_info_eps,
        )
        mi_matrix, geo_matrix, info_distance = run_stage_two_analysis(
            stage_params, plot=args.plot_stage_two
        )
        print("Mutual information matrix:")
        print(mi_matrix)
        print("Geometric distance matrix:")
        print(geo_matrix)
        print("Entanglement geodesic distance matrix:")
        print(info_distance)
        if args.stage2_export_prefix:
            export_prefix = Path(args.stage2_export_prefix)
            export_dir = export_prefix.parent if export_prefix.parent != Path("") else Path(".")
            export_dir.mkdir(parents=True, exist_ok=True)
            base_name = export_prefix.stem if export_prefix.suffix else export_prefix.name
            if not base_name:
                base_name = "stage2"
            def _save(matrix: np.ndarray, suffix: str) -> None:
                path = export_dir / f"{base_name}_{suffix}.csv"
                np.savetxt(path, matrix, delimiter=",", fmt="%.6f")

            _save(mi_matrix, "mi")
            _save(geo_matrix, "geo")
            _save(info_distance, "info")
        return

    if args.mode == "gate":
        params = SimulationParams(
            n_qubits=args.n_qubits,
            steps=args.steps,
            dt=args.dt,
            lam=args.lam,
            eta=args.eta,
            theta_gain=args.theta_gain,
            entropy_target=args.entropy_target,
        )
        entropies, pi_a = run_simulation(params)
    else:
        params = HamiltonianParams(
            n_qubits=args.n_qubits,
            steps=args.steps,
            dt=args.dt,
            eta=args.eta,
            entropy_target=args.entropy_target,
            initial_pi=args.initial_pi,
        )
        history_s, history_pi = run_hamiltonian_simulation(params, plot_history=args.plot_history)
        entropies = {edge: values[-1] for edge, values in history_s.items()}
        pi_a = {edge: values[-1] for edge, values in history_pi.items()}

    print("Final edge entropies and curvatures:")
    for edge in sorted(entropies):
        print(f"{edge}: S={entropies[edge]:.3f}, pi_a={pi_a[edge]:.3f}")


if __name__ == "__main__":
    main()
