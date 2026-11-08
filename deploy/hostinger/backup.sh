#!/bin/sh
set -eu
cd "$(dirname "$0")"
backup_dir="backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$backup_dir"
chmod 700 "$backup_dir"
docker compose stop api worker
trap 'docker compose start api worker' EXIT INT TERM
docker compose exec -T database pg_dump -U postgres -Fc medflock > "$backup_dir/database.dump"
docker compose run --rm --no-deps --entrypoint tar worker -C /app/artifacts -czf - . > "$backup_dir/artifacts.tar.gz"
sha256sum "$backup_dir/database.dump" "$backup_dir/artifacts.tar.gz" > "$backup_dir/SHA256SUMS"
printf 'Backup written to %s; copy to protected off-host storage.\n' "$backup_dir"
