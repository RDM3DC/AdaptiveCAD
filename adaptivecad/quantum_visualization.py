import numpy as np
import math
from typing import List, Tuple, Optional
from dataclasses import dataclass
from scipy.special import sph_harm, assoc_laguerre, hermite

try:
    from typing import Complex
except ImportError:  # Python <3.9
    Complex = complex

from .ndfield import NDField
from .spacetime import Event


@dataclass
class QuantumState:
    """Simple representation of a quantum state."""

    amplitudes: np.ndarray
    basis_labels: List[str]
    dimension: int

    def __post_init__(self) -> None:
        self.amplitudes = np.asarray(self.amplitudes, dtype=complex)
        if len(self.amplitudes) != self.dimension:
            raise ValueError("Amplitude array size must match dimension")

    def normalize(self) -> "QuantumState":
        norm = np.linalg.norm(self.amplitudes)
        amps = self.amplitudes if norm < 1e-10 else self.amplitudes / norm
        return QuantumState(amps, self.basis_labels, self.dimension)

    def probability(self, basis_index: int) -> float:
        return float(abs(self.amplitudes[basis_index]) ** 2)

    def expectation_value(self, operator: np.ndarray) -> complex:
        if operator.shape != (self.dimension, self.dimension):
            raise ValueError("Operator dimensions must match state space")
        psi_conj = np.conj(self.amplitudes)
        return np.dot(psi_conj, np.dot(operator, self.amplitudes))


class WavefunctionVisualizer:
    """Utilities for creating quantum wavefunctions on a grid."""

    def __init__(self, grid_size: Tuple[int, int, int] = (50, 50, 50)) -> None:
        self.grid_size = grid_size
        self.x_range = (-5.0, 5.0)
        self.y_range = (-5.0, 5.0)
        self.z_range = (-5.0, 5.0)

    def hydrogen_wavefunction(self, n: int, l: int, m: int) -> NDField:
        if not (0 <= l < n and -l <= m <= l):
            raise ValueError("Invalid quantum numbers: must have 0 \u2264 l < n and -l \u2264 m \u2264 l")

        nx, ny, nz = self.grid_size
        x_vals = np.linspace(*self.x_range, nx)
        y_vals = np.linspace(*self.y_range, ny)
        z_vals = np.linspace(*self.z_range, nz)
        x, y, z = np.meshgrid(x_vals, y_vals, z_vals, indexing="ij")
        r = np.sqrt(x ** 2 + y ** 2 + z ** 2)
        theta = np.arccos(np.divide(z, r, out=np.zeros_like(z), where=r > 1e-10))
        phi = np.arctan2(y, x)

        radial = self._radial_function(n, l, r)
        angular = sph_harm(m, l, phi, theta)
        psi = radial * angular
        return NDField(self.grid_size, psi.flatten())

    def _radial_function(self, n: int, l: int, r: np.ndarray) -> np.ndarray:
        a0 = 1.0
        rho = 2 * r / (n * a0)
        pref = math.sqrt((2 / (n * a0)) ** 3 * math.factorial(n - l - 1) / (2 * n * math.factorial(n + l)))
        lag = assoc_laguerre(rho, n - l - 1, 2 * l + 1)
        return pref * rho ** l * np.exp(-rho / 2) * lag

    def quantum_harmonic_oscillator(self, n: int, omega: float = 1.0) -> NDField:
        if n < 0:
            raise ValueError("Quantum number n must be non-negative")
        nx = ny = nz = n // 3
        remainder = n % 3
        nx += remainder

        gx = np.linspace(*self.x_range, self.grid_size[0])
        gy = np.linspace(*self.y_range, self.grid_size[1])
        gz = np.linspace(*self.z_range, self.grid_size[2])
        psi_x = self._harmonic_oscillator_1d(nx, gx, omega)
        psi_y = self._harmonic_oscillator_1d(ny, gy, omega)
        psi_z = self._harmonic_oscillator_1d(nz, gz, omega)
        psi = psi_x[:, None, None] * psi_y[None, :, None] * psi_z[None, None, :]
        return NDField(self.grid_size, psi.flatten())

    def _harmonic_oscillator_1d(self, n: int, x: np.ndarray, omega: float) -> np.ndarray:
        norm = (omega / np.pi) ** 0.25 / math.sqrt(2 ** n * math.factorial(n))
        xi = np.sqrt(omega) * x
        Hn = hermite(n)(xi)
        return norm * Hn * np.exp(-xi ** 2 / 2)


