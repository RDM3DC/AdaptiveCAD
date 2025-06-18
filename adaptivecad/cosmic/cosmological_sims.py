"""Cosmological Simulation Module for AdaptiveCAD.

Provides tools for simulating and visualizing cosmic-scale phenomena including
universe expansion, structure formation, and large-scale cosmic web dynamics.
"""

import numpy as np
import math
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

try:
    from adaptivecad.ndfield import NDField
    from adaptivecad.spacetime import Event
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False


class CosmologicalModel(Enum):
    """Standard cosmological models."""
    LAMBDA_CDM = "lambda_cdm"
    OPEN_UNIVERSE = "open"
    CLOSED_UNIVERSE = "closed"
    DE_SITTER = "de_sitter"
    ANTI_DE_SITTER = "anti_de_sitter"


@dataclass
class CosmologicalParameters:
    """Parameters defining a cosmological model."""
    
    # Hubble constant (km/s/Mpc)
    H0: float = 70.0
    
    # Density parameters (Ω)
    omega_matter: float = 0.31
    omega_lambda: float = 0.69
    omega_radiation: float = 0.0001
    omega_k: float = 0.0  # Curvature parameter
    
    # Other parameters
    age_universe: float = 13.8e9  # years
    temp_cmb: float = 2.725  # Kelvin
    
    def __post_init__(self):
        """Validate cosmological parameters."""
        total_omega = self.omega_matter + self.omega_lambda + self.omega_radiation + abs(self.omega_k)
        if abs(total_omega - 1.0) > 1e-3:
            print(f"Warning: Total Ω = {total_omega:.4f} (should be ~1.0)")


class UniverseExpansionSimulator:
    """Simulate universe expansion and scale factor evolution."""
    
    def __init__(self, cosmo_params: CosmologicalParameters):
        self.params = cosmo_params
        
    def scale_factor(self, time: float, t0: float = None) -> float:
        """Calculate scale factor a(t) as function of cosmic time."""
        if t0 is None:
            t0 = self.params.age_universe
            
        # Simplified for matter-dominated era
        if time <= 0:
            return 0.0
            
        # For matter-dominated universe: a(t) ∝ t^(2/3)
        if self.params.omega_matter > 0.5:
            return (time / t0) ** (2/3)
        
        # For lambda-dominated universe: exponential expansion
        elif self.params.omega_lambda > 0.5:
            H0_per_year = self.params.H0 / (9.78e11)  # Convert to 1/year
            return math.exp(H0_per_year * math.sqrt(self.params.omega_lambda) * (time - t0))
        
        # Radiation-dominated: a(t) ∝ t^(1/2)
        else:
            return (time / t0) ** 0.5
    
    def hubble_parameter(self, redshift: float) -> float:
        """Calculate Hubble parameter H(z) at given redshift."""
        z = redshift
        H_z_squared = (self.params.H0 ** 2) * (
            self.params.omega_matter * (1 + z) ** 3 +
            self.params.omega_radiation * (1 + z) ** 4 +
            self.params.omega_k * (1 + z) ** 2 +
            self.params.omega_lambda
        )
        return math.sqrt(H_z_squared)
    
    def comoving_distance(self, redshift: float, steps: int = 1000) -> float:
        """Calculate comoving distance to object at given redshift."""
        z_vals = np.linspace(0, redshift, steps)
        dz = redshift / steps
        
        # Integrate 1/H(z) dz
        integral = 0.0
        for z in z_vals:
            H_z = self.hubble_parameter(z)
            integral += 1.0 / H_z * dz
            
        c = 2.998e5  # km/s
        return c * integral  # Mpc
    
    def generate_expansion_history(self, time_range: Tuple[float, float],
                                 steps: int = 100) -> Tuple[List[float], List[float]]:
        """Generate scale factor evolution over cosmic time."""
        t_start, t_end = time_range
        times = np.linspace(t_start, t_end, steps)
        scale_factors = [self.scale_factor(t) for t in times]
        
        return list(times), scale_factors


