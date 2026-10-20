# Remove o autostart do agente local no Windows (desfaz instalar_autostart_windows.ps1).
$Vbs = Join-Path ([Environment]::GetFolderPath("Startup")) "alexandria-lexdash-agente.vbs"

Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*servidor_local.py*" -or $_.CommandLine -like "*iniciar_agente_windows.bat*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

if (Test-Path $Vbs) {
    Remove-Item $Vbs
    Write-Host "OK - autostart removido."
} else {
    Write-Host "Nada instalado ($Vbs não existe)."
}
