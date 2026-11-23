#!/bin/bash
# Runs once, on first start of an empty database volume.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v collector_pw="$COLLECTOR_PASSWORD" \
  -v grafana_pw="$GRAFANA_RO_PASSWORD" <<'SQL'

CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE aprs_telemetry (
  time           timestamptz NOT NULL,
  callsign       text        NOT NULL,
  latitude       double precision,
  longitude      double precision,
  altitude_m     double precision,
  speed_kmh      double precision,
  course_deg     int,
  frame_counter  int,
  temperature_c  double precision,
  pressure_hpa   double precision,
  voltage_v      double precision,
  satellites     int,
  comment        text
);
SELECT create_hypertable('aprs_telemetry', 'time');
GRANT INSERT ON aprs_telemetry TO collector;
GRANT SELECT ON aprs_telemetry TO grafana_ro;
SQL
