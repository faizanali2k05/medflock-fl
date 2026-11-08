#!/bin/sh
set -eu
cd "$(dirname "$0")"
port=${1:-18088}
case "$port" in *[!0-9]*|"") echo "Expected a numeric port" >&2; exit 2;; esac
docker compose config --quiet
docker compose ps
curl --fail --silent --show-error http://127.0.0.1:${port}/health/ready
printf '\nAnonymous GraphQL must return 401: '
status=$(curl --silent --output /dev/null --write-out '%{http_code}' -H 'Content-Type: application/json' --data '{"query":"{ runs { id } }"}' http://127.0.0.1:${port}/graphql)
printf '%s\n' "$status"
test "$status" = 401
