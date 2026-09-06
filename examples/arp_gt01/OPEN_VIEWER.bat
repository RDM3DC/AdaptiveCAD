@echo off
if not exist "%~dp0ARP_GT01_Viewer.html" (
    echo Run build_viewer.py first to generate ARP_GT01_Viewer.html.
    exit /b 1
)
start "" "%~dp0ARP_GT01_Viewer.html"
