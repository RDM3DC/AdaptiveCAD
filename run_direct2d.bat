@echo off
:: Try running with Direct2D platform renderer
call D:\Mconda\Scripts\activate.bat adaptivecad

:: Get the correct conda prefix
for /f "delims=" %%i in ('python -c "import sys; print(sys.prefix)"') do set CONDA_PREFIX=%%i

:: Set Qt environment variables to use Direct2D instead of Windows
set QT_QPA_PLATFORM=direct2d
set QT_DEBUG_PLUGINS=1

:: Add all necessary directories to PATH
for /f "delims=" %%i in ('python -c "import PySide6; print(PySide6.__path__[0])"') do set PYSIDE6_DIR=%%i
set PATH=%PYSIDE6_DIR%;%PATH%
set PATH=%CONDA_PREFIX%\Library\bin;%PATH%

echo Starting AdaptiveCAD Playground GUI with Direct2D platform...
echo.
python -m adaptivecad.gui.playground
pause
