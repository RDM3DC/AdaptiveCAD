"""Test and demonstration script for AdaptiveCAD Cosmic Exploration features.

This script tests all the cosmic exploration modules and provides examples
of how to use them for scientific visualization and analysis.
"""

import sys
import os
import numpy as np

# Add the AdaptiveCAD path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_spacetime_visualization():
    """Test spacetime visualization tools."""
    print("\n🌌 Testing Spacetime Visualization...")
    
    try:
        from adaptivecad.cosmic.spacetime_viz import LightConeExplorer, CurvatureVisualizer, GravitationalLensing
        from adaptivecad.spacetime import Event
        
        # Test light cone exploration
        origin = Event(0, 0, 0, 0)
        explorer = LightConeExplorer(origin)
        
        future_cone, past_cone = explorer.generate_light_cone_surface(radius=2.0, resolution=20)
        print(f"  ✓ Generated light cones: {len(future_cone)} future, {len(past_cone)} past events")
        
        # Test causality analysis
        event1 = Event(0, 0, 0, 0)
        event2 = Event(1, 0.5, 0, 0)  # Timelike separated
        event3 = Event(0, 2, 0, 0)    # Spacelike separated
        
        relation1 = explorer.is_causally_connected(event1, event2)
        relation2 = explorer.is_causally_connected(event1, event3)
        print(f"  ✓ Causal analysis: event1-event2 = {relation1}, event1-event3 = {relation2}")
        
        # Test worldline generation
        worldline = explorer.generate_worldline((0.5, 0, 0), duration=2.0, steps=10)
        print(f"  ✓ Generated worldline with {len(worldline)} events")
        
        # Test curvature visualization
        curv_viz = CurvatureVisualizer()
        masses = [(Event(0, 0, 0, 0), 10.0)]
        curvature_field = curv_viz.create_curvature_field(masses, (8, 8, 8, 8))
        print(f"  ✓ Created curvature field: shape {curvature_field.grid_shape}")
        
        # Test gravitational lensing
        lens = GravitationalLensing(mass=5.0, lens_position=Event(0, 0, 0, 0))
        light_ray = [Event(0, -5, y, 0) for y in np.linspace(-1, 1, 10)]
        deflected_ray = lens.calculate_light_deflection(light_ray)
        print(f"  ✓ Calculated gravitational lensing for {len(deflected_ray)} light ray events")
        
        print("  🎉 Spacetime visualization tests passed!")
        return True
        
    except Exception as e:
        print(f"  ❌ Spacetime visualization test failed: {e}")
        return False


def test_quantum_geometry():
    """Test quantum geometry visualization tools."""
    print("\n⚛️ Testing Quantum Geometry...")
    
    try:
        from adaptivecad.cosmic.quantum_geometry import (
            QuantumState, WavefunctionVisualizer, EntanglementVisualizer, QuantumFieldVisualizer
        )
        
        # Test quantum states
        amplitudes = [1/np.sqrt(2), 0, 0, 1/np.sqrt(2)]  # Bell state
        basis_labels = ["|00⟩", "|01⟩", "|10⟩", "|11⟩"]
        bell_state = QuantumState(amplitudes, basis_labels, 4)
        
        normalized = bell_state.normalize()
        prob_00 = bell_state.probability(0)
        print(f"  ✓ Created Bell state: P(|00⟩) = {prob_00:.3f}")
        
        # Test wavefunction visualization
        wf_viz = WavefunctionVisualizer(grid_size=(16, 16, 16))
        hydrogen_1s = wf_viz.hydrogen_wavefunction(1, 0, 0)
        print(f"  ✓ Generated hydrogen 1s wavefunction: shape {hydrogen_1s.grid_shape}")
        
        harmonic_n2 = wf_viz.quantum_harmonic_oscillator(2, omega=1.0)
        print(f"  ✓ Generated harmonic oscillator n=2: shape {harmonic_n2.grid_shape}")
        
        # Test entanglement analysis
        ent_viz = EntanglementVisualizer()
        bell_phi_plus = ent_viz.create_bell_state("phi_plus")
        entanglement_entropy = ent_viz.calculate_entanglement_entropy(bell_phi_plus)
        print(f"  ✓ Bell state entanglement entropy: {entanglement_entropy:.3f} bits")
        
        # Test Bloch sphere representation
        qubit = np.array([1/np.sqrt(2), 1/np.sqrt(2)])  # |+⟩ state
        bloch_coords = ent_viz.visualize_bloch_sphere(qubit)
        print(f"  ✓ Bloch sphere coordinates: ({bloch_coords[0]:.3f}, {bloch_coords[1]:.3f}, {bloch_coords[2]:.3f})")
        
        # Test quantum field visualization
        qf_viz = QuantumFieldVisualizer(field_size=(12, 12, 12))
        vacuum_field = qf_viz.scalar_field_vacuum_fluctuations(field_strength=0.5)
        print(f"  ✓ Generated vacuum fluctuations: shape {vacuum_field.grid_shape}")
        
        particle = qf_viz.create_particle_excitation((0, 0, 0), (1, 0, 0), mass=1.0)
        print(f"  ✓ Created particle excitation: shape {particle.grid_shape}")
        
        print("  🎉 Quantum geometry tests passed!")
        return True
        
    except Exception as e:
        print(f"  ❌ Quantum geometry test failed: {e}")
        return False


