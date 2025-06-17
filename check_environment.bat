@echo off
echo AdaptiveCAD Environment Diagnostic
echo ================================

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
if exist "D:\Mconda\Scripts\conda.exe" (
    set CONDA_EXE=D:\Mconda\Scripts\conda.exe
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

:: Create a temporary batch file to run in the activated environment
echo @echo off > temp_check.bat
echo python check_environment.py >> temp_check.bat
echo exit /b %%ERRORLEVEL%% >> temp_check.bat

:: Use call with conda activation to ensure environment is active
echo Activating adaptivecad conda environment...
call %CONDA_EXE% activate adaptivecad && (
    call temp_check.bat
) || (
    echo Failed to activate adaptivecad environment
    echo Make sure adaptivecad environment exists by running:
    echo     conda env create -f environment.yml
)

:: Clean up
if exist temp_check.bat del temp_check.bat

pause
