#!/usr/bin/env bash
# Backup lógico de PostgreSQL (formato custom, comprimido). Uso: scripts/backup.sh [directorio]
set -euo pipefail
OUT_DIR="${1:-backups}"
mkdir -p "$OUT_DIR"
FILE="$OUT_DIR/tallerya-$(date -u +%Y%m%dT%H%M%SZ).dump"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$FILE"
echo "Backup creado: $FILE ($(wc -c < "$FILE") bytes)"
