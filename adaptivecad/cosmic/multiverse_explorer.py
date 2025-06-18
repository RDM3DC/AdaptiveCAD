"""Multiverse Hypothesis Exploration for AdaptiveCAD.

Interactive tools for exploring parameter variations in physical laws,
simulating hypothetical universes, and analyzing the landscape of possible
physical realities.
"""

import numpy as np
import math
from typing import List, Tuple, Optional, Dict, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import itertools

try:
    from adaptivecad.ndfield import NDField
    from adaptivecad.spacetime import Event
    HAS_DEPENDENCIES = True
except ImportError:
    HAS_DEPENDENCIES = False


class PhysicalConstant(Enum):
    """Fundamental physical constants that can be varied."""
    SPEED_OF_LIGHT = "c"
    PLANCK_CONSTANT = "h"
    GRAVITATIONAL_CONSTANT = "G"
    FINE_STRUCTURE_CONSTANT = "alpha"
    ELECTRON_MASS = "m_e"
    PROTON_MASS = "m_p"
    COSMOLOGICAL_CONSTANT = "Lambda"
    WEAK_COUPLING = "g_w"
    STRONG_COUPLING = "g_s"


@dataclass
class UniverseParameters:
    """Complete set of parameters defining a universe."""
    
    # Fundamental constants (in natural units where our universe = 1.0)
    c: float = 1.0              # Speed of light
    hbar: float = 1.0           # Reduced Planck constant
    G: float = 1.0              # Gravitational constant
    alpha: float = 1.0          # Fine structure constant (α ≈ 1/137)
    m_electron: float = 1.0     # Electron mass
    m_proton: float = 1.0       # Proton mass
    Lambda: float = 1.0         # Cosmological constant
    
    # Coupling constants
    g_weak: float = 1.0         # Weak nuclear coupling
    g_strong: float = 1.0       # Strong nuclear coupling
    
    # Spacetime properties
    spacetime_dimensions: int = 4
    signature: Tuple[int, int] = (1, 3)  # (time, space) dimensions
    
    # Initial conditions
    initial_entropy: float = 1.0
    initial_temperature: float = 1.0
    
    # Derived properties (calculated)
    stability_score: float = field(default=0.0, init=False)
    complexity_measure: float = field(default=0.0, init=False)
    habitability_index: float = field(default=0.0, init=False)


