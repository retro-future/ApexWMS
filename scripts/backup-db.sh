#!/usr/bin/env sh
# Dump every database (master + all tenants) plus roles, gzipped, then
# delete backups older than RETENTION_DAYS.
#   ./scripts/backup-db.sh [output-dir]
#   RETENTION_DAYS=14 ./scripts/backup-db.sh
# Restore: gunzip -c FILE.sql.gz | docker compose -f docker-compose.prod.yml \
#          --env-file .env.prod exec -T postgres psql -U "$POSTGRES_USER"
set -eu

OUT_DIR=${1:-./backups}
RETENTION_DAYS=${RETENTION_DAYS:-7}
STAMP=$(date +%Y%m%d-%H%M%S)
FINAL_FILE="$OUT_DIR/apexwms-$STAMP.sql.gz"
TMP_FILE="$FINAL_FILE.tmp"

log() {
	echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

cleanup() {
	rm -f "$TMP_FILE"
}
trap cleanup EXIT

mkdir -p "$OUT_DIR"

log "starting dump -> $FINAL_FILE"

# dump to a temp file first: set -eu alone won't catch a failed pg_dumpall
# once it's piped into gzip, since the pipeline's exit status is gzip's.
if ! docker compose -f docker-compose.prod.yml --env-file .env.prod exec -T postgres \
	sh -c 'pg_dumpall -U "$POSTGRES_USER"' >"$TMP_FILE"; then
	log "ERROR: pg_dumpall failed, aborting (no backup written)"
	exit 1
fi

if [ ! -s "$TMP_FILE" ]; then
	log "ERROR: dump is empty, aborting (no backup written)"
	exit 1
fi

gzip -c "$TMP_FILE" >"$FINAL_FILE"
trap - EXIT
rm -f "$TMP_FILE"

log "wrote $FINAL_FILE ($(du -h "$FINAL_FILE" | cut -f1))"

log "rotating backups older than $RETENTION_DAYS days in $OUT_DIR"
find "$OUT_DIR" -name 'apexwms-*.sql.gz' -type f -mtime "+$RETENTION_DAYS" -print -delete |
	while IFS= read -r removed; do log "removed $removed"; done

log "done"
