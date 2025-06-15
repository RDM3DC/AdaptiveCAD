@echo off
echo Repairing PySide6 installation...

:: Activate conda environment
call D:\Mconda\Scripts\activate.bat adaptivecad

:: Uninstall and reinstall PySide6
echo Uninstalling PySide6...
pip uninstall -y pyside6
conda uninstall -y pyside6
echo.

echo Reinstalling PySide6...
conda install -y pyside6
echo.

echo Repair completed. Please try running the application again.
pause
