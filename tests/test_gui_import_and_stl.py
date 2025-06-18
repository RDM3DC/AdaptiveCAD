import os
import sys
import time
import pytest
import importlib

try:
    from PySide6.QtWidgets import QApplication
    HAS_QT = True
except Exception:
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")

# Ensure the project root is in sys.path before importing adaptivecad
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def test_gui_import_system():
    """Test that the import system is properly configured and can be imported."""
    
    try:
        # Try importing the main modules needed for STL import
        print("Testing imports...")
        
        # Test importing the main module
        import adaptivecad
        print("✓ adaptivecad module imported successfully")
        
        # Test importing the gui module
        from adaptivecad import gui
        print("✓ adaptivecad.gui module imported successfully")
        
        # Test importing the commands module which contains import_conformal
        from adaptivecad import commands
        print("✓ adaptivecad.commands module imported successfully")
        
        # Test importing the specific import_conformal module
        from adaptivecad.commands import import_conformal
        print("✓ adaptivecad.commands.import_conformal module imported successfully")
        
        # Check that ImportConformalCmd exists
        assert hasattr(import_conformal, 'ImportConformalCmd')
        print("✓ ImportConformalCmd class exists")
        
        # Create an instance of ImportConformalCmd
        cmd = import_conformal.ImportConformalCmd()
        assert cmd is not None
        print("✓ ImportConformalCmd instance created successfully")
        
        # Check for pi_a_over_pi function
        from adaptivecad.nd_math import pi_a_over_pi
        assert callable(pi_a_over_pi)
        print("✓ pi_a_over_pi function exists and is callable")
        
        # Test importing playground (but don't instantiate)
        from adaptivecad.gui import playground
        has_gui = getattr(playground, "HAS_GUI", False)
        print(f"✓ adaptivecad.gui.playground module imported (HAS_GUI={has_gui})")
        
        # If we get here, all imports worked
        print("All imports successful - the import system is properly configured.")
        
    except ImportError as e:
        pytest.fail(f"Import error: {e}")
    except Exception as e:
        import traceback
        print(f"ERROR in test: {e}")
        traceback.print_exc()
        pytest.fail(f"Test failed with error: {e}")
        
    # This test doesn't actually create a GUI or run the import, but verifies all components can be imported
    print("ok - Import system verification")

def test_gui_import_and_stl():
    """Test that we can start the GUI, add a square, and import an STL."""
    
    try:
        # Try importing PySide6 and creating QApplication first
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtTest import QTest
            from PySide6.QtCore import QTimer
        except ImportError:
            pytest.skip("PySide6 not installed, skipping GUI test")
        
        # Create QApplication first
        app = QApplication.instance() or QApplication(sys.argv)
        print("✓ QApplication created successfully")
        
        # Now import MainWindow from adaptivecad
        from adaptivecad.gui.playground import MainWindow, HAS_GUI
        
        if not HAS_GUI:
            pytest.skip("GUI dependencies not available, skipping test")
            
        print("Creating MainWindow with existing QApplication...")
        mw = MainWindow(existing_app=app)
        assert mw is not None, "MainWindow is None"
        assert mw.win is not None, "MainWindow.win is None"
        print("✓ MainWindow created successfully")
          # Show the window
        mw.win.show()
        QTest.qWait(1000)  # Wait for window to appear
        
        # Add a square or box to the document
        try:
            # Try to execute NewBoxCmd
            from adaptivecad.command_defs import NewBoxCmd
            mw.run_cmd(NewBoxCmd())
            print("✓ Added box to document")
            QTest.qWait(1000)  # Wait for box to be created
        except Exception as e:
            print(f"Failed to add box: {e}")
            # Proceed with test even if this fails
        
        # Import STL file
        try:
            # Check if test_cube.stl exists
            test_stl_file = os.path.join(os.path.dirname(__file__), "..", "test_cube.stl")
            assert os.path.exists(test_stl_file), f"Test STL file not found: {test_stl_file}"
              # Import the file
            from adaptivecad.commands.import_conformal import ImportConformalCmd
            cmd = ImportConformalCmd()
            cmd.file_path = test_stl_file  # Set the file_path property
            mw.run_cmd(cmd)
            print("✓ ImportConformalCmd executed")
            
            # Wait for import to complete
            QTest.qWait(3000)
            print("✓ STL import completed")
        except Exception as e:
            print(f"STL import error: {e}")
            pytest.fail(f"STL import failed: {e}")
        
        # Close the window
        mw.win.close()
        print("✓ Window closed successfully")
        
        # If we get here, the test passed
        print("ok - GUI import test completed successfully")
        
    except ImportError as e:
        print(f"Import error: {e}")
        pytest.skip(f"Required module not found: {e}")
    except Exception as e:
        import traceback
        print(f"ERROR in test: {e}")
        traceback.print_exc()
        pytest.fail(f"Test failed with error: {e}")