class UniverseSimulator:
    """Simulate the evolution and properties of hypothetical universes."""
    
    def __init__(self):
        self.reference_universe = UniverseParameters()  # Our universe as reference
        
    def simulate_universe_evolution(self, params: UniverseParameters,
                                  time_steps: int = 100) -> Dict[str, List[float]]:
        """Simulate basic evolution of a universe with given parameters."""
        
        evolution = {
            "time": [],
            "scale_factor": [],
            "temperature": [],
            "entropy": [],
            "complexity": []
        }
        
        # Initial conditions
        a_0 = 1.0  # Initial scale factor
        T_0 = params.initial_temperature
        S_0 = params.initial_entropy
        
        for step in range(time_steps):
            t = step / time_steps * 13.8e9  # 13.8 billion years
            
            # Scale factor evolution (depends on cosmological constant)
            if params.Lambda > 0:
                # Exponential expansion for positive Lambda
                a_t = a_0 * math.exp(math.sqrt(params.Lambda/3) * t / 1e9)
            elif params.Lambda < 0:
                # Collapsing universe for negative Lambda
                collapse_time = math.pi / math.sqrt(-params.Lambda/3) * 1e9
                if t < collapse_time:
                    a_t = a_0 * math.cos(math.sqrt(-params.Lambda/3) * t / 1e9)
                else:
                    a_t = 0.0  # Universe has collapsed
            else:
                # Critical universe (power law)
                a_t = a_0 * (t / 1e9) ** (2/3) if t > 0 else a_0
            
            # Temperature evolution (adiabatic cooling)
            T_t = T_0 / a_t if a_t > 0 else 0
            
            # Entropy evolution (typically increasing)
            S_t = S_0 * a_t**3 if a_t > 0 else S_0
            
            # Complexity measure (peaks during structure formation)
            complexity_t = self._calculate_complexity(params, t, a_t, T_t)
            
            evolution["time"].append(t)
            evolution["scale_factor"].append(a_t)
            evolution["temperature"].append(T_t)
            evolution["entropy"].append(S_t)
            evolution["complexity"].append(complexity_t)
            
        return evolution
    
    def _calculate_complexity(self, params: UniverseParameters, 
                            time: float, scale_factor: float, 
                            temperature: float) -> float:
        """Calculate a measure of cosmic complexity."""
        
        # Complexity peaks when structures can form and persist
        # Requires: not too hot (T < nucleosynthesis), not too cold (T > CMB)
        # and universe not collapsing too fast
        
        complexity = 0.0
        
        # Temperature window for complexity
        if 1e-4 < temperature < 1e12:  # Rough temperature range for structure
            temp_factor = 1.0 / (1.0 + abs(math.log10(temperature)))
            complexity += temp_factor
        
        # Scale factor stability (not expanding/contracting too rapidly)
        if scale_factor > 0.1 and scale_factor < 100:
            scale_factor_factor = math.exp(-abs(math.log10(scale_factor))**2)
            complexity += scale_factor_factor
        
        # Physical constant effects
        # Fine structure constant near 1/137 allows atoms
        alpha_factor = math.exp(-100 * (params.alpha - 1.0/137)**2)
        complexity += alpha_factor
        
        # Gravitational constant allows star formation
        G_factor = math.exp(-10 * (params.G - 1.0)**2)
        complexity += G_factor
        
        return complexity / 4.0  # Normalize
    
    def calculate_stability_score(self, params: UniverseParameters) -> float:
        """Calculate how stable/long-lived this universe would be."""
        
        stability = 1.0
        
        # Cosmological constant stability
        if abs(params.Lambda) > 10:
            stability *= 0.1  # Very unstable
        elif abs(params.Lambda) > 1:
            stability *= 0.5  # Somewhat unstable
        
        # Fine structure constant - too large prevents atoms
        if params.alpha > 0.1:
            stability *= 0.1
        elif params.alpha < 1e-4:
            stability *= 0.2
        
        # Gravitational constant - affects star formation
        if params.G > 100 or params.G < 0.01:
            stability *= 0.1
        
        # Mass ratios - proton much heavier than electron needed
        mass_ratio = params.m_proton / params.m_electron
        if mass_ratio < 100 or mass_ratio > 10000:
            stability *= 0.5
        
        return max(0.0, min(1.0, stability))
    
    def calculate_habitability_index(self, params: UniverseParameters) -> float:
        """Calculate how suitable this universe is for complex life."""
        
        habitability = 0.0
        
        # Anthropic principle constraints
        
        # 1. Stable atoms require fine structure constant in narrow range
        alpha_optimal = 1.0/137  # Our universe value
        alpha_score = math.exp(-1000 * (params.alpha - alpha_optimal)**2)
        habitability += 0.3 * alpha_score
        
        # 2. Stars require balanced gravity vs. other forces
        G_score = math.exp(-5 * (params.G - 1.0)**2)
        habitability += 0.2 * G_score
        
        # 3. Nuclear processes require proper mass scales
        mass_score = math.exp(-0.1 * (params.m_proton / params.m_electron - 1836)**2)
        habitability += 0.2 * mass_score
        
        # 4. Cosmic expansion rate (cosmological constant)
        Lambda_score = math.exp(-100 * params.Lambda**2)  # Small Lambda preferred
        habitability += 0.2 * Lambda_score
        
        # 5. Dimensionality - 3+1 spacetime seems optimal
        if params.spacetime_dimensions == 4 and params.signature == (1, 3):
            habitability += 0.1
        
        return habitability


