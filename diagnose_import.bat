@echo off
TITLE AdaptiveCAD Import Diagnostics

echo AdaptiveCAD Import Diagnostics
echo ==================================
echo.

:: Test accessing the environment
echo Testing conda environment...
call conda info

echo.
echo Checking Python version:
python --version

echo.
echo Checking required packages:
echo.
echo NumPy:
python -c "try: import numpy; print('SUCCESS: NumPy available, version:', numpy.__version__); except ImportError: print('ERROR: NumPy not installed')"

echo.
echo PySide6:
python -c "try: from PySide6 import QtCore; print('SUCCESS: PySide6 available, version:', QtCore.__version__); except ImportError: print('ERROR: PySide6 not installed')"

echo.
echo PythonOCC:
python -c "try: from OCC import VERSION; print('SUCCESS: PythonOCC available, version:', VERSION); except ImportError: print('ERROR: PythonOCC not installed')"

echo.
echo Testing import of essential modules:
python -c "try: from adaptivecad.commands.import_conformal import ImportConformalCmd; print('SUCCESS: ImportConformalCmd imported successfully'); except Exception as e: print('ERROR:', e)"

echo.
echo Testing AdaptiveCAD paths:
python -c "import sys; print('Python path:'); [print(' -', p) for p in sys.path]"

echo.
echo Diagnosing ImportConformalCmd:
python -c "import traceback; try: from adaptivecad.commands.import_conformal import ImportConformalCmd; cmd = ImportConformalCmd(); print('Command created successfully'); except Exception as e: print('Error:', e); print(traceback.format_exc())"

echo.
echo Diagnostics complete.
echo ==================================
echo.
echo If errors were found, try installing the missing packages:
echo     conda install -c conda-forge numpy pyside6 pythonocc-core
echo.
echo Or use the included debug_import.bat script.
echo.
pause
