"""AdaptiveCAD Cosmic Exploration Module.

This module extends AdaptiveCAD's geometry and visualization capabilities
for deep exploration of cosmological, quantum, and relativistic phenomena.
Builds on the existing spacetime, ndfield, and adaptive pi geometry foundations.
"""

try:
    from .spacetime_viz import *
    from .quantum_geometry import *
    from .cosmological_sims import *
    from .topology_tools import *
    from .multiverse_explorer import *
    from .curve_tools import *
    HAS_COSMIC_MODULES = True
except ImportError as e:
    HAS_COSMIC_MODULES = False
    print(f"Warning: Some cosmic modules not available: {e}")

# Commands for integration with AdaptiveCAD GUI
if HAS_COSMIC_MODULES:    COSMIC_COMMANDS = [
        ("Spacetime Visualization", "SpacetimeVisualizationCmd"),
        ("Light Cone Display Box", "LightConeDisplayBoxCmd"),
        ("Quantum Geometry", "QuantumVisualizationCmd"),
        ("Cosmological Simulation", "CosmologicalSimulationCmd"),
        ("Topology Exploration", "TopologyExplorationCmd"),
        ("Multiverse Exploration", "MultiverseExplorationCmd"),
        ("Bizarre Curve", "BizarreCurveCmd"),
        ("Cosmic Spline", "CosmicSplineCmd"),
        ("ND Field Explorer", "NDFieldExplorerCmd"),
    ]
else:
    COSMIC_COMMANDS = []