class ParameterSpaceExplorer:
    """Explore the parameter space of possible universes."""
    
    def __init__(self, simulator: UniverseSimulator):
        self.simulator = simulator
        
    def generate_parameter_grid(self, 
                              parameter_ranges: Dict[str, Tuple[float, float]],
                              grid_points: int = 10) -> List[UniverseParameters]:
        """Generate a grid of universe parameters to explore."""
        
        universes = []
        
        # Create grid points for each parameter
        param_grids = {}
        for param_name, (min_val, max_val) in parameter_ranges.items():
            param_grids[param_name] = np.linspace(min_val, max_val, grid_points)
        
        # Generate all combinations
        param_names = list(parameter_ranges.keys())
        param_values = [param_grids[name] for name in param_names]
        
        for combination in itertools.product(*param_values):
            params = UniverseParameters()
            
            # Set parameter values
            for i, param_name in enumerate(param_names):
                setattr(params, param_name, combination[i])
            
            # Calculate derived properties
            params.stability_score = self.simulator.calculate_stability_score(params)
            params.complexity_measure = self._estimate_max_complexity(params)
            params.habitability_index = self.simulator.calculate_habitability_index(params)
            
            universes.append(params)
        
        return universes
    
    def _estimate_max_complexity(self, params: UniverseParameters) -> float:
        """Estimate maximum complexity this universe could achieve."""
        # Run a quick simulation and find peak complexity
        evolution = self.simulator.simulate_universe_evolution(params, 50)
        return max(evolution["complexity"]) if evolution["complexity"] else 0.0
    
    def find_optimal_universes(self, universes: List[UniverseParameters],
                             criteria: str = "habitability") -> List[UniverseParameters]:
        """Find universes that optimize given criteria."""
        
        if criteria == "habitability":
            key_func = lambda u: u.habitability_index
        elif criteria == "stability":
            key_func = lambda u: u.stability_score
        elif criteria == "complexity":
            key_func = lambda u: u.complexity_measure
        else:
            raise ValueError(f"Unknown criteria: {criteria}")
        
        # Sort by criteria and return top 10%
        sorted_universes = sorted(universes, key=key_func, reverse=True)
        top_count = max(1, len(sorted_universes) // 10)
        
        return sorted_universes[:top_count]
    
    def analyze_parameter_sensitivity(self, base_params: UniverseParameters,
                                    parameter: str, variation_range: float = 0.5) -> Dict[str, Any]:
        """Analyze how sensitive universe properties are to one parameter."""
        
        base_value = getattr(base_params, parameter)
        
        # Vary parameter around base value
        variations = np.linspace(base_value * (1 - variation_range),
                               base_value * (1 + variation_range), 21)
        
        results = {
            "parameter_values": [],
            "stability_scores": [],
            "habitability_indices": [],
            "complexity_measures": []
        }
        
        for value in variations:
            test_params = UniverseParameters(**base_params.__dict__)
            setattr(test_params, parameter, value)
            
            # Calculate metrics
            stability = self.simulator.calculate_stability_score(test_params)
            habitability = self.simulator.calculate_habitability_index(test_params)
            complexity = self._estimate_max_complexity(test_params)
            
            results["parameter_values"].append(value)
            results["stability_scores"].append(stability)
            results["habitability_indices"].append(habitability)
            results["complexity_measures"].append(complexity)
        
        return results


class MultiverseLandscape:
    """Visualize and analyze the landscape of possible universes."""
    
    def __init__(self):
        self.universes = []
        
    def add_universe_sample(self, params: UniverseParameters):
        """Add a universe to the landscape."""
        self.universes.append(params)
    
    def create_landscape_field(self, parameter1: str, parameter2: str,
                             metric: str = "habitability") -> NDField:
        """Create a 2D field showing universe properties across parameter space."""
        
        if not self.universes:
            raise ValueError("No universes in landscape")
        
        # Extract parameter values
        param1_vals = [getattr(u, parameter1) for u in self.universes]
        param2_vals = [getattr(u, parameter2) for u in self.universes]
        
        # Extract metric values
        if metric == "habitability":
            metric_vals = [u.habitability_index for u in self.universes]
        elif metric == "stability":
            metric_vals = [u.stability_score for u in self.universes]
        elif metric == "complexity":
            metric_vals = [u.complexity_measure for u in self.universes]
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        # Create grid
        grid_size = int(math.sqrt(len(self.universes)))
        if grid_size * grid_size != len(self.universes):
            grid_size = 10  # Default grid size
            
        # Reshape data into grid
        try:
            field_data = np.array(metric_vals).reshape(grid_size, grid_size)
        except ValueError:
            # If reshape fails, interpolate onto regular grid
            field_data = np.zeros((grid_size, grid_size))
            # Simple nearest neighbor interpolation
            for i in range(grid_size):
                for j in range(grid_size):
                    if i * grid_size + j < len(metric_vals):
                        field_data[i, j] = metric_vals[i * grid_size + j]
        
        return NDField((grid_size, grid_size), field_data.flatten())
    
    def find_anthropic_islands(self, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Find regions in parameter space suitable for complex structures."""
        
        islands = []
        
        # Group nearby universes with high habitability
        high_habitability = [u for u in self.universes if u.habitability_index > threshold]
        
        if not high_habitability:
            return islands
        
        # Simple clustering by parameter similarity
        used = set()
        
        for i, universe in enumerate(high_habitability):
            if i in used:
                continue
                
            # Start new island
            island = {
                "center_params": universe,
                "member_count": 1,
                "avg_habitability": universe.habitability_index,
                "avg_stability": universe.stability_score,
                "parameter_ranges": {}
            }
            
            cluster = [universe]
            used.add(i)
            
            # Find nearby universes
            for j, other in enumerate(high_habitability[i+1:], i+1):
                if j in used:
                    continue
                    
                # Check if parameters are similar (simplified distance metric)
                distance = self._parameter_distance(universe, other)
                
                if distance < 0.5:  # Threshold for clustering
                    cluster.append(other)
                    used.add(j)
            
            # Calculate island properties
            if len(cluster) > 1:
                island["member_count"] = len(cluster)
                island["avg_habitability"] = np.mean([u.habitability_index for u in cluster])
                island["avg_stability"] = np.mean([u.stability_score for u in cluster])
                
                # Calculate parameter ranges
                for param in ["alpha", "G", "Lambda", "m_proton", "m_electron"]:
                    values = [getattr(u, param) for u in cluster]
                    island["parameter_ranges"][param] = (min(values), max(values))
                
                islands.append(island)
        
        return sorted(islands, key=lambda x: x["avg_habitability"], reverse=True)
    
    def _parameter_distance(self, universe1: UniverseParameters, 
                          universe2: UniverseParameters) -> float:
        """Calculate normalized distance between two universes in parameter space."""
        
        # Important parameters for comparison
        params = ["alpha", "G", "Lambda", "m_proton", "m_electron"]
        
        distance_squared = 0.0
        
        for param in params:
            val1 = getattr(universe1, param)
            val2 = getattr(universe2, param)
            
            # Normalized difference
            avg_val = (val1 + val2) / 2
            if avg_val != 0:
                norm_diff = (val1 - val2) / avg_val
                distance_squared += norm_diff ** 2
        
        return math.sqrt(distance_squared / len(params))


# Integration with AdaptiveCAD
class MultiverseExplorationCmd:
    """Command to add multiverse exploration tools to AdaptiveCAD."""
    
    def __init__(self):
        self.name = "Multiverse Exploration"
        
    def run(self, mw):
        """Add multiverse exploration to the main window."""
        if not HAS_DEPENDENCIES:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(mw.win, "Missing Dependencies", 
                              "Multiverse exploration dependencies not available.")
            return
            
        try:
            # Create multiverse tools
            simulator = UniverseSimulator()
            explorer = ParameterSpaceExplorer(simulator)
            landscape = MultiverseLandscape()
            
            # Define parameter ranges to explore
            param_ranges = {
                "alpha": (0.001, 0.01),      # Fine structure constant
                "G": (0.1, 10.0),            # Gravitational constant  
                "Lambda": (-1.0, 1.0),       # Cosmological constant
                "m_proton": (0.5, 2.0),      # Proton mass
                "m_electron": (0.5, 2.0)     # Electron mass
            }
            
            # Generate universe samples (small grid for demo)
            universe_sample = explorer.generate_parameter_grid(param_ranges, grid_points=5)
            
            # Add to landscape
            for universe in universe_sample:
                landscape.add_universe_sample(universe)
            
            # Find optimal universes
            optimal_habitable = explorer.find_optimal_universes(universe_sample, "habitability")
            optimal_stable = explorer.find_optimal_universes(universe_sample, "stability")
            
            # Find anthropic islands
            anthropic_islands = landscape.find_anthropic_islands(threshold=0.3)
            
            # Analyze parameter sensitivity around our universe
            our_universe = UniverseParameters()
            alpha_sensitivity = explorer.analyze_parameter_sensitivity(our_universe, "alpha", 0.2)
            
            mw.win.statusBar().showMessage(
                f"Multiverse exploration: {len(universe_sample)} universes sampled, "
                f"{len(optimal_habitable)} highly habitable, {len(anthropic_islands)} anthropic islands", 5000
            )
            
        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(mw.win, "Error", f"Multiverse exploration error: {str(e)}")
