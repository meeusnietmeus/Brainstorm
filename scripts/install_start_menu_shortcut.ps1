# Creates (or refreshes) a Start menu shortcut that launches Brainstorm from this checkout's venv.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\install_start_menu_shortcut.ps1 [-Remove]
param([switch]$Remove)

$root = Split-Path -Parent $PSScriptRoot
$shortcut = Join-Path ([Environment]::GetFolderPath("Programs")) "Brainstorm.lnk"

if ($Remove) {
    Remove-Item $shortcut -ErrorAction SilentlyContinue
    Write-Host "Removed $shortcut"
    return
}

$pythonw = Join-Path $root ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    throw "Missing $pythonw. Create the venv first (see README)."
}

$link = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcut)
$link.TargetPath = $pythonw          # pythonw: no console window
$link.Arguments = "-m brainstorm"
$link.WorkingDirectory = $root
$link.Description = "Brainstorm"
$link.Save()
Write-Host "Created $shortcut"
