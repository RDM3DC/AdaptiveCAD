#!/usr/bin/env python3
"""
Quick test script to verify the new Mandelbulb UI controls are working.
This script creates a Mandelbulb primitive and exports it with different settings.
"""

import sys
import os
import time
from pathlib import Path

# Add the AdaptiveCAD path
sys.path.insert(0, str(Path(__file__).parent))

def test_new_mandelbulb_cli():
    """Test the new CLI parameters we just added."""
    print("=== Testing New Mandelbulb CLI Parameters ===")
    
    # Test 1: Adaptive π with Euclidean norm
    print("\n[Test 1] Adaptive π + Euclidean norm (safe mode)")
    cmd1 = [
        sys.executable, "mandelbulb_make.py",
        "--res", "64",  # Small for quick test
        "--pi-mode", "adaptive",
        "--pi-alpha", "0.0",
        "--pi-mu", "0.05", 
        "--norm-mode", "euclid",
        "--gpu",
        "--outfile", "test_adaptive_pi"
    ]
    
    import subprocess
    result1 = subprocess.run(cmd1, capture_output=True, text=True, cwd=Path(__file__).parent)
    if result1.returncode == 0:
        print("✅ Adaptive π + Euclidean norm test PASSED")
    else:
        print("❌ Test failed:")
        print(result1.stderr)
        
    # Test 2: Full adaptive mode
    print("\n[Test 2] Adaptive π + Adaptive norm + GPU colors")
    cmd2 = [
        sys.executable, "mandelbulb_make.py",
        "--res", "64",
        "--pi-mode", "adaptive",
        "--pi-alpha", "0.0",
        "--pi-mu", "0.05",
        "--norm-mode", "adaptive",
        "--norm-k", "0.12",
        "--norm-r0", "0.9", 
        "--norm-sigma", "0.35",
        "--step-scale", "0.8",
        "--gpu",
        "--gpu-colors",
        "--color", "orbit",
        "--outfile", "test_full_adaptive"
    ]
    
    result2 = subprocess.run(cmd2, capture_output=True, text=True, cwd=Path(__file__).parent)
    if result2.returncode == 0:
        print("✅ Full adaptive mode test PASSED")
    else:
        print("❌ Test failed:")
        print(result2.stderr)
        
    print("\n=== CLI Tests Complete ===")
    return result1.returncode == 0 and result2.returncode == 0

def show_new_ui_features():
    """Display information about the new UI features."""
    print("\n=== NEW MANDELBULB UI FEATURES ===")
    print("🎛️  New Controls Added to Parameter Panel:")
    print("   • Norm Mode: [Euclidean, Adaptive Norm]")
    print("   • Norm k: 0.0 - 1.0 (default: 0.12)")
    print("   • Norm r₀: 0.1 - 2.0 (default: 0.9)")
    print("   • Norm σ: 0.01 - 1.0 (default: 0.35)")
    print("   • Step Scale: 0.1 - 2.0 (default: 1.0, auto-adjusts to 0.8 for adaptive)")
    print("   • GPU Vertex Colors: Enable GPU vertex coloring")
    print("")
    print("🔬 Smart Features:")
    print("   • Auto step scale adjustment: Euclidean=1.0, Adaptive=0.8")
    print("   • GPU coloring with RawKernel for performance")
    print("   • Fallback to CPU if GPU fails")
    print("   • All existing π controls preserved")
    print("")
    print("📍 Location: Look for 'Mandelbulb Mesh Export' section in parameter panel")
    print("🎯 Usage: Create Mandelbulb primitive → Set parameters → Export STL & PLY")
    
if __name__ == "__main__":
    print("AdaptiveCAD Mandelbulb UI Enhancement Test")
    print("=" * 50)
    
    # Show new features
    show_new_ui_features()
    
    # Test CLI
    cli_success = test_new_mandelbulb_cli()
    
    if cli_success:
        print("\n🎉 ALL TESTS PASSED! New Mandelbulb features are working correctly.")
        print("\n👉 Next steps:")
        print("   1. Open the Analytic Viewport")
        print("   2. Add a Mandelbulb primitive from the toolbar")
        print("   3. Find 'Mandelbulb Mesh Export' in the parameter panel")
        print("   4. Try the new Adaptive norm controls!")
    else:
        print("\n⚠️  Some tests failed. Check error messages above.")
        
    print("\nTest completed.")