@echo off
:: Set the environment variables for Qt plugins
for /f "delims=" %%i in ('pip show pyside6 ^| findstr "Location"') do set PY_SITE_PKG=%%i
set PY_SITE_PKG=%PY_SITE_PKG:~10%
set QT_PLUGIN_PATH=%PY_SITE_PKG%\PySide6\plugins
set QT_QPA_PLATFORM_PLUGIN_PATH=%PY_SITE_PKG%\PySide6\plugins\platforms
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
call D:\Mconda\Scripts\activate.bat adaptivecad
python -m adaptivecad.gui.playground
pause
