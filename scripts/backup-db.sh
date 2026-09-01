#!/usr/bin/env sh
# Dump every database (master + all tenants) plus roles, gzipped.
#   ./scripts/backup-db.sh [output-dir]
# Restore: gunzip -c FILE.sql.gz | docker compose -f docker-compose.prod.yml \
#          --env-file .env.prod exec -T postgres psql -U "$POSTGRES_USER"
set -eu

OUT_DIR=${1:-./backups}
STAMP=$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT_DIR"

docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T postgres \
	sh -c 'pg_dumpall -U "$POSTGRES_USER"' | gzip >"$OUT_DIR/apexwms-$STAMP.sql.gz"

echo "wrote $OUT_DIR/apexwms-$STAMP.sql.gz"
