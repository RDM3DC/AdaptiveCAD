@echo off
echo Testing OpenCascade availability in the AdaptiveCAD environment...
call D:\Mconda\Scripts\conda.exe run -p D:\SuperCAD\AdaptiveCAD\.conda python test_occ_availability.py
pause
