# PowerShell script to run the AdaptiveCAD Full Playground
Write-Host "Starting AdaptiveCAD Full Playground with advanced shapes and modeling tools..." -ForegroundColor Cyan

# Activate conda environment if needed
if (Test-Path "activate_conda.ps1") {
    . .\activate_conda.ps1
}

# Run the playground
python run_full_playground.py

# Wait for user input before closing
Write-Host "Press any key to continue..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
