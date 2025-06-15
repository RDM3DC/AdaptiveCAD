@echo off
REM Locate the Miniconda root – adjust if you move it
set "MCONDA=D:\Mconda"
CALL "%MCONDA%\Scripts\activate.bat" "%MCONDA%"
CALL conda activate adaptivecad
echo.
echo AdaptiveCAD environment activated.  Type 'python example_script.py' or 'pytest'.
cmd /k
