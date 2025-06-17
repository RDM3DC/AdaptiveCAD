@echo off
REM AdaptiveCAD Terminal Starter
REM This batch file sets up the terminal environment for AdaptiveCAD

REM Navigate to the AdaptiveCAD directory
cd /d "D:\SuperCAD\AdaptiveCAD"
echo Changed directory to: %cd%

REM Find conda executable
set CONDA_EXE=
for %%p in (conda.exe) do (
    if not "%%~$PATH:p"=="" (
        set CONDA_EXE=%%~$PATH:p
        goto :found_conda
    )
)

REM Check common locations if not found in PATH
if exist "%USERPROFILE%\Miniconda3\Scripts\conda.exe" (
    set CONDA_EXE=%USERPROFILE%\Miniconda3\Scripts\conda.exe
    goto :found_conda
)
if exist "%USERPROFILE%\Anaconda3\Scripts\conda.exe" (
    set CONDA_EXE=%USERPROFILE%\Anaconda3\Scripts\conda.exe
    goto :found_conda
)
if exist "D:\Miniconda3\Scripts\conda.exe" (
    set CONDA_EXE=D:\Miniconda3\Scripts\conda.exe
    goto :found_conda
)
if exist "C:\Miniconda3\Scripts\conda.exe" (
    set CONDA_EXE=C:\Miniconda3\Scripts\conda.exe
    goto :found_conda
)
if exist "D:\Mconda\Scripts\conda.exe" (
    set CONDA_EXE=D:\Mconda\Scripts\conda.exe
    goto :found_conda
)

echo Conda not found in PATH or common locations
echo Make sure conda is installed correctly.
exit /b 1

:found_conda
echo Found conda at: %CONDA_EXE%

REM Activate the adaptivecad environment
echo Activating adaptivecad conda environment...
call %CONDA_EXE% activate adaptivecad

REM Verify environment activation and check dependencies
echo.
echo Checking for key dependencies:
python -c "
import sys
try:
    import numpy
    print(f'  ✓ numpy: {numpy.__version__}')
except ImportError:
    print('  ✗ numpy: Not installed')

try:
    import PySide6
    print(f'  ✓ PySide6: {PySide6.__version__}')
except ImportError:
    print('  ✗ PySide6: Not installed')

try:
    from OCC.Core.TopoDS import TopoDS_Shape
    print('  ✓ pythonocc-core: Installed')
except ImportError:
    print('  ✗ pythonocc-core: Not installed')
"

REM Display helpful commands
echo.
echo Helpful commands:
echo   python -m adaptivecad.gui.playground    # Start the AdaptiveCAD GUI
echo   check_environment.bat                   # Run full environment check
echo   test_import.bat                         # Test import functionality
echo   start_adaptivecad.bat                   # Start AdaptiveCAD GUI with environment setup

echo.
echo AdaptiveCAD environment is ready.
