@echo off
:: Simple Qt test script
call D:\Mconda\Scripts\activate.bat adaptivecad

:: Get the correct Python site-packages path
for /f "delims=" %%i in ('python -c "import site; print(site.getsitepackages()[0])"') do set PY_SITE_PKG=%%i

:: Get the correct conda prefix
for /f "delims=" %%i in ('python -c "import sys; print(sys.prefix)"') do set CONDA_PREFIX=%%i

:: Set Qt environment variables properly
set QT_PLUGIN_PATH=%PY_SITE_PKG%\PySide6\plugins
set QT_QPA_PLATFORM_PLUGIN_PATH=%PY_SITE_PKG%\PySide6\plugins\platforms
set QT_QPA_PLATFORM=windows
set QT_DEBUG_PLUGINS=1

:: Add all necessary directories to PATH
set PATH=%PY_SITE_PKG%\PySide6;%PATH%
set PATH=%CONDA_PREFIX%\Library\bin;%PATH%
set PATH=%PY_SITE_PKG%\PySide6\plugins\platforms;%PATH%

echo Running simple Qt test...
python test_qt.py
pause
