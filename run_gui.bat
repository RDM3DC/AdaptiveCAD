@echo off
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
