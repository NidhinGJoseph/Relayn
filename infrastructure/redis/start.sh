#!/bin/sh
set -eu
# Hex-only generated secret can be safely included in a Redis configuration.
password="$(cat /run/secrets/redis_password)"
case "$password" in
  ''|*[!0-9a-f]*) echo "Redis secret must be a generated hexadecimal password" >&2; exit 1 ;;
esac
umask 077
printf 'bind 0.0.0.0\nprotected-mode yes\nrequirepass %s\ndir /data\nappendonly yes\nappendfsync everysec\n' "$password" > /tmp/relayn-redis.conf
unset password
chown redis:redis /tmp/relayn-redis.conf
# The official entrypoint fixes /data ownership, then drops privileges to redis.
exec /usr/local/bin/docker-entrypoint.sh redis-server /tmp/relayn-redis.conf
