"""Test that MainWindow can be imported and run."""

import sys
import os

# Add project root to path
script_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, script_dir)

print("Importing MainWindow from adaptivecad.gui.playground...")
try:
    from adaptivecad.gui.playground import MainWindow
    print("✅ MainWindow imported successfully")
except ImportError as e:
    print(f"❌ Error importing MainWindow: {e}")
    sys.exit(1)

if __name__ == "__main__":
    print("Starting AdaptiveCAD GUI...")
    try:
        app = MainWindow()
        print("✅ MainWindow instance created")
        result = app.run()
        print(f"✅ AdaptiveCAD GUI closed with result: {result}")
    except Exception as e:
        print(f"❌ Error running MainWindow: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
