#!/usr/bin/env bash
# Re-applies all passwords from .env to the running Postgres and Grafana.
set -euo pipefail
cd "$(dirname "$0")"
set -a; source .env; set +a

# Start/recreate containers so they pick up the new env values
docker compose up -d

# Wait for Postgres
until docker compose exec -T timescaledb pg_isready -U postgres >/dev/null 2>&1; do
  sleep 1
done

set_role_password() {   # $1 = role, $2 = password
  echo "ALTER ROLE $1 PASSWORD :'pw';" | \
    docker compose exec -T timescaledb psql -U postgres -d yamana \
      -v ON_ERROR_STOP=1 -v pw="$2"
}

set_role_password postgres   "$POSTGRES_PASSWORD"
set_role_password collector  "$COLLECTOR_PASSWORD"
set_role_password grafana_ro "$GRAFANA_RO_PASSWORD"

# Grafana admin (retry while Grafana is still starting up)
for i in $(seq 1 20); do
  if docker compose exec -T grafana grafana cli admin reset-admin-password \
       "$GRAFANA_ADMIN_PASSWORD"; then
    break
  fi
  sleep 2
done

echo "Done."
