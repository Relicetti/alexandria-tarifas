#!/bin/bash
# Remove o autostart do agente local (desfaz o instalar_autostart.sh).
set -e

LABEL="com.alexandria.lexdash-agente"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

if [ -f "$PLIST" ]; then
  launchctl unload "$PLIST" 2>/dev/null || true
  rm "$PLIST"
  echo "✓ Autostart removido."
else
  echo "Nada instalado (arquivo $PLIST não existe)."
fi
