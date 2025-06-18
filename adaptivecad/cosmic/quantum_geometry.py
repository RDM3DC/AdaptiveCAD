"""Quantum Geometry Visualization Module.

Provides tools for visualizing quantum states, wavefunctions, and entanglement
patterns within AdaptiveCAD's geometry framework.
"""

import numpy as np
import math
import cmath
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass

# Handle Python version compatibility for Complex type
try:
    from typing import Complex
except ImportError:
    # For older Python versions, use the standard complex type
    Complex = complex

try:
    from adaptivecad.ndfield import NDField
    from adaptivecad.spacetime import Event
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False


@dataclass
class QuantumState:
    """Represents a quantum state in Hilbert space."""
    
    amplitudes: np.ndarray  # Complex amplitudes
    basis_labels: List[str]  # Labels for basis states
    dimension: int
    
    def __post_init__(self):
        self.amplitudes = np.array(self.amplitudes, dtype=complex)
        if len(self.amplitudes) != self.dimension:
            raise ValueError("Amplitude array size must match dimension")
    
    def normalize(self) -> 'QuantumState':
        """Return normalized quantum state."""
        norm = np.linalg.norm(self.amplitudes)
        if norm > 1e-10:
            normalized_amps = self.amplitudes / norm
        else:
            normalized_amps = self.amplitudes
            
        return QuantumState(normalized_amps, self.basis_labels, self.dimension)    
    def probability(self, basis_index: int) -> float:
        """Get probability of measuring state in given basis."""
        return abs(self.amplitudes[basis_index]) ** 2
    
    def expectation_value(self, operator: np.ndarray) -> complex:
        """Calculate expectation value of an operator."""
        if operator.shape != (self.dimension, self.dimension):
            raise ValueError("Operator dimensions must match state space")
            
        psi_conj = np.conj(self.amplitudes)
        return np.dot(psi_conj, np.dot(operator, self.amplitudes))


class WavefunctionVisualizer:
    """Visualize quantum wavefunctions in 3D space."""
    
    def __init__(self, grid_size: Tuple[int, int, int] = (50, 50, 50)):
        self.grid_size = grid_size
        self.x_range = (-5, 5)
        self.y_range = (-5, 5)
        self.z_range = (-5, 5)
        
    def hydrogen_wavefunction(self, n: int, l: int, m: int) -> NDField:
        """Generate hydrogen atom wavefunction."""
        nx, ny, nz = self.grid_size
        x_vals = np.linspace(*self.x_range, nx)
        y_vals = np.linspace(*self.y_range, ny)
        z_vals = np.linspace(*self.z_range, nz)
        
        wavefunction = np.zeros((nx, ny, nz), dtype=complex)
        
        for i, x in enumerate(x_vals):
            for j, y in enumerate(y_vals):
                for k, z in enumerate(z_vals):
                    r = math.sqrt(x*x + y*y + z*z)
                    if r < 1e-10:  # Avoid singularity at origin
                        wavefunction[i, j, k] = 0
                        continue
                        
                    theta = math.acos(z / r) if r > 0 else 0
                    phi = math.atan2(y, x)
                    
                    # Simplified hydrogen wavefunction (for demonstration)
                    # Real implementation would use proper spherical harmonics
                    radial_part = self._radial_function(n, l, r)
                    angular_part = self._spherical_harmonic(l, m, theta, phi)
                    
                    wavefunction[i, j, k] = radial_part * angular_part
        
        # Convert to NDField for compatibility
        return NDField(self.grid_size, wavefunction.flatten())
    
    def _radial_function(self, n: int, l: int, r: float) -> float:
        """Simplified radial part of hydrogen wavefunction."""
        a0 = 1.0  # Bohr radius in atomic units
        rho = 2 * r / (n * a0)
        
        # Very simplified - real version would use associated Laguerre polynomials
        if n == 1 and l == 0:
            return 2 * (1/a0)**(3/2) * math.exp(-r/a0)
        elif n == 2 and l == 0:
            return (1/(2*math.sqrt(2))) * (1/a0)**(3/2) * (2 - r/a0) * math.exp(-r/(2*a0))
        else:
            # Generic exponential decay
            return math.exp(-r/(n*a0)) / math.sqrt(n**3)
    
    def _spherical_harmonic(self, l: int, m: int, theta: float, phi: float) -> complex:
        """Simplified spherical harmonics."""
        # Very basic implementation - real version would use proper Ylm
        if l == 0:
            return 1/math.sqrt(4*math.pi)
        elif l == 1:
            if m == -1:
                return math.sqrt(3/(8*math.pi)) * math.sin(theta) * cmath.exp(-1j*phi)
            elif m == 0:
                return math.sqrt(3/(4*math.pi)) * math.cos(theta)
            elif m == 1:
                return -math.sqrt(3/(8*math.pi)) * math.sin(theta) * cmath.exp(1j*phi)
        
        return 1.0  # Fallback
    
    def quantum_harmonic_oscillator(self, n: int, omega: float = 1.0) -> NDField:
        """Generate 1D quantum harmonic oscillator wavefunction extended to 3D."""
        nx, ny, nz = self.grid_size
        x_vals = np.linspace(*self.x_range, nx)
        
        wavefunction = np.zeros((nx, ny, nz), dtype=complex)
        
        # Hermite polynomial coefficients (simplified)
        def hermite_poly(n: int, x: float) -> float:
            if n == 0:
                return 1
            elif n == 1:
                return 2 * x
            elif n == 2:
                return 4 * x*x - 2
            elif n == 3:
                return 8 * x*x*x - 12 * x
            else:
                return 0  # Simplified
        
        for i, x in enumerate(x_vals):
            # 1D harmonic oscillator wavefunction
            normalization = (omega/math.pi)**(1/4) / math.sqrt(2**n * math.factorial(n))
            xi = math.sqrt(omega) * x
            psi_x = normalization * hermite_poly(n, xi) * math.exp(-xi*xi/2)
            
            # Extend to 3D by using same function in all directions
            for j in range(ny):
                for k in range(nz):
                    wavefunction[i, j, k] = psi_x
        
        return NDField(self.grid_size, wavefunction.flatten())


