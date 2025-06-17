# AdaptiveCAD Terminal Starter
# This script sets up the terminal environment for AdaptiveCAD

# Navigate to the AdaptiveCAD directory
Set-Location -Path "D:\SuperCAD\AdaptiveCAD"
Write-Host "Changed directory to: $(Get-Location)" -ForegroundColor Green

# Check if conda is available
$condaCmd = Get-Command conda -ErrorAction SilentlyContinue
if (-not $condaCmd) {
    Write-Host "Conda not found in PATH. Make sure conda is installed correctly." -ForegroundColor Red
    return
}

# Initialize conda for PowerShell
& conda shell.powershell hook | Out-String | Invoke-Expression

# Activate the adaptivecad environment
Write-Host "Activating adaptivecad conda environment..." -ForegroundColor Cyan
conda activate adaptivecad

# Verify environment activation
if ($env:CONDA_DEFAULT_ENV -eq "adaptivecad") {
    Write-Host "Successfully activated adaptivecad environment" -ForegroundColor Green
    Write-Host "Python path: $(Get-Command python | Select-Object -ExpandProperty Source)" -ForegroundColor Green
    
    # Check dependencies
    Write-Host "Checking for key dependencies:" -ForegroundColor Cyan
    python -c "
import sys
try:
    import numpy
    print(f'  ✓ numpy: {numpy.__version__}')
except ImportError:
    print('  ✗ numpy: Not installed')

try:
    import PySide6
    print(f'  ✓ PySide6: {PySide6.__version__}')
except ImportError:
    print('  ✗ PySide6: Not installed')

try:
    from OCC.Core.TopoDS import TopoDS_Shape
    print('  ✓ pythonocc-core: Installed')
except ImportError:
    print('  ✗ pythonocc-core: Not installed')
"
} else {
    Write-Host "Failed to activate adaptivecad environment. Current environment: $env:CONDA_DEFAULT_ENV" -ForegroundColor Red
}

# Display helpful commands
Write-Host "`nHelpful commands:" -ForegroundColor Yellow
Write-Host "  python -m adaptivecad.gui.playground    # Start the AdaptiveCAD GUI" -ForegroundColor Yellow
Write-Host "  .\check_environment.ps1                 # Run full environment check" -ForegroundColor Yellow
Write-Host "  .\test_import.ps1                       # Test import functionality" -ForegroundColor Yellow
Write-Host "  .\start_adaptivecad.ps1                 # Start AdaptiveCAD GUI with environment setup" -ForegroundColor Yellow
