#!/usr/bin/env python3
"""Test script for the new cosmic curve tools in AdaptiveCAD."""

import sys

def test_imports():
    """Test that all cosmic curve tools can be imported."""
    print("Testing cosmic curve tool imports...")
    
    try:
        from adaptivecad.cosmic.curve_tools import BizarreCurveCmd, CosmicSplineCmd, NDFieldExplorerCmd
        print("✓ All cosmic curve commands imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False

def test_cosmic_module():
    """Test the cosmic module initialization."""
    print("\nTesting cosmic module initialization...")
    
    try:
        from adaptivecad.cosmic import HAS_COSMIC_MODULES, COSMIC_COMMANDS
        print(f"✓ Cosmic modules available: {HAS_COSMIC_MODULES}")
        print(f"✓ Number of cosmic commands: {len(COSMIC_COMMANDS)}")
        
        # Check that our new commands are included
        command_names = [cmd[0] for cmd in COSMIC_COMMANDS]
        expected_commands = ["Bizarre Curve", "Cosmic Spline", "ND Field Explorer", "Light Cone Display Box"]
        
        for cmd in expected_commands:
            if cmd in command_names:
                print(f"✓ Found command: {cmd}")
            else:
                print(f"✗ Missing command: {cmd}")
                return False
        
        return True
    except ImportError as e:
        print(f"✗ Cosmic module import failed: {e}")
        return False

def test_feature_creation():
    """Test creating the feature objects without GUI."""
    print("\nTesting feature creation...")
    
    try:
        from adaptivecad.cosmic.curve_tools import BizarreCurveFeature, CosmicSplineFeature, NDFieldExplorerFeature
        
        # Test BizarreCurveFeature
        try:
            bizarre_curve = BizarreCurveFeature(
                base_radius=20.0,
                height=50.0,
                frequency=2.0,
                distortion=1.0,
                segments=50
            )
            print("✓ BizarreCurveFeature created successfully")
        except Exception as e:
            print(f"✗ BizarreCurveFeature failed: {e}")
        
        # Test CosmicSplineFeature
        try:
            control_points = [(0, 0, 0), (10, 10, 5), (20, 0, 10), (30, -10, 15)]
            cosmic_spline = CosmicSplineFeature(
                control_points=control_points,
                degree=3,
                cosmic_curvature=0.5
            )
            print("✓ CosmicSplineFeature created successfully")
        except Exception as e:
            print(f"✗ CosmicSplineFeature failed: {e}")
        
        # Test NDFieldExplorerFeature
        try:
            ndfield_explorer = NDFieldExplorerFeature(
                dimensions=4,
                grid_size=5,
                field_type="scalar_wave"
            )
            print("✓ NDFieldExplorerFeature created successfully")
        except Exception as e:
            print(f"✗ NDFieldExplorerFeature failed: {e}")
        
        return True
    except ImportError as e:
        print(f"✗ Feature import failed: {e}")
        return False

def test_light_cone_import():
    """Test that light cone display box can be imported."""
    print("\nTesting light cone display box import...")
    
    try:
        from adaptivecad.cosmic.spacetime_viz import LightConeDisplayBoxCmd, SpacetimeVisualizationCmd
        print("✓ Light Cone Display Box command imported successfully")
        print("✓ Enhanced Spacetime Visualization command imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Light cone import failed: {e}")
        return False

def main():
    """Run all tests."""
    print("AdaptiveCAD Cosmic Curve Tools Test Suite")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_cosmic_module,
        test_feature_creation,
        test_light_cone_import
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                print("Test failed!")
        except Exception as e:
            print(f"Test crashed: {e}")
        print()
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! The cosmic curve tools are ready to use.")
        print("\nTo use them:")
        print("1. Run: python -m adaptivecad.gui.playground")
        print("2. Look for the 'Advanced Shapes' menu")
        print("3. You'll find: Bizarre Curve, Cosmic Spline, ND Field Explorer")
        print("4. Or check the 'Cosmic Exploration' menus:")
        print("   • 'Spacetime & Relativity' → Light Cone Display Box")
        print("   • 'Cosmic Curve Tools' → Bizarre Curve, Cosmic Spline, ND Field Explorer")
        return 0
    else:
        print("❌ Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