class EntanglementVisualizer:
    """Tools for simple entanglement visualizations."""

    def create_bell_state(self, state_type: str = "phi_plus") -> QuantumState:
        if state_type == "phi_plus":
            amps = [1 / math.sqrt(2), 0, 0, 1 / math.sqrt(2)]
        elif state_type == "phi_minus":
            amps = [1 / math.sqrt(2), 0, 0, -1 / math.sqrt(2)]
        elif state_type == "psi_plus":
            amps = [0, 1 / math.sqrt(2), 1 / math.sqrt(2), 0]
        elif state_type == "psi_minus":
            amps = [0, 1 / math.sqrt(2), -1 / math.sqrt(2), 0]
        else:
            raise ValueError("Unknown Bell state type")
        labels = ["|00\u27e9", "|01\u27e9", "|10\u27e9", "|11\u27e9"]
        return QuantumState(np.array(amps, dtype=complex), labels, 4)

    def calculate_entanglement_entropy(self, state: QuantumState) -> float:
        if state.dimension != 4:
            raise ValueError("Currently only supports two-qubit systems")
        rho = np.outer(state.amplitudes, np.conj(state.amplitudes))
        rho_A = np.zeros((2, 2), dtype=complex)
        rho_A[0, 0] = rho[0, 0] + rho[1, 1]
        rho_A[0, 1] = rho[0, 2] + rho[1, 3]
        rho_A[1, 0] = rho[2, 0] + rho[3, 1]
        rho_A[1, 1] = rho[2, 2] + rho[3, 3]
        eig = np.linalg.eigvals(rho_A)
        eig = eig[eig > 1e-10]
        return float((-eig * np.log2(eig)).sum().real)

    def visualize_bloch_sphere(self, qubit_state: np.ndarray) -> Tuple[float, float, float]:
        if len(qubit_state) != 2:
            raise ValueError("Input must be a two-level qubit state")
        rho = np.outer(qubit_state, np.conj(qubit_state))
        sigma_x = np.array([[0, 1], [1, 0]])
        sigma_y = np.array([[0, -1j], [1j, 0]])
        sigma_z = np.array([[1, 0], [0, -1]])
        x = np.trace(rho @ sigma_x).real
        y = np.trace(rho @ sigma_y).real
        z = np.trace(rho @ sigma_z).real
        return float(x), float(y), float(z)


class QuantumFieldVisualizer:
    """Create simple quantum field configurations."""

    def __init__(self, field_size: Tuple[int, int, int] = (30, 30, 30)) -> None:
        self.field_size = field_size

    def scalar_field_vacuum_fluctuations(self, field_strength: float = 1.0) -> NDField:
        nx, ny, nz = self.field_size
        real = np.random.normal(0, field_strength, (nx, ny, nz))
        imag = np.random.normal(0, field_strength, (nx, ny, nz))
        vals = real + 1j * imag
        return NDField(self.field_size, vals.flatten())

    def create_particle_excitation(
        self,
        center: Tuple[float, float, float],
        momentum: Tuple[float, float, float],
        mass: float = 1.0,
    ) -> NDField:
        nx, ny, nz = self.field_size
        x_range = np.linspace(-5, 5, nx)
        y_range = np.linspace(-5, 5, ny)
        z_range = np.linspace(-5, 5, nz)
        x, y, z = np.meshgrid(x_range, y_range, z_range, indexing="ij")
        cx, cy, cz = center
        px, py, pz = momentum
        r = np.sqrt((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2)
        phase = px * x + py * y + pz * z
        amp = np.exp(-r ** 2 / (2 * mass)) * np.exp(1j * phase)
        return NDField(self.field_size, amp.flatten())


class QuantumVisualizationCmd:
    """Simple command to initialize quantum tools in the UI."""

    def __init__(self) -> None:
        self.name = "Quantum Geometry Visualization"

    def run(self, mw: Any) -> None:
        try:
            wf_viz = WavefunctionVisualizer()
            ent_viz = EntanglementVisualizer()
            hydrogen = wf_viz.hydrogen_wavefunction(1, 0, 0)
            bell = ent_viz.create_bell_state("phi_plus")
            entropy = ent_viz.calculate_entanglement_entropy(bell)
            qf_viz = QuantumFieldVisualizer()
            _vac = qf_viz.scalar_field_vacuum_fluctuations()
            mw.win.statusBar().showMessage(
                f"Quantum visualization ready: Bell entropy = {entropy:.3f} bits",
                5000,
            )
        except Exception as exc:  # pragma: no cover - GUI feedback
            from PySide6.QtWidgets import QMessageBox

            QMessageBox.critical(mw.win, "Error", f"Quantum visualization error: {exc}")
