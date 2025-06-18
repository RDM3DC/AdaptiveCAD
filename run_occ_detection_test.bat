@echo off
echo Testing OpenCascade detection in AdaptiveCAD...
call D:\poth\condabin\conda.bat run -p D:\SuperCAD\AdaptiveCAD\.conda python test_occ_detection.py
pause