def test_cosmological_simulations():
    """Test cosmological simulation tools."""
    print("\n🌠 Testing Cosmological Simulations...")
    
    try:
        from adaptivecad.cosmic.cosmological_sims import (
            CosmologicalParameters, UniverseExpansionSimulator, 
            StructureFormationSimulator, CMBVisualizer
        )
        
        # Test cosmological parameters
        lambda_cdm = CosmologicalParameters(
            H0=70.0, omega_matter=0.31, omega_lambda=0.69
        )
        print(f"  ✓ Created ΛCDM model: H₀={lambda_cdm.H0}, Ωₘ={lambda_cdm.omega_matter}")
        
        # Test universe expansion
        expansion_sim = UniverseExpansionSimulator(lambda_cdm)
        
        scale_now = expansion_sim.scale_factor(13.8e9)
        scale_early = expansion_sim.scale_factor(1e6)
        print(f"  ✓ Scale factors: early={scale_early:.6f}, now={scale_now:.3f}")
        
        hubble_z1 = expansion_sim.hubble_parameter(1.0)  # z=1
        print(f"  ✓ Hubble parameter at z=1: {hubble_z1:.1f} km/s/Mpc")
        
        comoving_dist = expansion_sim.comoving_distance(1.0, steps=100)
        print(f"  ✓ Comoving distance to z=1: {comoving_dist:.0f} Mpc")
        
        times, scale_factors = expansion_sim.generate_expansion_history((1e6, 13.8e9), 20)
        print(f"  ✓ Generated expansion history: {len(times)} time steps")
        
        # Test structure formation
        structure_sim = StructureFormationSimulator(box_size=25.0, n_particles=8**3)
        initial_field = structure_sim.generate_initial_conditions(redshift_initial=100.0)
        print(f"  ✓ Generated initial conditions: shape {initial_field.grid_shape}")
        
        evolution = structure_sim.evolve_density_field(initial_field, redshift_final=0.0, time_steps=3)
        print(f"  ✓ Evolved density field: {len(evolution)} time steps")
        
        halos = structure_sim.identify_halos(evolution[-1], threshold=1.3)
        print(f"  ✓ Identified {len(halos)} dark matter halos")
        
        # Test CMB visualization
        cmb_viz = CMBVisualizer(map_resolution=32)
        cmb_map = cmb_viz.generate_cmb_map(l_max=20)
        print(f"  ✓ Generated CMB map: shape {cmb_map.grid_shape}")
        
        print("  🎉 Cosmological simulation tests passed!")
        return True
        
    except Exception as e:
        print(f"  ❌ Cosmological simulation test failed: {e}")
        return False


