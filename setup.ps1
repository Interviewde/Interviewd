# ══════════════════════════════════════════════════════════════════
#  Interviewd — one-shot setup script for Windows (PowerShell)
#  Run this once after cloning:
#
#      Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#      .\setup.ps1
#
#  Installs: uv → Python 3.11 → Node.js → Python deps → frontend deps
#  Then hands off to `interviewd setup` for API key configuration.
# ══════════════════════════════════════════════════════════════════
#Requires -Version 5.1
$ErrorActionPreference = "Stop"

# ── Helpers ───────────────────────────────────────────────────────

function Write-Ok($msg)   { Write-Host "  " -NoNewline; Write-Host "v" -ForegroundColor Green -NoNewline; Write-Host "  $msg" }
function Write-Fail($msg) { Write-Host "  " -NoNewline; Write-Host "x" -ForegroundColor Red -NoNewline; Write-Host "  $msg" }
function Write-Info($msg) { Write-Host "     $msg" }
function Write-Step($msg) {
    Write-Host ""
    Write-Host $msg -ForegroundColor White
    Write-Host ("─" * 52)
}

function Confirm-Step($prompt) {
    $ans = Read-Host "     $prompt [Y/n]"
    return ($ans -eq "" -or $ans -match "^[Yy]")
}

function Refresh-EnvPath {
    $env:PATH = `
        [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + `
        [System.Environment]::GetEnvironmentVariable("Path", "User")
}

function Assert-LastOk($msg) {
    if ($LASTEXITCODE -ne 0) {
        Write-Fail $msg
        exit 1
    }
}

# ── Banner ────────────────────────────────────────────────────────

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoDir

Write-Host ""
Write-Host "══════════════════════════════════════════════════════"
Write-Host "  Interviewd Setup"
Write-Host "══════════════════════════════════════════════════════"

# ── Step 1: uv ────────────────────────────────────────────────────
Write-Step "[1/5] uv  (Python toolchain manager)"

if (Get-Command uv -ErrorAction SilentlyContinue) {
    $uvVer = (uv --version) -replace "uv ", ""
    Write-Ok "uv $uvVer"
} else {
    Write-Fail "uv not found"
    Write-Info "Official installer: https://docs.astral.sh/uv/"
    if (Confirm-Step "Install uv now?") {
        irm https://astral.sh/uv/install.ps1 | iex
        Refresh-EnvPath
        if (Get-Command uv -ErrorAction SilentlyContinue) {
            Write-Ok "uv installed"
        } else {
            Write-Fail "uv installed but not in PATH yet"
            Write-Info "Restart PowerShell and re-run: .\setup.ps1"
            exit 1
        }
    } else {
        Write-Fail "uv is required — install from https://docs.astral.sh/uv/ and re-run"
        exit 1
    }
}

# ── Step 2: Python 3.11+ ──────────────────────────────────────────
Write-Step "[2/5] Python 3.11+"

$pyOk = $false
if (Get-Command python -ErrorAction SilentlyContinue) {
    $pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
    if ($pyVer -match "^(\d+)\.(\d+)") {
        if ([int]$Matches[1] -ge 3 -and [int]$Matches[2] -ge 11) {
            Write-Ok "Python $pyVer"
            $pyOk = $true
        }
    }
}

if (-not $pyOk) {
    Write-Fail "Python 3.11+ not found"
    Write-Info "uv can install and manage Python versions for you"
    if (Confirm-Step "Install Python 3.11 via uv?") {
        uv python install 3.11
        Assert-LastOk "Failed to install Python 3.11"
        Write-Ok "Python 3.11 installed"
    } else {
        Write-Fail "Python 3.11+ is required — install from https://python.org/downloads and re-run"
        exit 1
    }
}

# ── Step 3: Node.js ───────────────────────────────────────────────
Write-Step "[3/5] Node.js + npm"

$nodeOk = (Get-Command node -ErrorAction SilentlyContinue) -and (Get-Command npm -ErrorAction SilentlyContinue)

if ($nodeOk) {
    Write-Ok "node $(node --version)  •  npm $(npm --version)"
} else {
    Write-Fail "node / npm not found"
    Write-Info "Will run: winget install --id OpenJS.NodeJS.LTS -e"
    if (Confirm-Step "Install Node.js via winget?") {
        winget install --id OpenJS.NodeJS.LTS -e
        Refresh-EnvPath
        if (Get-Command node -ErrorAction SilentlyContinue) {
            Write-Ok "node $(node --version)  •  npm $(npm --version)"
        } else {
            Write-Fail "Node.js installed but not in PATH yet"
            Write-Info "Restart PowerShell and re-run: .\setup.ps1"
            exit 1
        }
    } else {
        Write-Fail "Node.js is required — install from https://nodejs.org and re-run"
        exit 1
    }
}

# ── Step 4: Python deps ───────────────────────────────────────────
Write-Step "[4/5] Python dependencies"
Write-Info "uv sync --extra web"
uv sync --extra web
Assert-LastOk "uv sync failed — check output above"
Write-Ok "Python deps ready"

# ── Step 5: Frontend deps ─────────────────────────────────────────
Write-Step "[5/5] Frontend dependencies"
Write-Info "npm install  (frontend/)"
Push-Location frontend
npm install
Pop-Location
Assert-LastOk "npm install failed — check output above"
Write-Ok "Frontend deps ready"

# ── Hand off to API key wizard ────────────────────────────────────
Write-Host ""
Write-Host "══════════════════════════════════════════════════════"
Write-Ok "System setup complete"
Write-Host "══════════════════════════════════════════════════════"
Write-Host ""

uv run interviewd setup
