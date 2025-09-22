#!/usr/bin/env python3
"""Comprehensive test script for AdaptiveCAD playground functionality."""

import sys
import os
import subprocess
import time
from pathlib import Path

def test_import():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    
    try:
        import numpy
        print("✓ numpy imported successfully")
    except ImportError as e:
        print(f"✗ numpy import failed: {e}")
        return False
    
    try:
        import PySide6
        print("✓ PySide6 imported successfully")
    except ImportError as e:
        print(f"✗ PySide6 import failed: {e}")
        return False
    
    try:
        from adaptivecad.gui.playground import MainWindow, main
        print("✓ playground module imported successfully")
    except ImportError as e:
        print(f"✗ playground import failed: {e}")
        return False
    
    return True

def test_mainwindow_creation():
    """Test MainWindow class creation."""
    print("\nTesting MainWindow creation...")
    
    # Set offscreen platform for headless testing
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    try:
        from adaptivecad.gui.playground import MainWindow
        mw = MainWindow()
        print("✓ MainWindow created successfully")
        
        # Check key attributes
        if hasattr(mw, 'win'):
            print("✓ Main window widget created")
        else:
            print("✗ Main window widget missing")
            return False
            
        if hasattr(mw, 'app'):
            print("✓ QApplication instance created")
        else:
            print("✗ QApplication instance missing")
            return False
            
        if hasattr(mw, 'run'):
            print("✓ run method available")
        else:
            print("✗ run method missing")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ MainWindow creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_demo_mode():
    """Test demo mode functionality."""
    print("\nTesting demo mode...")
    
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    
    try:
        from adaptivecad.gui.playground import MainWindow
        mw = MainWindow()
        
        start_time = time.time()
        result = mw.run(demo_mode=True, demo_timeout=500)  # 500ms timeout
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"✓ Demo mode completed in {duration:.2f} seconds")
        print(f"✓ Exit code: {result}")
        
        if duration > 2.0:  # Should complete quickly in offscreen mode
            print("! Demo took longer than expected (but still passed)")
        
        return result == 0
        
    except Exception as e:
        print(f"✗ Demo mode failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_command_line():
    """Test command line execution."""
    print("\nTesting command line execution...")
    
    project_root = Path(__file__).parent
    
    try:
        # Test regular module execution
        env = os.environ.copy()
        env['QT_QPA_PLATFORM'] = 'offscreen'
        
        result = subprocess.run([
            sys.executable, '-m', 'adaptivecad.gui.playground', '--demo'
        ], cwd=project_root, env=env, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            print("✓ Command line execution successful")
            print(f"✓ Exit code: {result.returncode}")
            if result.stderr:
                print(f"  (stderr: {result.stderr.strip()})")
            return True
        else:
            print(f"✗ Command line execution failed with exit code {result.returncode}")
            if result.stdout:
                print(f"  stdout: {result.stdout}")
            if result.stderr:
                print(f"  stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ Command line execution timed out")
        return False
    except Exception as e:
        print(f"✗ Command line test failed: {e}")
        return False

def test_enhanced_launcher():
    """Test the enhanced launcher script."""
    print("\nTesting enhanced launcher...")
    
    project_root = Path(__file__).parent
    launcher_path = project_root / "run_playground_enhanced.py"
    
    if not launcher_path.exists():
        print(f"✗ Enhanced launcher not found at {launcher_path}")
        return False
    
    try:
        result = subprocess.run([
            sys.executable, str(launcher_path)
        ], cwd=project_root, capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            print("✓ Enhanced launcher executed successfully")
            if "Playground initialized successfully!" in result.stdout:
                print("✓ Playground initialization confirmed")
            return True
        else:
            print(f"✗ Enhanced launcher failed with exit code {result.returncode}")
            if result.stdout:
                print(f"  stdout: {result.stdout}")
            if result.stderr:
                print(f"  stderr: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("✗ Enhanced launcher timed out")
        return False
    except Exception as e:
        print(f"✗ Enhanced launcher test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("=" * 60)
    print("AdaptiveCAD Playground Comprehensive Test Suite")
    print("=" * 60)
    
    tests = [
        ("Import Test", test_import),
        ("MainWindow Creation Test", test_mainwindow_creation),
        ("Demo Mode Test", test_demo_mode),
        ("Command Line Test", test_command_line),
        ("Enhanced Launcher Test", test_enhanced_launcher),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n[{passed + 1}/{total}] {test_name}")
        print("-" * 40)
        
        try:
            if test_func():
                print(f"✓ {test_name} PASSED")
                passed += 1
            else:
                print(f"✗ {test_name} FAILED")
        except Exception as e:
            print(f"✗ {test_name} FAILED with exception: {e}")
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! AdaptiveCAD playground is working correctly.")
        return 0
    else:
        print("💥 Some tests failed. Please check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())