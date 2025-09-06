# AdaptiveCAD Environment Setup

This document explains how to set up and use the AdaptiveCAD environment.

## Miniconda Setup

Miniconda is installed at `D:\Mconda` with a Python 3.10 environment named `adaptivecad`.

## Using the Environment

### Option 1: Using the Start Script (Recommended)

1. Double-click on `start_adaptivecad.bat` in the project root folder
2. This will open a command prompt with the environment activated
3. You can then run Python scripts using the `python` command

### Option 2: Using PowerShell

1. Open PowerShell
2. Navigate to the project directory:
   ```powershell
   cd C:\Users\RDM3D\SuperCAD\AdaptiveCAD
   ```
3. Run the activation script:
   ```powershell
   .\activate_conda.ps1
   ```
4. Now you can run Python scripts or tests:
   ```powershell
   python example_script.py
   python -m pytest
   ```

### Option 3: Using the Full Path to Python

You can always use the full path to the Python interpreter:

```powershell
D:\Mconda\envs\adaptivecad\python.exe example_script.py
```

## Running the GUI Playground

To run the GUI playground, use the following command:

```powershell
python -c "from adaptivecad.gui.playground import main; main()"
```

Or you can create a shortcut with this command.

### macOS (New Native Launch Script)

For macOS users a helper script has been added: `run_gui_mac.sh`.

Steps:
1. Ensure the Conda environment exists (first time only):
   ```bash
   conda env create -f environment.yml
   ```
2. Activate it:
   ```bash
   conda activate adaptivecad
   ```
3. Make sure the script is executable (only once):
   ```bash
   chmod +x run_gui_mac.sh
   ```
4. Launch the GUI:
   ```bash
   ./run_gui_mac.sh
   ```

If you encounter a Qt platform plugin error (e.g. cocoa), re-run with debug:
```bash
QT_DEBUG_PLUGINS=1 ./run_gui_mac.sh
```

Manual fallback (equivalent):
```bash
python -m adaptivecad.gui.playground
```

High‑DPI scaling tweaks (optional):
```bash
QT_AUTO_SCREEN_SCALE_FACTOR=1 QT_ENABLE_HIGHDPI_SCALING=1 ./run_gui_mac.sh
```

Software rendering (if black/blank window):
```bash
QT_OPENGL=software ./run_gui_mac.sh
```

## Installed Packages

The environment has the following packages installed:
- Python 3.10
- NumPy
- PyQt5
- PySide2
- PySide6
- matplotlib
- pythonocc-core
- pytest

## Installing Additional Packages

To install additional packages, use:

```powershell
python -m pip install package_name
```

or 

```powershell
D:\Mconda\condabin\conda.bat install -n adaptivecad package_name
```