def test_topology_exploration():
    """Test topology exploration tools."""
    print("\n🔗 Testing Topology Exploration...")
    
    try:
        from adaptivecad.cosmic.topology_tools import (
            HomologyCalculator, HomotopyAnalyzer, ManifoldAnalyzer, TopologicalSpace
        )
        
        # Test homology calculation
        homology_calc = HomologyCalculator(dimension=3)
        
        # Create a torus-like point cloud
        n_points = 50
        theta = np.linspace(0, 2*np.pi, n_points)
        R, r = 2.0, 0.5
        x = (R + r*np.cos(theta)) * np.cos(theta)
        y = (R + r*np.cos(theta)) * np.sin(theta)
        z = r * np.sin(theta)
        torus_points = np.column_stack([x, y, z])
        
        betti_numbers = homology_calc.calculate_betti_numbers(torus_points)
        print(f"  ✓ Torus Betti numbers: β₀={betti_numbers[0]}, β₁={betti_numbers[1]}, β₂={betti_numbers[2]}")
        
        # Test homotopy analysis
        homotopy_analyzer = HomotopyAnalyzer()
        pi1_torus = homotopy_analyzer.analyze_fundamental_group(TopologicalSpace.TOROIDAL)
        pi1_sphere = homotopy_analyzer.analyze_fundamental_group(TopologicalSpace.SPHERICAL)
        print(f"  ✓ Fundamental groups: π₁(T²) = {pi1_torus}, π₁(S²) = {pi1_sphere}")
        
        # Create a simple loop
        loop_points = [np.array([[np.cos(t), np.sin(t), 0] for t in np.linspace(0, 2*np.pi, 20)])]
        loop_analysis = homotopy_analyzer.analyze_loops(loop_points)
        print(f"  ✓ Loop analysis: {loop_analysis}")
        
        # Test manifold analysis
        manifold_analyzer = ManifoldAnalyzer()
        
        # Create simple triangulated surface (tetrahedron)
        vertices = np.array([[0, 0, 0], [1, 0, 0], [0.5, np.sqrt(3)/2, 0], [0.5, np.sqrt(3)/6, np.sqrt(6)/3]])
        triangles = [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)]
        
        surface_topology = manifold_analyzer.analyze_surface_topology(vertices, triangles)
        print(f"  ✓ Surface topology: χ={surface_topology['euler_characteristic']}, genus={surface_topology['genus']}")
        
        # Test topological defect detection
        field_size = (16, 16)
        # Create a simple vortex field
        y_coords, x_coords = np.mgrid[0:field_size[0], 0:field_size[1]]
        center_x, center_y = field_size[0]//2, field_size[1]//2
        dx = x_coords - center_x
        dy = y_coords - center_y
        theta_field = np.arctan2(dy, dx)
        vortex_field = np.exp(1j * theta_field)
        
        from adaptivecad.ndfield import NDField
        test_field = NDField(field_size, vortex_field.flatten())
        
        vortices = manifold_analyzer.detect_topological_defects(test_field, "vortex")
        print(f"  ✓ Detected {len(vortices)} topological vortices")
        
        print("  🎉 Topology exploration tests passed!")
        return True
        
    except Exception as e:
        print(f"  ❌ Topology exploration test failed: {e}")
        return False


