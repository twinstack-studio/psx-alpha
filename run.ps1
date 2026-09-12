<#
    One-command setup and launch for the PSX Alpha research engine.

        .\run.ps1              build everything, then serve API + dashboard
        .\run.ps1 -SkipData    reuse the existing database and exports
        .\run.ps1 -Dashboard   dashboard only, no API
        .\run.ps1 -Rebuild     drop the database and rebuild from scratch

    Requires Python 3.12 and Node.js 20+.
#>
param(
    [switch]$SkipData,
    [switch]$Dashboard,
    [switch]$Rebuild
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$python = Join-Path $backend ".venv\Scripts\python.exe"

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }

# ---------------------------------------------------------------- backend ---
if (-not (Test-Path $python)) {
    Step "Creating the Python 3.12 virtual environment"
    & py -3.12 -m venv (Join-Path $backend ".venv")
    if (-not (Test-Path $python)) { throw "Python 3.12 not found. Install it, or point `$python at another interpreter." }
    & $python -m pip install --quiet --upgrade pip
    Step "Installing Python dependencies (this takes a few minutes the first time)"
    & $python -m pip install -r (Join-Path $backend "requirements.txt")
}

Push-Location $backend
try {
    $db = Join-Path $backend "data\psx.db"
    if ($Rebuild -or (-not $SkipData -and -not (Test-Path $db))) {
        Step "Building the point-in-time dataset"
        & $python -m scripts.build_dataset --reset
    }

    $bundle = Join-Path $backend "data\exports\dashboard.json"
    if ($Rebuild -or (-not $SkipData) -or (-not (Test-Path $bundle))) {
        Step "Running the analysis pipeline: ratios, backtest, scores, exports"
        & $python -m scripts.run_pipeline
    }
}
finally { Pop-Location }

# --------------------------------------------------------------- frontend ---
Push-Location $frontend
try {
    if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
        Step "Installing Node dependencies"
        & npm install
    }
    Step "Syncing the analysis bundle into the dashboard"
    & npm run sync-data
}
finally { Pop-Location }

# ------------------------------------------------------------------ serve ---
if (-not $Dashboard) {
    Step "Starting the REST API on http://localhost:8000  (docs at /docs)"
    Start-Process -FilePath $python `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--port", "8000" `
        -WorkingDirectory $backend
}

Step "Starting the dashboard on http://localhost:3000"
Write-Host "Press Ctrl+C to stop.`n" -ForegroundColor DarkGray
Push-Location $frontend
try { & npm run dev }
finally { Pop-Location }
