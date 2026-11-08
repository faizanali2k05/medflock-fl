#!/bin/sh
set -eu
printf 'SYSTEM\n'
uname -sr
printf 'AVAILABLE MEMORY\n'
free -m
printf 'DISK\n'
df -Pk / /opt
printf 'LISTENING TCP PORTS\n'
ss -ltn
printf 'DOCKER VERSION\n'
docker version --format '{{.Server.Version}}'
printf 'EXISTING CONTAINERS\n'
docker ps --format '{{.Names}} {{.Image}} {{.Ports}}'
printf 'COMPOSE VERSION\n'
docker compose version
printf 'MEDFLOCK TARGET\n'
if test -e /opt/medflock; then ls -ld /opt/medflock; else printf 'Not present\n'; fi