def test_multiverse_exploration():
    """Test multiverse exploration tools."""
    print("\n🌌 Testing Multiverse Exploration...")
    
    try:
        from adaptivecad.cosmic.multiverse_explorer import (
            UniverseParameters, UniverseSimulator, ParameterSpaceExplorer, MultiverseLandscape
        )
        
        # Test universe parameters
        our_universe = UniverseParameters()
        alt_universe = UniverseParameters(alpha=0.01, G=2.0, Lambda=0.5)
        print(f"  ✓ Created universe parameters: α={our_universe.alpha}, G={our_universe.G}")
        
        # Test universe simulation
        simulator = UniverseSimulator()
        
        evolution = simulator.simulate_universe_evolution(our_universe, time_steps=10)
        print(f"  ✓ Simulated universe evolution: {len(evolution['time'])} time steps")
        
        stability = simulator.calculate_stability_score(our_universe)
        habitability = simulator.calculate_habitability_index(our_universe)
        print(f"  ✓ Our universe: stability={stability:.3f}, habitability={habitability:.3f}")
        
        alt_stability = simulator.calculate_stability_score(alt_universe)
        alt_habitability = simulator.calculate_habitability_index(alt_universe)
        print(f"  ✓ Alt universe: stability={alt_stability:.3f}, habitability={alt_habitability:.3f}")
        
        # Test parameter space exploration
        explorer = ParameterSpaceExplorer(simulator)
        
        param_ranges = {
            "alpha": (0.001, 0.01),
            "G": (0.5, 2.0),
            "Lambda": (-0.5, 0.5)
        }
        
        universe_grid = explorer.generate_parameter_grid(param_ranges, grid_points=3)
        print(f"  ✓ Generated parameter grid: {len(universe_grid)} universes")
        
        optimal_habitable = explorer.find_optimal_universes(universe_grid, "habitability")
        optimal_stable = explorer.find_optimal_universes(universe_grid, "stability")
        print(f"  ✓ Found {len(optimal_habitable)} highly habitable, {len(optimal_stable)} highly stable universes")
        
        # Test parameter sensitivity
        sensitivity = explorer.analyze_parameter_sensitivity(our_universe, "alpha", 0.1)
        max_habitability = max(sensitivity["habitability_indices"])
        print(f"  ✓ Alpha sensitivity: max habitability = {max_habitability:.3f}")
        
        # Test multiverse landscape
        landscape = MultiverseLandscape()
        for universe in universe_grid:
            landscape.add_universe_sample(universe)
        
        anthropic_islands = landscape.find_anthropic_islands(threshold=0.1)
        print(f"  ✓ Found {len(anthropic_islands)} anthropic islands")
        
        if len(anthropic_islands) > 0:
            best_island = anthropic_islands[0]
            print(f"  ✓ Best island: {best_island['member_count']} members, "
                  f"avg habitability = {best_island['avg_habitability']:.3f}")
        
        print("  🎉 Multiverse exploration tests passed!")
        return True
        
    except Exception as e:
        print(f"  ❌ Multiverse exploration test failed: {e}")
        return False


def test_integration():
    """Test integration with existing AdaptiveCAD components."""
    print("\n🔧 Testing Integration with AdaptiveCAD...")
    
    try:
        # Test that cosmic modules can import AdaptiveCAD components
        from adaptivecad.spacetime import Event, minkowski_interval
        from adaptivecad.ndfield import NDField
        
        # Test spacetime integration
        event1 = Event(0, 0, 0, 0)
        event2 = Event(1, 0.5, 0, 0)
        interval = minkowski_interval(event1, event2)
        print(f"  ✓ Spacetime integration: interval = {interval:.3f}")
        
        # Test NDField integration
        field = NDField((10, 10), np.random.random(100))
        slice_2d = field.get_slice([5, None])
        print(f"  ✓ NDField integration: slice shape = {slice_2d.shape}")
        
        # Test with hyperbolic geometry if available
        try:
            from adaptivecad.geom.hyperbolic import pi_a_over_pi
            pi_ratio = pi_a_over_pi(1.0, 0.5)
            print(f"  ✓ Hyperbolic geometry integration: πₐ/π = {pi_ratio:.3f}")
        except ImportError:
            print("  ⚠️ Hyperbolic geometry not available")
        
        print("  🎉 Integration tests passed!")
        return True
        
    except Exception as e:
        print(f"  ❌ Integration test failed: {e}")
        return False


def main():
    """Run all cosmic exploration tests."""
    print("🚀 AdaptiveCAD Cosmic Exploration Test Suite")
    print("=" * 50)
    
    tests = [
        ("Spacetime Visualization", test_spacetime_visualization),
        ("Quantum Geometry", test_quantum_geometry),
        ("Cosmological Simulations", test_cosmological_simulations),
        ("Topology Exploration", test_topology_exploration),
        ("Multiverse Exploration", test_multiverse_exploration),
        ("Integration", test_integration),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = 0
    failed = 0
    
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status:<10} {test_name}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print("-" * 60)
    print(f"Total: {passed + failed} tests")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 All cosmic exploration features are working perfectly!")
        print("🌌 AdaptiveCAD is ready for deep universe exploration!")
    else:
        print(f"\n⚠️ {failed} test(s) failed. Check dependencies and implementation.")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