class StructureFormationSimulator:
    """Simulate cosmic structure formation and dark matter evolution."""
    
    def __init__(self, box_size: float = 100.0, n_particles: int = 64**3):
        self.box_size = box_size  # Mpc/h
        self.n_particles = n_particles
        self.grid_size = int(round(n_particles ** (1/3)))
        
    def generate_initial_conditions(self, redshift_initial: float = 1000.0) -> NDField:
        """Generate initial density field from primordial fluctuations."""
        # Create 3D grid
        grid_shape = (self.grid_size, self.grid_size, self.grid_size)
        
        # Generate Gaussian random field for density fluctuations
        # In reality would use power spectrum P(k) ∝ k^n with n ≈ 1
        density_field = np.random.normal(1.0, 0.01, grid_shape)  # Small fluctuations around mean
        
        # Apply power spectrum filtering (simplified)
        # Real implementation would use proper cosmological power spectrum
        k_vals = np.fft.fftfreq(self.grid_size, d=self.box_size/self.grid_size)
        kx, ky, kz = np.meshgrid(k_vals, k_vals, k_vals, indexing='ij')
        k_mag = np.sqrt(kx**2 + ky**2 + kz**2)
        
        # Avoid division by zero
        k_mag[k_mag == 0] = 1e-10
        
        # Simple power law: P(k) ∝ k^(-1) (Harrison-Zeldovich spectrum)
        power_spectrum = 1.0 / k_mag
        
        # Apply in Fourier space
        density_fft = np.fft.fftn(density_field)
        density_fft *= np.sqrt(power_spectrum)
        density_field = np.fft.ifftn(density_fft).real
        
        # Normalize to have mean density = 1
        density_field = density_field / np.mean(density_field)
        
        return NDField(grid_shape, density_field.flatten())
    
    def evolve_density_field(self, initial_field: NDField, 
                           redshift_final: float = 0.0,
                           time_steps: int = 50) -> List[NDField]:
        """Evolve density field using simplified N-body dynamics."""
        evolution = [initial_field]
        
        # Simple linear growth approximation
        # Real N-body would solve Poisson equation and particle dynamics
        growth_factor_initial = self._linear_growth_factor(1000.0)  # z=1000
        growth_factor_final = self._linear_growth_factor(redshift_final)
        
        growth_ratio = growth_factor_final / growth_factor_initial
        
        for step in range(1, time_steps + 1):
            # Linear interpolation of growth
            current_growth = growth_factor_initial + (growth_ratio - 1) * step / time_steps
            
            # Apply growth to density field
            current_density = initial_field.values.reshape(initial_field.grid_shape)
            evolved_density = 1.0 + current_growth * (current_density - 1.0)
            
            # Apply some nonlinear effects (very simplified)
            # Real code would use proper N-body or perturbation theory
            evolved_density = np.where(evolved_density > 1.5, 
                                     evolved_density**1.5, evolved_density)
            
            evolution.append(NDField(initial_field.grid_shape, evolved_density.flatten()))
            
        return evolution
    
    def _linear_growth_factor(self, redshift: float) -> float:
        """Calculate linear growth factor D(z) for structure formation."""
        # Simplified for matter-dominated universe
        # Real implementation would integrate growth equation
        z = redshift
        return 1.0 / (1.0 + z)  # Very simplified
    
    def identify_halos(self, density_field: NDField, threshold: float = 1.5) -> List[Dict]:
        """Identify dark matter halos using friends-of-friends algorithm."""
        density = density_field.values.reshape(density_field.grid_shape)
        
        # Find overdense regions
        overdense_mask = density > threshold
        
        # Simple connected component analysis (simplified FoF)
        from scipy import ndimage
        labeled_array, num_features = ndimage.label(overdense_mask)
        
        halos = []
        for label in range(1, num_features + 1):
            halo_mask = labeled_array == label
            halo_indices = np.where(halo_mask)
            
            if len(halo_indices[0]) > 10:  # Minimum halo size
                # Calculate halo properties
                center_x = np.mean(halo_indices[0]) * self.box_size / self.grid_size
                center_y = np.mean(halo_indices[1]) * self.box_size / self.grid_size
                center_z = np.mean(halo_indices[2]) * self.box_size / self.grid_size
                
                mass = np.sum(density[halo_mask])  # Proportional to mass
                
                halos.append({
                    'center': (center_x, center_y, center_z),
                    'mass': mass,
                    'num_particles': len(halo_indices[0])
                })
                
        return halos


