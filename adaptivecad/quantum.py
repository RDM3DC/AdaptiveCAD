from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from typing import NamedTuple, Optional, Tuple, List

import numpy as np

try:
    from scipy.special import sph_harm, assoc_laguerre
    SCIPY_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    SCIPY_AVAILABLE = False


def _fallback_spherical_harmonic(m: int, l: int, theta: np.ndarray, phi: np.ndarray) -> np.ndarray:
    """Simple fallback using numpy for low order harmonics if SciPy is missing."""
    if l == 0:
        return np.ones_like(theta) / math.sqrt(4 * math.pi)
    elif l == 1:
        if m == 0:
            return math.sqrt(3 / (4 * math.pi)) * np.cos(theta)
        elif m == 1:
            return -math.sqrt(3 / (8 * math.pi)) * np.sin(theta) * np.exp(1j * phi)
        elif m == -1:
            return math.sqrt(3 / (8 * math.pi)) * np.sin(theta) * np.exp(-1j * phi)
    raise ValueError("Fallback only supports l<=1")


def _fallback_assoc_laguerre(rho: np.ndarray, p: int, k: int) -> np.ndarray:
    """Return a simple polynomial approximation if SciPy is unavailable."""
    # Only implement small orders used in demos.
    if p == 0:
        return np.ones_like(rho)
    elif p == 1:
        return -rho + k + 1
    else:
        # crude approximation
        result = np.ones_like(rho)
        for i in range(p):
            result *= (-rho + k + 2 + i)
        return result


@dataclass
class QuantumConfig:
    GRID_SIZE: Tuple[int, int, int] = (50, 50, 50)
    X_RANGE: Tuple[float, float] = (-5.0, 5.0)
    Y_RANGE: Tuple[float, float] = (-5.0, 5.0)
    Z_RANGE: Tuple[float, float] = (-5.0, 5.0)
    BOHR_RADIUS: float = 1.0


def create_3d_grid(
    grid_size: Tuple[int, int, int],
    x_range: Tuple[float, float],
    y_range: Tuple[float, float],
    z_range: Tuple[float, float],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    nx, ny, nz = grid_size
    x_vals = np.linspace(*x_range, nx)
    y_vals = np.linspace(*y_range, ny)
    z_vals = np.linspace(*z_range, nz)
    return np.meshgrid(x_vals, y_vals, z_vals, indexing="ij")


class BlochCoordinates(NamedTuple):
    x: float
    y: float
    z: float


@dataclass
class QuantumState:
    amplitudes: np.ndarray
    basis_labels: Optional[List[str]] = None
    dimension: Optional[int] = None

    def __post_init__(self) -> None:
        self.amplitudes = np.asarray(self.amplitudes, dtype=complex)
        self.dimension = len(self.amplitudes) if self.dimension is None else self.dimension
        if len(self.amplitudes) != self.dimension:
            raise ValueError("Amplitude array size must match dimension")
        if self.basis_labels is None:
            self.basis_labels = [f"|{i}⟩" for i in range(self.dimension)]

    def normalize(self) -> "QuantumState":
        norm = np.linalg.norm(self.amplitudes)
        if norm == 0:
            raise ValueError("Cannot normalize a zero vector")
        self.amplitudes = self.amplitudes / norm
        return self


class WavefunctionVisualizer:
    def __init__(self, config: QuantumConfig | None = None) -> None:
        self.config = config or QuantumConfig()
        self.grid_size = self.config.GRID_SIZE
        self.x_range = self.config.X_RANGE
        self.y_range = self.config.Y_RANGE
        self.z_range = self.config.Z_RANGE

    def _radial_function(self, n: int, l: int, r: np.ndarray) -> np.ndarray:
        a0 = self.config.BOHR_RADIUS
        rho = 2 * r / (n * a0)
        if SCIPY_AVAILABLE:
            normalization = math.sqrt((2 / (n * a0))**3 * math.factorial(n - l - 1) / (2 * n * math.factorial(n + l)))
            laguerre = assoc_laguerre(rho, n - l - 1, 2 * l + 1)
            return normalization * rho**l * np.exp(-rho / 2) * laguerre
        # Fallback approximation
        normalization = (2 / (n * a0))**3
        laguerre = _fallback_assoc_laguerre(rho, n - l - 1, 2 * l + 1)
        return normalization * rho**l * np.exp(-rho / 2) * laguerre

    @lru_cache(maxsize=100)
    def _spherical_harmonic(self, l: int, m: int, theta: np.ndarray, phi: np.ndarray) -> np.ndarray:
        if SCIPY_AVAILABLE:
            return sph_harm(m, l, phi, theta)
        return _fallback_spherical_harmonic(m, l, theta, phi)

    def hydrogen_wavefunction(self, n: int, l: int, m: int) -> Tuple[Tuple[int, int, int], np.ndarray]:
        if not (n > 0 and 0 <= l < n and -l <= m <= l):
            raise ValueError(f"Invalid quantum numbers: n={n}, l={l}, m={m}")
        x, y, z = create_3d_grid(self.grid_size, self.x_range, self.y_range, self.z_range)
        r = np.sqrt(x**2 + y**2 + z**2)
        r = np.where(r < 1e-3 * self.config.BOHR_RADIUS, 1e-3 * self.config.BOHR_RADIUS, r)
        theta = np.arccos(z / r)
        phi = np.arctan2(y, x)
        radial_part = self._radial_function(n, l, r)
        angular_part = self._spherical_harmonic(l, m, theta, phi)
        wavefunction = radial_part * angular_part
        return self.grid_size, wavefunction


class EntanglementVisualizer:
    def create_bell_state(self, state_type: str = "phi_plus") -> QuantumState:
        mapping = {
            "phi_plus": np.array([1, 0, 0, 1], dtype=complex),
            "phi_minus": np.array([1, 0, 0, -1], dtype=complex),
            "psi_plus": np.array([0, 1, 1, 0], dtype=complex),
            "psi_minus": np.array([0, 1, -1, 0], dtype=complex),
        }
        if state_type not in mapping:
            raise ValueError(f"Unknown Bell state: {state_type}")
        state = QuantumState(mapping[state_type], ["|00⟩", "|01⟩", "|10⟩", "|11⟩"])
        return state.normalize()

    def calculate_entanglement_entropy(self, state: QuantumState, subsystem: List[int] | None = None) -> float:
        if state.dimension & (state.dimension - 1) != 0:
            raise ValueError("State dimension must be a power of 2")
        subsystem = subsystem or [0]
        rho = np.outer(state.amplitudes, np.conj(state.amplitudes))
        n_qubits = int(np.log2(state.dimension))
        rho_tensor = rho.reshape([2] * (2 * n_qubits))
        traced_qubits = [i for i in range(n_qubits) if i not in subsystem]
        for qubit in traced_qubits:
            rho_tensor = np.trace(rho_tensor, axis1=qubit, axis2=qubit + n_qubits)
        eigenvals = np.linalg.eigvals(rho_tensor)
        eigenvals = eigenvals.real[eigenvals.real > 1e-10]
        return float(-np.sum(eigenvals * np.log2(eigenvals)))
