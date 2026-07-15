$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PortableExe = Join-Path $ScriptDir "dist\APE\APE.exe"
$SourceBat = Join-Path $ScriptDir "run_ape.bat"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "APE.lnk"

if (Test-Path $PortableExe) {
    $TargetPath = $PortableExe
    $WorkingDirectory = Split-Path -Parent $PortableExe
} elseif (Test-Path $SourceBat) {
    $TargetPath = $SourceBat
    $WorkingDirectory = $ScriptDir
} else {
    throw "Khong tim thay dist\APE\APE.exe hoac run_ape.bat."
}

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetPath
$Shortcut.WorkingDirectory = $WorkingDirectory
$Shortcut.Description = "APE - Adaptive Prediction Engine"
if (Test-Path $PortableExe) {
    $Shortcut.IconLocation = "$PortableExe,0"
}
$Shortcut.Save()

Write-Host "Da tao shortcut:" $ShortcutPath
