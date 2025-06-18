"""
Start script for AdaptiveCAD GUI with proper environment
"""
import os
import sys
import subprocess

def main():
    print("Starting AdaptiveCAD GUI...")
    
    # Get conda executable path
    conda_path = "D:\\poth\\condabin\\conda.bat"
    if not os.path.exists(conda_path):
        print(f"Error: Conda not found at {conda_path}")
        return 1
    
    # Define Python script to execute
    script = "adaptivecad.gui.playground"
    
    # Get conda environment path
    env_path = os.path.join(os.path.dirname(__file__), ".conda")
    if not os.path.exists(env_path):
        print(f"Error: Conda environment not found at {env_path}")
        return 1
    
    # Construct the command
    cmd = [conda_path, "run", "-p", env_path, "python", "-m", script]
    
    # Run the command
    print(f"Running command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd)
        return 0
    except Exception as e:
        print(f"Error running command: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
