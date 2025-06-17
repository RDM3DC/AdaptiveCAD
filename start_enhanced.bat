@echo off
REM Enhanced AdaptiveCAD start script with dependency checking

echo AdaptiveCAD startup...

REM Locate Miniconda - try various common locations
set "MCONDA=D:\Mconda"
if not exist "%MCONDA%" set "MCONDA=%USERPROFILE%\Miniconda3"
if not exist "%MCONDA%" set "MCONDA=%LOCALAPPDATA%\Continuum\Miniconda3"

if exist "%MCONDA%" (
    echo Found Miniconda at %MCONDA%
    CALL "%MCONDA%\Scripts\activate.bat" "%MCONDA%"
    CALL conda activate adaptivecad
    
    REM Check if necessary packages are installed
    echo Checking required packages...
    CALL conda list | findstr numpy > nul
    if errorlevel 1 (
        echo Installing numpy...
        CALL conda install -y -c conda-forge numpy
    ) else (
        echo numpy already installed
    )
    
    CALL conda list | findstr pyside6 > nul
    if errorlevel 1 (
        echo Installing pyside6...
        CALL conda install -y -c conda-forge pyside6
    ) else (
        echo pyside6 already installed
    )
    
    CALL conda list | findstr pythonocc-core > nul
    if errorlevel 1 (
        echo Installing pythonocc-core...
        CALL conda install -y -c conda-forge pythonocc-core
    ) else (
        echo pythonocc-core already installed
    )
    
    echo.
    echo AdaptiveCAD environment activated with dependencies.
    echo.
    echo To run the playground: python -c "from adaptivecad.gui import playground; playground.main()"
    echo To test imports:       python test_import.py
    echo.
) else (
    echo Miniconda not found at expected locations.
    echo Please ensure Miniconda is installed and update this script with its location.
    pause
    exit /b 1
)

cmd /k
