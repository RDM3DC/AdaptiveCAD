param(
    [string]$EnvName = "adaptivecad"
)
& (Join-Path $PSScriptRoot "..\..\Mconda\Scripts\conda.exe") activate $EnvName
Write-Host "Activated '$EnvName' (Python: $(Get-Command python).Source)" -ForegroundColor Green
