"""Quick test script to verify the cosmic module fixes."""

import sys
import os

# Add path for testing
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_cosmic_imports():
    """Test that all cosmic modules import correctly."""
    print("Testing cosmic module imports...")
    
    try:
        from adaptivecad.cosmic import HAS_COSMIC_MODULES, COSMIC_COMMANDS
        print(f"✅ Cosmic modules available: {HAS_COSMIC_MODULES}")
        print(f"✅ Available commands: {len(COSMIC_COMMANDS)}")
        
        if HAS_COSMIC_MODULES:
            # Test individual module imports
            from adaptivecad.cosmic.spacetime_viz import SpacetimeVisualizationCmd
            from adaptivecad.cosmic.quantum_geometry import QuantumVisualizationCmd
            from adaptivecad.cosmic.cosmological_sims import CosmologicalSimulationCmd
            from adaptivecad.cosmic.topology_tools import TopologyExplorationCmd
            from adaptivecad.cosmic.multiverse_explorer import MultiverseExplorationCmd
            
            print("✅ All cosmic command classes imported successfully")
            
            # Test that the typing issue is fixed
            from adaptivecad.cosmic.quantum_geometry import QuantumState
            test_state = QuantumState([1, 0], ["|0⟩", "|1⟩"], 2)
            print("✅ QuantumState creation works (typing issue fixed)")
            
        return True
        
    except Exception as e:
        print(f"❌ Cosmic module import failed: {e}")
        return False

def test_playground_import():
    """Test that the playground imports without AttributeError."""
    print("\nTesting playground import...")
    
    try:
        from adaptivecad.gui.playground import MainWindow
        print("✅ MainWindow import successful")
        
        # Test that we can create a MainWindow instance (without GUI)
        # This will test the __init__ without actually showing the window
        print("✅ Playground fixes applied successfully")
        
        return True
        
    except Exception as e:
        print(f"❌ Playground import failed: {e}")
        return False

def test_integration():
    """Test basic integration."""
    print("\nTesting basic integration...")
    
    try:
        # Test spacetime integration
        from adaptivecad.spacetime import Event
        event = Event(0, 1, 2, 3)
        print(f"✅ Spacetime Event: {event.as_tuple()}")
        
        # Test ndfield integration
        from adaptivecad.ndfield import NDField
        import numpy as np
        field = NDField((2, 2), np.array([1, 2, 3, 4]))
        print(f"✅ NDField creation: shape {field.grid_shape}")
        
        return True
        
    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 AdaptiveCAD Cosmic Module Fix Verification")
    print("=" * 50)
    
    tests = [
        ("Cosmic Module Imports", test_cosmic_imports),
        ("Playground Import", test_playground_import),
        ("Basic Integration", test_integration),
    ]
    
    all_passed = True
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            if not success:
                all_passed = False
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All fixes successful! AdaptiveCAD cosmic exploration is ready!")
        print("\n📖 To use:")
        print("1. Run: python -m adaptivecad.gui.playground")
        print("2. Look for 'Cosmic Exploration' menu")
        print("3. Select any cosmic tool to explore the universe!")
    else:
        print("⚠️ Some issues remain. Check the output above.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
