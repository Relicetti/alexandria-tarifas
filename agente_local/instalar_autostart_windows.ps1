# Instala o agente local para iniciar sozinho a cada login no Windows,
# escondido em segundo plano (equivale ao instalar_autostart.sh do Mac).
#
# Uso (PowerShell, dentro da pasta agente_local, com o venv já criado):
#   powershell -ExecutionPolicy Bypass -File .\instalar_autostart_windows.ps1
$ErrorActionPreference = "Stop"

$Dir = $PSScriptRoot
$Python = Join-Path $Dir ".venv\Scripts\python.exe"
$Bat = Join-Path $Dir "iniciar_agente_windows.bat"
$Vbs = Join-Path ([Environment]::GetFolderPath("Startup")) "alexandria-lexdash-agente.vbs"

if (-not (Test-Path $Python)) {
    Write-Host "venv não encontrado em $Python."
    Write-Host "Rode primeiro: py -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
    exit 1
}
if (-not (Test-Path (Join-Path $Dir ".env"))) {
    Write-Host "Aviso: .env não existe ainda (TARIFAS_API_URL / ADMIN_TOKEN). Crie-o antes - veja o README.md."
    exit 1
}
if (-not (Test-Path (Join-Path $Dir "cert.pem")) -or -not (Test-Path (Join-Path $Dir "key.pem"))) {
    Write-Host "Aviso: cert.pem/key.pem não existem - o agente vai rodar em HTTP simples e o dashboard"
    Write-Host "(https) não consegue chamá-lo. Gere com:"
    Write-Host "  mkcert -install; mkcert -cert-file cert.pem -key-file key.pem localhost 127.0.0.1 ::1"
}
if (-not (Test-Path (Join-Path $Dir "lexdash_session.json"))) {
    Write-Host "Aviso: lexdash_session.json não existe ainda."
    Write-Host "Rode '.venv\Scripts\python login_lexdash.py' primeiro para salvar a sessão do LexDash."
    exit 1
}

# VBS na pasta Inicializar roda o .bat sem abrir janela de console.
Set-Content -Path $Vbs -Encoding ASCII -Value "CreateObject(""WScript.Shell"").Run """"""$Bat"""""", 0, False"

# Derruba uma instância antiga (se houver) e sobe a nova agora.
Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -like "*servidor_local.py*" -or $_.CommandLine -like "*iniciar_agente_windows.bat*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Process wscript.exe -ArgumentList "`"$Vbs`""

Write-Host "OK - agente instalado e rodando em segundo plano."
Write-Host "  Vai subir sozinho sempre que você fizer login no Windows."
Write-Host "  Log em: $(Join-Path $Dir 'agente.log')"
Write-Host ""
Write-Host "Para reiniciar (ex.: depois de atualizar o código): rode este script de novo."
Write-Host "Para desinstalar: powershell -ExecutionPolicy Bypass -File .\desinstalar_autostart_windows.ps1"
