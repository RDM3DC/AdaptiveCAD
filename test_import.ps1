# PowerShell script to test STL import functionality

# Define variables
$EnvName = "adaptivecad"
$TestScript = "test_stl_import.py"

Write-Host "Testing STL Import functionality" -ForegroundColor Cyan
Write-Host "=================================" -ForegroundColor Cyan

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

# First check if environment exists
Write-Host "Checking if $EnvName environment exists..." -ForegroundColor Cyan
$envList = & $condaCmd env list
if ($envList -notmatch $EnvName) {
    Write-Host "Environment $EnvName not found!" -ForegroundColor Red
    Write-Host "Creating environment from environment.yml..." -ForegroundColor Yellow
    & $condaCmd env create -f environment.yml
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create environment from environment.yml" -ForegroundColor Red
        Write-Host "Press any key to exit..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    }
}

# Activate the environment and run the test script
Write-Host "Activating $EnvName conda environment..." -ForegroundColor Cyan

# Initialize conda for PowerShell
& $condaCmd shell.powershell hook | Out-String | Invoke-Expression

# Activate the environment
conda activate $EnvName

# Check if activation was successful
if ($env:CONDA_PROMPT_MODIFIER -notmatch $EnvName) {
    Write-Host "Failed to activate $EnvName environment" -ForegroundColor Red
    Write-Host "Press any key to exit..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

Write-Host "Successfully activated $EnvName environment" -ForegroundColor Green
Write-Host "Python path: $(Get-Command python | Select-Object -ExpandProperty Source)" -ForegroundColor Green

# Ensure dependencies are installed
Write-Host "Checking for required packages..." -ForegroundColor Cyan
conda install -y -c conda-forge numpy pyside6 pythonocc-core

# Run the test script
Write-Host "Running STL import test..." -ForegroundColor Cyan
python $TestScript

Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
