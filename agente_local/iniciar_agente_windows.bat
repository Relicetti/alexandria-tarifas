@echo off
rem Sobe o agente local no Windows e o reinicia se cair (equivale ao KeepAlive
rem do LaunchAgent no Mac). Chamado escondido pelo atalho da pasta Inicializar,
rem criado por instalar_autostart_windows.ps1.
cd /d "%~dp0"
set PYTHONUNBUFFERED=1
set PYTHONUTF8=1
:loop
".venv\Scripts\python.exe" -u servidor_local.py >> agente.log 2>&1
timeout /t 5 /nobreak > nul
goto loop
