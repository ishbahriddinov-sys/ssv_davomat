#!/usr/bin/env bash
# Резервное копирование базы данных PostgreSQL (pg_dump).
set -euo pipefail

source .env 2>/dev/null || true

TS=$(date +%Y%m%d_%H%M%S)
DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$DIR"
OUT="$DIR/attendance_${TS}.sql.gz"

echo "Создание резервной копии -> $OUT"
docker compose exec -T db pg_dump \
  -U "${POSTGRES_USER:-attendance}" \
  "${POSTGRES_DB:-attendance}" | gzip > "$OUT"

# Ротация: хранить последние 14 копий
ls -1t "$DIR"/attendance_*.sql.gz | tail -n +15 | xargs -r rm --
echo "Готово. Копий в каталоге: $(ls -1 "$DIR"/attendance_*.sql.gz | wc -l)"
