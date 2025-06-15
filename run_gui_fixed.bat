@echo off
:: Enhanced run_gui script with better Qt handling
echo Setting up environment for AdaptiveCAD...

:: Activate conda environment
call D:\Mconda\Scripts\activate.bat adaptivecad

:: Get the correct Python site-packages path
for /f "delims=" %%i in ('python -c "import site; print(site.getsitepackages()[0])"') do set PY_SITE_PKG=%%i

:: Get the correct conda prefix
for /f "delims=" %%i in ('python -c "import sys; print(sys.prefix)"') do set CONDA_PREFIX=%%i

echo Python site packages: %PY_SITE_PKG%
echo Conda prefix: %CONDA_PREFIX%

:: Set Qt environment variables properly
set QT_PLUGIN_PATH=%PY_SITE_PKG%\PySide6\plugins
set QT_QPA_PLATFORM_PLUGIN_PATH=%PY_SITE_PKG%\PySide6\plugins\platforms
set QT_QPA_PLATFORM=windows
set QT_DEBUG_PLUGINS=1

:: Add all necessary directories to PATH
set PATH=%PY_SITE_PKG%\PySide6;%PATH%
set PATH=%CONDA_PREFIX%\Library\bin;%PATH%
set PATH=%PY_SITE_PKG%\PySide6\plugins\platforms;%PATH%

echo Starting AdaptiveCAD Playground GUI...
echo.
echo Navigation:
echo   Left mouse drag: Rotate view
echo   Middle mouse drag: Pan view
echo   Mouse wheel: Zoom view
echo   Shift + Middle mouse: Fit all geometry to view
echo   Press 'R': Reload the scene during development
echo.
echo Qt plugin paths:
echo QT_PLUGIN_PATH=%QT_PLUGIN_PATH%
echo QT_QPA_PLATFORM_PLUGIN_PATH=%QT_QPA_PLATFORM_PLUGIN_PATH%
echo.

:: Run diagnostic first (optional, comment out if not needed)
echo Running Qt diagnostic...
python check_qt.py
echo.

:: Run the application
echo Starting application...
python -m adaptivecad.gui.playground
pause