class CMBVisualizer:
    """Visualize Cosmic Microwave Background anisotropies."""
    
    def __init__(self, map_resolution: int = 256):
        self.resolution = map_resolution
        
    def generate_cmb_map(self, l_max: int = 100) -> NDField:
        """Generate synthetic CMB temperature map."""
        # Create spherical grid (simplified to 2D for now)
        theta_vals = np.linspace(0, np.pi, self.resolution)
        phi_vals = np.linspace(0, 2*np.pi, self.resolution)
        
        temperature_map = np.zeros((self.resolution, self.resolution))
        
        # Add spherical harmonic modes (simplified)
        for l in range(2, min(l_max, 20)):  # Limit for computation
            for m in range(-l, l+1):
                # Random amplitude (would use actual CMB power spectrum)
                amplitude = np.random.normal(0, 1.0/l**2)
                
                for i, theta in enumerate(theta_vals):
                    for j, phi in enumerate(phi_vals):
                        # Simplified spherical harmonic
                        Y_lm = self._simple_spherical_harmonic(l, m, theta, phi)
                        temperature_map[i, j] += amplitude * Y_lm.real
        
        # Add mean temperature
        temperature_map += 2.725  # Kelvin
        
        return NDField((self.resolution, self.resolution), temperature_map.flatten())
    
    def _simple_spherical_harmonic(self, l: int, m: int, theta: float, phi: float) -> complex:
        """Simplified spherical harmonics for CMB."""
        # Very basic implementation
        if l == 2 and m == 0:
            return (5/(16*np.pi))**0.5 * (3*np.cos(theta)**2 - 1)
        elif l == 2 and abs(m) == 1:
            sign = -1 if m < 0 else 1
            return sign * (15/(8*np.pi))**0.5 * np.sin(theta) * np.cos(theta) * np.exp(1j*m*phi)
        else:
            # Generic fallback
            return np.cos(l*theta) * np.exp(1j*m*phi)


# Integration with AdaptiveCAD
class CosmologicalSimulationCmd:
    """Command to add cosmological simulation tools to AdaptiveCAD."""
    
    def __init__(self):
        self.name = "Cosmological Simulation"
        
    def run(self, mw):
        """Add cosmological simulation to the main window."""
        if not HAS_DEPENDENCIES:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(mw.win, "Missing Dependencies", 
                              "Cosmological simulation dependencies not available.")
            return
            
        try:
            # Create cosmological parameters (ΛCDM model)
            cosmo_params = CosmologicalParameters()
            
            # Create universe expansion simulator
            expansion_sim = UniverseExpansionSimulator(cosmo_params)
            
            # Generate expansion history
            times, scale_factors = expansion_sim.generate_expansion_history(
                (1e6, 13.8e9), steps=100  # 1 Myr to present
            )
            
            # Create structure formation simulator
            structure_sim = StructureFormationSimulator(box_size=50.0)  # 50 Mpc/h box
            
            # Generate initial conditions
            initial_density = structure_sim.generate_initial_conditions(redshift_initial=100.0)
            
            # Evolve structure (just first few steps for demo)
            evolution = structure_sim.evolve_density_field(initial_density, 
                                                         redshift_final=0.0, 
                                                         time_steps=5)
            
            # Find halos in final state
            final_halos = structure_sim.identify_halos(evolution[-1])
            
            # Create CMB map
            cmb_viz = CMBVisualizer(map_resolution=128)
            cmb_map = cmb_viz.generate_cmb_map(l_max=50)
            
            mw.win.statusBar().showMessage(
                f"Cosmological simulation ready: {len(final_halos)} halos found, "
                f"CMB map generated, expansion history computed", 5000
            )
            
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(mw.win, "Error", f"Cosmological simulation error: {str(e)}")
