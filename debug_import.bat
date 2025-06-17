@echo off
echo Setting up AdaptiveCAD environment...

:: Use the provided activate_conda script if available
if exist "%~dp0activate_conda.ps1" (
    echo Running conda activate script...
    powershell -ExecutionPolicy Bypass -File "%~dp0activate_conda.ps1"
) else (
    echo Activate script not found, trying to use default conda...
    call conda activate adaptivecad || echo Failed to activate conda environment.
)

:: Install required packages if not already installed
echo Installing required packages...
call conda install -y -c conda-forge numpy pyside6 pythonocc-core 

:: Run the playground with verbose output
echo Running AdaptiveCAD playground...
python -c "import sys; print('Python path:', sys.path); print('Modules available:'); help('modules'); from adaptivecad.gui import playground; print('Imported playground'); win = playground.MainWindow(); print('Created MainWindow'); win._build_demo(); print('Built demo'); win.win.show(); print('Showing window'); win.app.exec()"

echo Press any key to exit...
pause
