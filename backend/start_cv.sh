#!/bin/bash
# ==============================================================================
# start_cv.sh - Arranque del backend de Hojas de Vida
# ==============================================================================
# Lee la configuración de un archivo .env ubicado junto a este script (rutas de
# Solr, VIVO, LibreOffice y plantillas). Ese .env no se versiona: cópialo de
# .env.example y ajústalo en cada servidor.
#
# El servicio no usa clave de API: escucha solo en loopback (BIND_HOST) y el
# acceso desde el navegador entra por el proxy de Tomcat.
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: no se encontró $ENV_FILE. Créalo a partir de .env.example." >&2
    exit 1
fi

# Cargar variables del .env (export automático)
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

PORT="${PORT:-3001}"

echo "Iniciando el backend de Hojas de Vida..."
echo "  PORT:         $PORT"
echo "  BIND_HOST:    ${BIND_HOST:-127.0.0.1}"
echo "  SOFFICE_PATH: ${SOFFICE_PATH:-<no definido>}"

# Matar instancia previa si está corriendo en el puerto
PID=$(lsof -t -i:"$PORT" || true)
if [ -n "$PID" ]; then
    echo "Deteniendo instancia previa (PID: $PID)..."
    kill -9 "$PID"
    sleep 1
fi

# Arrancar en segundo plano (considera migrar a systemd para producción)
nohup python3 cv_api.py > backend.log 2>&1 &
echo "Servicio en segundo plano (PID: $!). Ver logs con: tail -f backend.log"