class EntanglementVisualizer:
    """Visualize quantum entanglement patterns and correlations."""
    
    def __init__(self):
        self.entangled_pairs = []
        
    def create_bell_state(self, state_type: str = "phi_plus") -> QuantumState:
        """Create Bell state for two-qubit entanglement."""
        if state_type == "phi_plus":
            # |Φ⁺⟩ = (|00⟩ + |11⟩)/√2
            amplitudes = [1/math.sqrt(2), 0, 0, 1/math.sqrt(2)]
        elif state_type == "phi_minus":
            # |Φ⁻⟩ = (|00⟩ - |11⟩)/√2
            amplitudes = [1/math.sqrt(2), 0, 0, -1/math.sqrt(2)]
        elif state_type == "psi_plus":
            # |Ψ⁺⟩ = (|01⟩ + |10⟩)/√2
            amplitudes = [0, 1/math.sqrt(2), 1/math.sqrt(2), 0]
        elif state_type == "psi_minus":
            # |Ψ⁻⟩ = (|01⟩ - |10⟩)/√2
            amplitudes = [0, 1/math.sqrt(2), -1/math.sqrt(2), 0]
        else:
            raise ValueError("Unknown Bell state type")
            
        basis_labels = ["|00⟩", "|01⟩", "|10⟩", "|11⟩"]
        return QuantumState(amplitudes, basis_labels, 4)
    
    def calculate_entanglement_entropy(self, state: QuantumState) -> float:
        """Calculate von Neumann entropy as measure of entanglement."""
        # For two-qubit system, reshape amplitudes to 2x2 density matrix
        if state.dimension != 4:
            raise ValueError("Currently only supports two-qubit systems")
            
        # Create density matrix
        rho = np.outer(state.amplitudes, np.conj(state.amplitudes))
        
        # Partial trace over second qubit to get reduced density matrix
        rho_A = np.zeros((2, 2), dtype=complex)
        rho_A[0, 0] = rho[0, 0] + rho[1, 1]  # |0⟩⟨0|
        rho_A[0, 1] = rho[0, 2] + rho[1, 3]  # |0⟩⟨1|
        rho_A[1, 0] = rho[2, 0] + rho[3, 1]  # |1⟩⟨0|
        rho_A[1, 1] = rho[2, 2] + rho[3, 3]  # |1⟩⟨1|
        
        # Calculate eigenvalues
        eigenvals = np.linalg.eigvals(rho_A)
        eigenvals = eigenvals[eigenvals > 1e-10]  # Remove near-zero eigenvalues
        
        # Von Neumann entropy
        entropy = -np.sum(eigenvals * np.log2(eigenvals))
        return float(entropy.real)
    
    def visualize_bloch_sphere(self, qubit_state: np.ndarray) -> Tuple[float, float, float]:
        """Convert qubit state to Bloch sphere coordinates."""
        if len(qubit_state) != 2:
            raise ValueError("Input must be a two-level qubit state")
            
        alpha, beta = qubit_state[0], qubit_state[1]
        
        # Pauli matrices
        sigma_x = np.array([[0, 1], [1, 0]])
        sigma_y = np.array([[0, -1j], [1j, 0]])
        sigma_z = np.array([[1, 0], [0, -1]])
        
        # Calculate expectation values
        rho = np.outer(qubit_state, np.conj(qubit_state))
        
        x = np.trace(np.dot(rho, sigma_x)).real
        y = np.trace(np.dot(rho, sigma_y)).real
        z = np.trace(np.dot(rho, sigma_z)).real
        
        return (float(x), float(y), float(z))


