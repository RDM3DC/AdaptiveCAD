@echo off
:: Enhanced run_gui script with better Qt handling
echo Setting up environment for AdaptiveCAD...

:: First run the fix script
call fix_qt_path.bat

:: Activate conda environment
call D:\Mconda\Scripts\activate.bat adaptivecad

:: Get the correct Python site-packages path
for /f "delims=" %%i in ('python -c "import site; print(site.getsitepackages()[0])"') do set PY_SITE_PKG=%%i

:: Get the correct conda prefix and PySide6 directory
for /f "delims=" %%i in ('python -c "import sys; print(sys.prefix)"') do set CONDA_PREFIX=%%i
for /f "delims=" %%i in ('python -c "import PySide6; print(PySide6.__path__[0])"') do set PYSIDE6_DIR=%%i

echo Conda prefix: %CONDA_PREFIX%
echo PySide6 directory: %PYSIDE6_DIR%

:: Set environment variables to prioritize PySide6 directory plugins
set QT_PLUGIN_PATH=%PYSIDE6_DIR%\plugins
set QT_QPA_PLATFORM_PLUGIN_PATH=%PYSIDE6_DIR%\plugins\platforms
:: Try different platform in case windows fails
set QT_QPA_PLATFORM=windows

:: Make Qt look for plugins in both locations
set PATH=%PYSIDE6_DIR%;%PYSIDE6_DIR%\plugins\platforms;%PATH%
set PATH=%CONDA_PREFIX%\Library\bin;%CONDA_PREFIX%\Library\lib\qt6\plugins\platforms;%PATH%

:: Turn on debug output for troubleshooting
set QT_DEBUG_PLUGINS=1

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

:: Run the application
echo Starting application...
python -m adaptivecad.gui.playground
if %ERRORLEVEL% neq 0 (
    echo.
    echo Trying fallback approach with direct2d platform...
    set QT_QPA_PLATFORM=direct2d
    python -m adaptivecad.gui.playground
)

pause
