@echo off
:: Set the environment variables for Qt plugins
call D:\Mconda\Scripts\activate.bat adaptivecad
:: Get the correct Python site-packages path
for /f "delims=" %%i in ('python -c "import site; print(site.getsitepackages()[0])"') do set PY_SITE_PKG=%%i
:: Set Qt environment variables correctly
set QT_PLUGIN_PATH=%PY_SITE_PKG%\PySide6\plugins
set QT_QPA_PLATFORM_PLUGIN_PATH=%PY_SITE_PKG%\PySide6\plugins\platforms
:: Force Qt to use the Windows platform plugin
set QT_QPA_PLATFORM=windows
:: Add both PySide6 directories to PATH
set PATH=%PY_SITE_PKG%\PySide6;%PY_SITE_PKG%\PySide6\plugins\platforms;%PATH%
:: Make sure we have Visual C++ redistributable DLLs in the path
set PATH=D:\Mconda\envs\adaptivecad\Library\bin;%PATH%

echo Starting AdaptiveCAD Playground GUI...
echo.
echo Navigation:
echo   Left mouse drag: Rotate view
echo   Middle mouse drag: Pan view
echo   Mouse wheel: Zoom view
echo   Shift + Middle mouse: Fit all geometry to view
echo   Press 'R': Reload the scene during development
echo.
:: No need to activate again, already done above
echo Qt plugin paths:
echo QT_PLUGIN_PATH=%QT_PLUGIN_PATH%
echo QT_QPA_PLATFORM_PLUGIN_PATH=%QT_QPA_PLATFORM_PLUGIN_PATH%
python -m adaptivecad.gui.playground
pause
