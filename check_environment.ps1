# PowerShell script to check the AdaptiveCAD environment

# Define variables
$EnvName = "adaptivecad"

Write-Host "AdaptiveCAD Environment Diagnostic" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

# Check if conda is in the path
$condaCmd = Get-Command conda -ErrorAction SilentlyContinue
if (-not $condaCmd) {
    # Try to find conda in common locations
    $possiblePaths = @(
        "$env:USERPROFILE\Miniconda3\Scripts\conda.exe",
        "$env:USERPROFILE\Anaconda3\Scripts\conda.exe",
        "D:\Miniconda3\Scripts\conda.exe",
        "D:\Anaconda3\Scripts\conda.exe",
        "C:\Miniconda3\Scripts\conda.exe",
        "C:\Anaconda3\Scripts\conda.exe",
        "D:\Mconda\Scripts\conda.exe",
        # Try to find Miniconda in the SuperCAD directory
        "$PSScriptRoot\Miniconda3\Scripts\conda.exe"
    )
    
    $condaPath = $null
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $condaPath = $path
            break
        }
    }
    
    if (-not $condaPath) {
        Write-Host "Conda not found in PATH or common locations" -ForegroundColor Red
        Write-Host "Make sure conda is installed and in your PATH" -ForegroundColor Yellow
        Write-Host "Press any key to exit..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
    
    Write-Host "Found conda at: $condaPath" -ForegroundColor Green
    $condaCmd = $condaPath
}
else {
    $condaCmd = $condaCmd.Source
    Write-Host "Found conda in PATH: $condaCmd" -ForegroundColor Green
}

# Initialize conda for PowerShell
& $condaCmd shell.powershell hook | Out-String | Invoke-Expression

# Activate the environment
Write-Host "Activating $EnvName conda environment..." -ForegroundColor Cyan
conda activate $EnvName

# Run the diagnostic script
Write-Host "Running environment diagnostic..." -ForegroundColor Cyan
python check_environment.py

Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