class QuantumFieldVisualizer:
    """Visualize quantum field configurations and excitations."""
    
    def __init__(self, field_size: Tuple[int, int, int] = (30, 30, 30)):
        self.field_size = field_size
        
    def scalar_field_vacuum_fluctuations(self, field_strength: float = 1.0) -> NDField:
        """Generate vacuum fluctuations of a scalar quantum field."""
        nx, ny, nz = self.field_size
        
        # Generate random field configuration representing vacuum fluctuations
        real_part = np.random.normal(0, field_strength, (nx, ny, nz))
        imag_part = np.random.normal(0, field_strength, (nx, ny, nz))
        
        field_values = real_part + 1j * imag_part
        
        return NDField(self.field_size, field_values.flatten())
    
    def create_particle_excitation(self, center: Tuple[float, float, float],
                                 momentum: Tuple[float, float, float],
                                 mass: float = 1.0) -> NDField:
        """Create a localized particle excitation in the quantum field."""
        nx, ny, nz = self.field_size
        x_range = np.linspace(-5, 5, nx)
        y_range = np.linspace(-5, 5, ny)
        z_range = np.linspace(-5, 5, nz)
        
        cx, cy, cz = center
        px, py, pz = momentum
        
        field_values = np.zeros((nx, ny, nz), dtype=complex)
        
        for i, x in enumerate(x_range):
            for j, y in enumerate(y_range):
                for k, z in enumerate(z_range):
                    # Distance from center
                    r = math.sqrt((x-cx)**2 + (y-cy)**2 + (z-cz)**2)
                    
                    # Wave packet with momentum
                    phase = px*x + py*y + pz*z
                    amplitude = math.exp(-r**2/(2*mass)) * cmath.exp(1j*phase)
                    
                    field_values[i, j, k] = amplitude
        
        return NDField(self.field_size, field_values.flatten())


# Integration with AdaptiveCAD
class QuantumVisualizationCmd:
    """Command to add quantum geometry visualization to AdaptiveCAD."""
    
    def __init__(self):
        self.name = "Quantum Geometry Visualization"
        
    def run(self, mw):
        """Add quantum visualization tools to the main window."""
        if not HAS_DEPENDENCIES:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(mw.win, "Missing Dependencies", 
                              "Quantum visualization dependencies not available.")
            return
            
        try:
            # Create quantum visualizers
            wf_viz = WavefunctionVisualizer()
            ent_viz = EntanglementVisualizer()
            
            # Generate a simple hydrogen wavefunction
            hydrogen_1s = wf_viz.hydrogen_wavefunction(1, 0, 0)
            
            # Create a Bell state
            bell_state = ent_viz.create_bell_state("phi_plus")
            entanglement = ent_viz.calculate_entanglement_entropy(bell_state)
            
            # Create quantum field
            qf_viz = QuantumFieldVisualizer()
            vacuum_field = qf_viz.scalar_field_vacuum_fluctuations()
            
            mw.win.statusBar().showMessage(
                f"Quantum visualization ready: H(1s) field generated, "
                f"Bell state entanglement = {entanglement:.3f} bits", 5000
            )
            
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(mw.win, "Error", f"Quantum visualization error: {str(e)}")
