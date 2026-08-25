#!/bin/bash
# Instala o agente local para iniciar sozinho a cada login no Mac (LaunchAgent),
# rodando em segundo plano — sem precisar abrir Terminal para usar o botão
# "Gravar no LexDash" do dashboard.
#
# Uso (dentro da pasta agente_local, com o venv já criado):
#   ./instalar_autostart.sh
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$DIR/.venv/bin/python"
LABEL="com.alexandria.lexdash-agente"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$DIR/agente.log"

if [ ! -x "$PYTHON" ]; then
  echo "venv não encontrado em $PYTHON."
  echo "Rode primeiro: python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [ ! -f "$DIR/.env" ]; then
  echo "Aviso: $DIR/.env não existe ainda (TARIFAS_API_URL / ADMIN_TOKEN)."
  echo "Crie-o antes de instalar — veja o README.md."
  exit 1
fi

if [ ! -f "$DIR/cert.pem" ] || [ ! -f "$DIR/key.pem" ]; then
  echo "Aviso: cert.pem/key.pem não existem — instalando mesmo assim, o agente vai"
  echo "rodar em HTTP simples (funciona com o dashboard em produção hoje / Chrome)."
  echo "Para habilitar HTTPS (necessário para Safari) depois:"
  echo "  mkcert -install && mkcert -cert-file cert.pem -key-file key.pem localhost 127.0.0.1 ::1"
  echo "  launchctl kickstart -k gui/\$(id -u)/com.alexandria.lexdash-agente"
fi

if [ ! -f "$DIR/lexdash_session.json" ]; then
  echo "Aviso: lexdash_session.json não existe ainda."
  echo "Rode 'python login_lexdash.py' primeiro para salvar sua sessão do LexDash."
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON</string>
        <string>-u</string>
        <string>$DIR/servidor_local.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONUNBUFFERED</key>
        <string>1</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$LOG</string>
    <key>StandardErrorPath</key>
    <string>$LOG</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"

echo "✓ Agente instalado e rodando em segundo plano."
echo "  Vai subir sozinho sempre que você fizer login no Mac — nada de Terminal."
echo "  Log em: $LOG"
echo ""
echo "Para reiniciar agora (ex.: depois de um git pull):"
echo "  launchctl kickstart -k gui/\$(id -u)/$LABEL"
echo ""
echo "Para desinstalar:"
echo "  ./desinstalar_autostart.sh"
