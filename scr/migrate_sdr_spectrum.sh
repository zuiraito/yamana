#!/bin/bash
# Adds the sdr_spectrum table to an EXISTING database (initdb/ only runs on an empty volume).
# Run from the project root:  ./scr/migrate_sdr_spectrum.sh
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T timescaledb psql -v ON_ERROR_STOP=1 -U postgres -d yamana <<'SQL'
CREATE TABLE IF NOT EXISTS sdr_spectrum (
  time           timestamptz NOT NULL,
  center_freq_hz bigint      NOT NULL,
  sample_rate_hz integer     NOT NULL,
  db_min         real        NOT NULL,
  db_max         real        NOT NULL,
  bins           bytea       NOT NULL
);
SELECT create_hypertable('sdr_spectrum', 'time', if_not_exists => TRUE);
SELECT add_retention_policy('sdr_spectrum', INTERVAL '7 days', if_not_exists => TRUE);
GRANT INSERT ON sdr_spectrum TO collector;
GRANT SELECT ON sdr_spectrum TO grafana_ro;
SQL
