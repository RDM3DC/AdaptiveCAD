"""
Qt diagnostic script to check if PySide6 is correctly installed and platform plugins are available.
"""
import sys
import os

def check_qt_setup():
    print("Python version:", sys.version)
    print("System path:", sys.path)
    
    # Try importing PySide6
    print("\nChecking PySide6 import...")
    try:
        import PySide6
        print("PySide6 imported successfully!")
        print("PySide6 version:", PySide6.__version__)
        print("PySide6 location:", PySide6.__file__)
        
        # Check Qt plugin paths
        from PySide6.QtCore import QCoreApplication
        print("\nQt plugin paths:")
        print(QCoreApplication.libraryPaths())
        
        # Show environment variables
        print("\nRelevant environment variables:")
        print("QT_PLUGIN_PATH:", os.environ.get("QT_PLUGIN_PATH", "Not set"))
        print("QT_QPA_PLATFORM_PLUGIN_PATH:", os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH", "Not set"))
        print("QT_QPA_PLATFORM:", os.environ.get("QT_QPA_PLATFORM", "Not set"))
        
        # List contents of the plugins directory
        try:
            plugin_path = os.path.join(os.path.dirname(PySide6.__file__), "plugins")
            platform_path = os.path.join(plugin_path, "platforms")
            
            print("\nChecking plugin directory:", plugin_path)
            if os.path.exists(plugin_path):
                print("Plugin directory exists. Contents:")
                print(os.listdir(plugin_path))
            else:
                print("Plugin directory does not exist!")
                
            print("\nChecking platforms directory:", platform_path)
            if os.path.exists(platform_path):
                print("Platforms directory exists. Contents:")
                print(os.listdir(platform_path))
                
                # Check for windows.dll specifically
                windows_dll = os.path.join(platform_path, "qwindows.dll")
                if os.path.exists(windows_dll):
                    print("\nqwindows.dll exists at:", windows_dll)
                    print("File size:", os.path.getsize(windows_dll), "bytes")
                else:
                    print("\nWARNING: qwindows.dll not found!")
            else:
                print("Platforms directory does not exist!")
                
        except Exception as e:
            print("Error checking plugin directories:", e)
    
    except ImportError as e:
        print("Failed to import PySide6:", e)
        
    # Check if Visual C++ Redistributable DLLs are available
    print("\nChecking for critical DLLs in PATH:")
    critical_dlls = ["VCRUNTIME140.dll", "MSVCP140.dll", "VCRUNTIME140_1.dll"]
    for dll in critical_dlls:
        found = False
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            if os.path.exists(os.path.join(path_dir, dll)):
                print(f"{dll} found in {path_dir}")
                found = True
                break
        if not found:
            print(f"WARNING: {dll} not found in PATH!")

if __name__ == "__main__":
    check_qt_setup()
