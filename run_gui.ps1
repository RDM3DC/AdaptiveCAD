Write-Host "Running AdaptiveCAD GUI Playground..." -ForegroundColor Cyan

# Locate conda
$condaPath = "D:\poth\condabin\conda.bat"

if (Test-Path $condaPath) {
    Write-Host "Found conda at: $condaPath" -ForegroundColor Green
    
    # Run the GUI with proper environment
    Write-Host "Starting AdaptiveCAD GUI..." -ForegroundColor Yellow
    & $condaPath run -p "D:\SuperCAD\AdaptiveCAD\.conda" python -m adaptivecad.gui.playground
} else {
    Write-Host "Could not find conda at: $condaPath" -ForegroundColor Red
    Write-Host "Please check the conda installation path." -ForegroundColor Red
}
