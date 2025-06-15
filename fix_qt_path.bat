@echo off
:: Script to fix Qt platform plugin issues
echo Fixing Qt paths for AdaptiveCAD...

:: Activate conda environment
call D:\Mconda\Scripts\activate.bat adaptivecad

:: Get conda environment information
for /f "delims=" %%i in ('python -c "import sys; print(sys.prefix)"') do set CONDA_PREFIX=%%i
echo Conda prefix: %CONDA_PREFIX%

:: Find qt.conf in PySide6
set PYSIDE6_DIR=
for /f "delims=" %%i in ('python -c "import PySide6; print(PySide6.__path__[0])"') do set PYSIDE6_DIR=%%i
echo PySide6 directory: %PYSIDE6_DIR%

:: Create a qt.conf file to fix plugin paths
echo Creating qt.conf file...
(
echo [Paths]
echo Prefix = %CONDA_PREFIX%/Library
echo Binaries = bin
echo Libraries = lib
echo Headers = include/qt6
echo TargetSpec = win32-msvc
echo HostSpec = win32-msvc
echo Plugins = lib/qt6/plugins
echo Data = .
) > "%PYSIDE6_DIR%\qt.conf"

echo qt.conf created at %PYSIDE6_DIR%\qt.conf

:: Copy dll files if needed
if not exist "%PYSIDE6_DIR%\plugins\platforms\qwindows.dll" (
    echo Creating platforms directory...
    if not exist "%PYSIDE6_DIR%\plugins\platforms" mkdir "%PYSIDE6_DIR%\plugins\platforms"
    
    echo Copying platform plugins...
    copy "%CONDA_PREFIX%\Library\lib\qt6\plugins\platforms\qwindows.dll" "%PYSIDE6_DIR%\plugins\platforms\"
    copy "%CONDA_PREFIX%\Library\lib\qt6\plugins\platforms\qdirect2d.dll" "%PYSIDE6_DIR%\plugins\platforms\"
    copy "%CONDA_PREFIX%\Library\lib\qt6\plugins\platforms\qminimal.dll" "%PYSIDE6_DIR%\plugins\platforms\"
    copy "%CONDA_PREFIX%\Library\lib\qt6\plugins\platforms\qoffscreen.dll" "%PYSIDE6_DIR%\plugins\platforms\"
)

echo Setup completed successfully.
echo.
