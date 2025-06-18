#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
multiverse_demo.py - Demonstration script for the AdaptiveCAD Multiverse Exploration features.

This script provides a standalone demo of multiverse hypothesis exploration without requiring 
the full GUI interface. It showcases parameter space exploration and anthropic island detection.
"""

import os
import sys
import importlib
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# Add parent directory to path if needed
script_dir = Path(__file__).parent
parent_dir = script_dir.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

try:
    from adaptivecad.cosmic.spacetime_viz import (
        Config, UniverseParameters, UniverseSimulator, 
        ParameterSpaceExplorer, MultiverseLandscape
    )
except ImportError:
    print("Error: Could not import multiverse exploration classes.")
    print("Please make sure you've installed AdaptiveCAD correctly.")
    sys.exit(1)


def run_multiverse_demo():
    """Run a demonstration of multiverse exploration and parameter analysis."""
    print("=" * 70)
    print("   AdaptiveCAD Multiverse Exploration Demonstration")
    print("=" * 70)
    print("\nInitializing universe simulator and parameter explorer...")
    
    # Create simulator and explorer
    config = Config()
    simulator = UniverseSimulator(config)
    explorer = ParameterSpaceExplorer(simulator)
    
    # Define parameter ranges
    parameter_ranges = {
        "alpha": (0.005, 0.01),  # Fine structure constant range
        "G": (0.5, 5.0),         # Gravitational constant range
        "Lambda": (-0.5, 0.5)    # Cosmological constant range
    }
    
    print(f"Exploring parameter space with ranges:")
    for param, (min_val, max_val) in parameter_ranges.items():
        print(f"  • {param}: {min_val} to {max_val}")
    
    # Generate universe samples
    n_samples = 100
    print(f"\nGenerating {n_samples} universe samples...")
    universes = explorer.generate_parameter_grid(
        parameter_ranges, 
        n_samples=n_samples,
        method="latin_hypercube"
    )
    
    # Create landscape
    print("Creating multiverse landscape...")
    landscape = MultiverseLandscape()
    for universe in universes:
        landscape.add_universe_sample(universe)
    
    # Find anthropic islands
    print("Finding anthropic islands...")
    islands = landscape.find_anthropic_islands(threshold=0.3)
    
    # Find optimal universes
    print("Identifying optimal universes...")
    optimal_universes = explorer.find_optimal_universes(universes)
    
    # Print summary statistics
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    
    # Calculate statistics
    habitability_scores = [u.habitability_index for u in universes]
    stability_scores = [u.stability_score for u in universes]
    complexity_scores = [u.complexity_measure for u in universes]
    
    print(f"Total universes explored: {len(universes)}")
    print(f"Anthropic islands found: {len(islands)}")
    
    print("\nMetric statistics:")
    print(f"  • Habitability - Mean: {np.mean(habitability_scores):.3f}, Max: {np.max(habitability_scores):.3f}")
    print(f"  • Stability - Mean: {np.mean(stability_scores):.3f}, Max: {np.max(stability_scores):.3f}")
    print(f"  • Complexity - Mean: {np.mean(complexity_scores):.3f}, Max: {np.max(complexity_scores):.3f}")
    
    # Print top universes
    print("\nTop 3 Optimal Universes:")
    for i, universe in enumerate(optimal_universes[:3]):
        print(f"  {i+1}. α={universe.alpha:.6f}, G={universe.G:.2f}, Λ={universe.Lambda:.4f}")
        print(f"     H={universe.habitability_index:.3f}, S={universe.stability_score:.3f}, C={universe.complexity_measure:.3f}")
    
    # Print island statistics
    if islands:
        print(f"\nAnthropically viable islands details:")
        for i, island in enumerate(islands):
            mean_h = np.mean([u.habitability_index for u in island])
            print(f"  Island {i+1}: {len(island)} universes, mean habitability: {mean_h:.3f}")
    
    # Try to visualize results if matplotlib is available
    try:
        print("\nCreating visualization (close plot window to continue)...")
        plt.figure(figsize=(10, 8))
        
        # Create scatter plot of alpha vs G colored by habitability
        plt.subplot(2, 2, 1)
        alphas = [u.alpha for u in universes]
        gs = [u.G for u in universes]
        h_vals = [u.habitability_index for u in universes]
        scatter = plt.scatter(alphas, gs, c=h_vals, cmap='viridis', alpha=0.7)
        plt.colorbar(scatter, label="Habitability")
        plt.xlabel("Fine Structure Constant (α)")
        plt.ylabel("Gravitational Constant (G)")
        plt.title("Parameter Space Exploration")
        
        # Create histogram of habitability
        plt.subplot(2, 2, 2)
        plt.hist(habitability_scores, bins=15, color='skyblue', edgecolor='black')
        plt.xlabel("Habitability Index")
        plt.ylabel("Count")
        plt.title("Habitability Distribution")
        
        # Create scatter plot of alpha vs Λ colored by stability
        plt.subplot(2, 2, 3)
        lambdas = [u.Lambda for u in universes]
        s_vals = [u.stability_score for u in universes]
        scatter = plt.scatter(alphas, lambdas, c=s_vals, cmap='plasma', alpha=0.7)
        plt.colorbar(scatter, label="Stability")
        plt.xlabel("Fine Structure Constant (α)")
        plt.ylabel("Cosmological Constant (Λ)")
        plt.title("Parameter Space Stability")
        
        # Create histogram of complexity
        plt.subplot(2, 2, 4)
        plt.hist(complexity_scores, bins=15, color='lightgreen', edgecolor='black')
        plt.xlabel("Complexity Measure")
        plt.ylabel("Count")
        plt.title("Complexity Distribution")
        
        plt.tight_layout()
        plt.show()
        
    except Exception as e:
        print(f"Visualization error: {e}")
    
    print("\nDemo completed successfully!")
    print("\nTo explore further, run the full AdaptiveCAD with:")
    print("  python -m adaptivecad.gui.playground")
    print("Then use the Multiverse Explorer command from the menu.")


if __name__ == "__main__":
    try:
        run_multiverse_demo()
    except Exception as e:
        print(f"Error running demo: {e}")
        sys.exit(1)
