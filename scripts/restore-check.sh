#!/usr/bin/env bash
# SIMULACRO DE RESTAURACIÓN: restaura un backup en una BD temporal y comprueba su integridad.
# Un backup NO es válido hasta que este script pasa. Uso: scripts/restore-check.sh backups/archivo.dump
set -euo pipefail
FILE="${1:?Indica el archivo .dump}"
TMPDB="restore_check_$$"
psql_() { docker compose exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -v ON_ERROR_STOP=1 -tA $*"; }
cleanup() { docker compose exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d postgres -c 'DROP DATABASE IF EXISTS $TMPDB'" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker compose exec -T db sh -c "psql -U \"\$POSTGRES_USER\" -d postgres -c 'CREATE DATABASE $TMPDB'" >/dev/null
docker compose exec -T db sh -c "pg_restore -U \"\$POSTGRES_USER\" -d $TMPDB --no-owner" < "$FILE"

q() { psql_ "-d $TMPDB -c \"$1\""; }
fail() { echo "FALLO de integridad: $1" >&2; exit 1; }

[ "$(q "SELECT count(*) FROM alembic_version")" -ge 1 ] || fail "sin versión de migraciones"
[ "$(q "SELECT count(*) FROM roles")" -ge 3 ] || fail "roles ausentes"
[ "$(q "SELECT count(*) FROM commissions WHERE commission_minor + net_minor <> gross_minor")" = 0 ] || fail "comisiones incoherentes"
[ "$(q "SELECT count(*) FROM bookings b LEFT JOIN courses c ON c.id = b.course_id WHERE c.id IS NULL")" = 0 ] || fail "reservas huérfanas"
[ "$(q "SELECT count(*) FROM (SELECT course_id, user_id FROM bookings WHERE status IN ('PENDING_PAYMENT','PAYMENT_PROCESSING','PAID','PENDING_APPROVAL','CONFIRMED') GROUP BY 1,2 HAVING count(*) > 1) d")" = 0 ] || fail "reservas duplicadas"
[ "$(q "SELECT count(*) FROM (SELECT c.id FROM courses c JOIN bookings b ON b.course_id = c.id AND b.status IN ('PAID','PENDING_APPROVAL','CONFIRMED') GROUP BY c.id, c.capacity HAVING count(*) > c.capacity) s")" = 0 ] || fail "cupos sobrevendidos"
echo "Restauración OK: $(q "SELECT count(*) FROM courses") cursos, $(q "SELECT count(*) FROM bookings") reservas, $(q "SELECT count(*) FROM users") usuarios verificados."
