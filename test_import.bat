@echo off
echo Testing STL Import functionality
echo =================================

:: Find conda executable
set CONDA_EXE=
for %%p in (conda.exe) do (
    if not "%%~$PATH:p"=="" (
        set CONDA_EXE=%%~$PATH:p
        goto :found_conda
    )
)

:: Check common locations if not found in PATH
if exist "%USERPROFILE%\Miniconda3\Scripts\conda.exe" (
    set CONDA_EXE=%USERPROFILE%\Miniconda3\Scripts\conda.exe
    goto :found_conda
)
if exist "%USERPROFILE%\Anaconda3\Scripts\conda.exe" (
    set CONDA_EXE=%USERPROFILE%\Anaconda3\Scripts\conda.exe
    goto :found_conda
)
if exist "D:\Miniconda3\Scripts\conda.exe" (
    set CONDA_EXE=D:\Miniconda3\Scripts\conda.exe
    goto :found_conda
)
if exist "C:\Miniconda3\Scripts\conda.exe" (
    set CONDA_EXE=C:\Miniconda3\Scripts\conda.exe
    goto :found_conda
)
if exist "%~dp0Miniconda3\Scripts\conda.exe" (
    set CONDA_EXE=%~dp0Miniconda3\Scripts\conda.exe
    goto :found_conda
)

echo Conda not found in PATH or common locations
echo Make sure conda is installed and in your PATH
pause
exit /b 1

:found_conda
echo Found conda at: %CONDA_EXE%

:: Check if environment exists
echo Checking if adaptivecad environment exists...
call %CONDA_EXE% env list | findstr adaptivecad > nul
if %errorlevel% neq 0 (
    echo Environment adaptivecad not found!
    echo Creating environment from environment.yml...
    call %CONDA_EXE% env create -f environment.yml
    if %errorlevel% neq 0 (
        echo Failed to create environment from environment.yml
        pause
        exit /b 1
    )
)

:: Create a temporary batch file to run in the activated environment
echo @echo off > temp_run.bat
echo echo Running STL import test... >> temp_run.bat
echo python test_stl_import.py >> temp_run.bat
echo exit /b %%ERRORLEVEL%% >> temp_run.bat

:: Use call with conda.bat activate to ensure environment is active
echo Activating adaptivecad conda environment...
call %CONDA_EXE% activate adaptivecad && (
    :: Verify activation
    echo Activated environment:
    python -c "import sys; print(f'Python: {sys.executable}')"
    
    :: Ensure dependencies are installed
    echo Checking for required packages...
    call %CONDA_EXE% install -y -c conda-forge numpy pyside6 pythonocc-core
    
    :: Run the test script in the activated environment
    call temp_run.bat
) || (
    echo Failed to activate adaptivecad environment
    echo Make sure adaptivecad environment exists by running:
    echo     conda env create -f environment.yml
)

:: Clean up
if exist temp_run.bat del temp_run.bat

pause
