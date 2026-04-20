# Hunter StrikeR — Windows PowerShell Installer
# Usage (run in PowerShell as Administrator):
#   iwr -useb https://raw.githubusercontent.com/FreddyDeveloper/hunter-striker/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$InstallDir = "$env:USERPROFILE\.hunter-striker"
$RepoUrl = "https://github.com/FreddyDeveloper/hunter-striker.git"

Write-Host ""
Write-Host "⚡ Hunter StrikeR Installer" -ForegroundColor Cyan
Write-Host "   Free, AI-Powered Antivirus" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pyVersion = python --version 2>&1
    $versionMatch = $pyVersion -match "Python (\d+)\.(\d+)"
    if ($versionMatch) {
        $major = [int]$Matches[1]
        $minor = [int]$Matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
            Write-Host "✗ Python $major.$minor found but 3.10+ required." -ForegroundColor Red
            exit 1
        }
        Write-Host "✓ Python $major.$minor found" -ForegroundColor Green
    }
} catch {
    Write-Host "✗ Python not found. Install from https://python.org" -ForegroundColor Red
    exit 1
}

# Check Git
try {
    git --version | Out-Null
} catch {
    Write-Host "✗ Git not found. Install from https://git-scm.com" -ForegroundColor Red
    exit 1
}

# Clone or update
if (Test-Path "$InstallDir\.git") {
    Write-Host "  Updating existing installation…"
    Set-Location $InstallDir
    git pull --quiet
} else {
    Write-Host "  Downloading Hunter StrikeR…"
    git clone --quiet $RepoUrl $InstallDir
}

Set-Location $InstallDir

# Virtual environment
if (-not (Test-Path "$InstallDir\.venv")) {
    Write-Host "  Creating virtual environment…"
    python -m venv "$InstallDir\.venv"
}

& "$InstallDir\.venv\Scripts\Activate.ps1"

# Install dependencies
Write-Host "  Installing dependencies (includes Google Magika)…"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

Write-Host "✓ Dependencies installed" -ForegroundColor Green

# Create desktop shortcut
$ShortcutPath = "$env:USERPROFILE\Desktop\Hunter StrikeR.lnk"
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "$InstallDir\.venv\Scripts\python.exe"
$Shortcut.Arguments = "$InstallDir\main.py"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.Description = "Hunter StrikeR — Free AI Antivirus"
$Shortcut.Save()

Write-Host ""
Write-Host "✓ Hunter StrikeR installed!" -ForegroundColor Green
Write-Host "  A shortcut was created on your Desktop." -ForegroundColor White
Write-Host ""
Write-Host "  Hunter StrikeR is 100% free." -ForegroundColor White
Write-Host "  Voluntary donations: https://paypal.me/freddydeveloper" -ForegroundColor Cyan
Write-Host ""
